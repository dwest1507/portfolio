"""Tests for validating the Judge against hand labels (ADR-0007).

Before a Judge result gates a build, its verdicts on ~30 hand-labelled answer sentences
are compared with the labels. These run with a fake Judge: what they pin down is how a
verdict is read off the Judge's judgments, and which disagreements are reported.
"""

from __future__ import annotations

import json

from eval.generation import split_sentences
from eval.run_generation import BASELINE_PATH
from eval.validate_judge import (
    FINAL_RUNS,
    HAND_LABELS,
    VALIDATION_PATH,
    compare,
    load_validation_set,
    median_of,
    missed_bar,
)
from tests.test_generation_harness import FakeJudge


def test_every_hand_label_is_on_a_sentence_the_harness_would_judge():
    """A label on a sentence the splitter no longer produces validates nothing.

    If the stored record or the sentence splitter changes, this fails rather than
    letting the validation quietly measure sentences the harness never sees.
    """
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    answers = {case["id"]: case["answer"] for case in record["cases"]}
    labelled = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["sentences"]
    taken = [sentence for sentence in labelled if not sentence.get("heldOut")]

    assert 25 <= len(taken) <= 40
    for sentence in taken:
        assert sentence["text"] in split_sentences(answers[sentence["case"]]), sentence
        assert sentence["label"] in HAND_LABELS, sentence
        assert isinstance(sentence["compound"], bool), sentence


def test_held_out_sentences_are_unsupported_and_written_against_a_recorded_case():
    """Hand-written, not taken from an answer, so the splitter check above skips them.

    They exist to catch question wording tuned to the other labels: each is a sentence
    the Judge should call unsupported, kept out of tuning until the final measurement.
    """
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    cases = {case["id"] for case in record["cases"]}
    labelled = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["sentences"]
    held_out = [sentence for sentence in labelled if sentence.get("heldOut")]

    assert len(held_out) >= 10
    for sentence in held_out:
        assert sentence["case"] in cases, sentence
        assert sentence["label"] in ("contradicted", "says_nothing"), sentence
        assert isinstance(sentence["compound"], bool), sentence


def test_sentences_supported_only_by_several_chunks_together_are_marked():
    """A stricter `supports`, asked one chunk at a time, could fail exactly these."""
    labelled = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["sentences"]
    across = [sentence for sentence in labelled if sentence.get("acrossChunks")]

    assert len(across) >= 5
    for sentence in across:
        assert sentence["label"] == "supported", sentence
        assert sentence["compound"], sentence


def test_each_labelled_sentence_is_loaded_with_the_chunks_its_answer_was_written_from():
    """The Judge must see what the generator saw, not today's retrieval.

    The question comes too: splitting a sentence into claims resolves "it" and "the
    system" from it.
    """
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in record["cases"]}

    items = load_validation_set(held_out=True)

    assert len(items) == len(json.loads(VALIDATION_PATH.read_text())["sentences"])
    for item in items:
        assert item["chunks"] == cases[item["case"]]["chunks"]
        assert item["question"] == cases[item["case"]]["question"]


def test_held_out_sentences_are_left_out_unless_asked_for():
    """Tuning the Judge's questions must never see Jev's judgments of the held-out set."""
    labelled = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["sentences"]
    held_out = sum(1 for sentence in labelled if sentence.get("heldOut"))

    tuning = load_validation_set()

    assert len(tuning) == len(labelled) - held_out
    assert not any(item.get("heldOut") for item in tuning)


# ---------------------------------------------------------------------------
# Comparing the Judge with the hand labels
# ---------------------------------------------------------------------------

CHUNKS = ["David works at Booz Allen Hamilton.", "The corpus holds 19 works."]


def labelled(text, label, compound=False):
    return {
        "case": "c",
        "question": "q",
        "text": text,
        "label": label,
        "compound": compound,
        "chunks": CHUNKS,
    }


def test_agreement_is_counted_as_faithfulness_counts_a_sentence():
    """Filler, supported, or not: contradicted and says-nothing both count as unsupported."""
    items = [
        labelled("Happy to help!", "filler"),
        labelled("David works at Booz Allen.", "supported"),
        labelled("David has a PhD.", "says_nothing"),
        labelled("The corpus holds 18 works.", "contradicted"),
    ]
    judge = FakeJudge(
        filler={"Happy to help!"},
        relations={
            ("David works at Booz Allen.", CHUNKS[0]): "supports",
            ("David has a PhD.", CHUNKS[1]): "supports",
            ("The corpus holds 18 works.", CHUNKS[1]): "contradicts",
        },
    )

    report = compare(items, judge)

    assert report["sentences"] == 4
    assert report["faithfulnessAgreement"] == 3 / 4
    assert [d["text"] for d in report["disagreements"]] == ["David has a PhD."]


def test_a_contradiction_the_judge_lists_or_misses_is_a_disagreement():
    """A listed Contradiction is a false statement about David; listing one wrongly matters.

    The supported sentence counts as supported in Faithfulness, so Faithfulness agrees,
    but the Judge also lists it as contradicted by another chunk.
    """
    items = [
        labelled("David works at Booz Allen.", "supported"),
        labelled("The corpus holds 18 works.", "contradicted"),
    ]
    judge = FakeJudge(
        relations={
            ("David works at Booz Allen.", CHUNKS[0]): "supports",
            ("David works at Booz Allen.", CHUNKS[1]): "contradicts",
        },
    )

    report = compare(items, judge)

    assert report["faithfulnessAgreement"] == 1.0
    assert report["contradictionAgreement"] == 0.0
    assert [
        (d["text"], d["hand"], d["judge"], d["judgeContradicts"]) for d in report["disagreements"]
    ] == [
        ("David works at Booz Allen.", "supported", "supported", True),
        ("The corpus holds 18 works.", "contradicted", "unsupported", False),
    ]


def test_disagreements_are_counted_separately_for_compound_sentences():
    """If they cluster on compound sentences, that is the case for LLM claim splitting."""
    items = [
        labelled("David works at Booz Allen and has a PhD.", "says_nothing", compound=True),
        labelled("David works at Booz Allen, as a Lead AI Engineer.", "supported", compound=True),
        labelled("David works at Booz Allen.", "supported"),
    ]
    judge = FakeJudge(
        relations={
            ("David works at Booz Allen and has a PhD.", CHUNKS[0]): "supports",
            ("David works at Booz Allen.", CHUNKS[0]): "supports",
        },
    )

    report = compare(items, judge)

    assert report["compound"] == {"sentences": 2, "disagreements": 2}
    assert report["single"] == {"sentences": 1, "disagreements": 0}


# ---------------------------------------------------------------------------
# The pass bar
# ---------------------------------------------------------------------------


def test_the_bar_is_measured_as_shares_of_the_sentences_it_covers():
    """Shares, not counts, so the bar holds as the labelled set grows.

    Unsupported sentences caught counts only held-out ones: the others were tuned against,
    so the Mars sentence the Judge misses here does not count.
    """
    across = "David works at Booz Allen; the corpus holds 19 works."
    items = [
        {**labelled("David has a PhD.", "says_nothing"), "heldOut": True},
        {**labelled("The corpus holds 18 works.", "contradicted"), "heldOut": True},
        labelled("David lives on Mars.", "says_nothing"),
        labelled("David works at Booz Allen.", "supported"),
        {**labelled(across, "supported", compound=True), "acrossChunks": True},
    ]
    judge = FakeJudge(
        relations={
            ("The corpus holds 18 works.", CHUNKS[1]): "contradicts",
            ("David lives on Mars.", CHUNKS[0]): "supports",
            ("David works at Booz Allen.", CHUNKS[0]): "supports",
        },
    )

    report = compare(items, judge)

    assert report["heldOutUnsupportedCaught"] == 1.0
    assert report["supportedKept"] == 1 / 2
    assert report["acrossChunksKept"] == 0.0


def report_with(**shares):
    passing = {
        "faithfulnessAgreement": 0.9,
        "heldOutUnsupportedCaught": 10 / 12,
        "supportedKept": 20 / 22,
        "acrossChunksKept": 4 / 5,
    }
    return {**passing, **shares}


def test_a_report_meeting_every_share_of_the_bar_misses_nothing():
    assert missed_bar(report_with()) == []


def test_each_share_below_the_bar_is_named():
    report = report_with(heldOutUnsupportedCaught=9 / 12, supportedKept=19 / 22)

    assert missed_bar(report) == ["heldOutUnsupportedCaught", "supportedKept"]


def test_the_final_measurement_checks_the_bar_against_the_median_of_its_runs():
    """Splits and Jev's borderline judgments vary, so one run could pass or fail on noise."""
    runs = [
        report_with(supportedKept=19 / 22, heldOutUnsupportedCaught=12 / 12),
        report_with(supportedKept=22 / 22, heldOutUnsupportedCaught=9 / 12),
        report_with(supportedKept=20 / 22, heldOutUnsupportedCaught=10 / 12),
    ]

    median = median_of(runs)

    assert median["supportedKept"] == 20 / 22
    assert median["heldOutUnsupportedCaught"] == 10 / 12
    assert missed_bar(median) == []
    assert FINAL_RUNS == 3


def test_a_run_without_held_out_sentences_cannot_meet_the_bar():
    """Agreement on sentences the questions were tuned against proves nothing."""
    assert missed_bar(report_with(heldOutUnsupportedCaught=None)) == ["heldOutUnsupportedCaught"]
