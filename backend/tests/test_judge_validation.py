"""Tests for validating the Judge against hand labels (ADR-0007).

Before a Judge result gates a build, its verdicts on ~30 hand-labelled answer sentences
are compared with the labels. These run with a fake Judge: what they pin down is how a
verdict is read off the Judge's judgments, and which disagreements are reported.
"""

from __future__ import annotations

import json

from eval.generation import split_sentences
from eval.run_generation import BASELINE_PATH
from eval.validate_judge import HAND_LABELS, VALIDATION_PATH, compare, load_validation_set
from tests.test_generation_harness import FakeJudge


def test_every_hand_label_is_on_a_sentence_the_harness_would_judge():
    """A label on a sentence the splitter no longer produces validates nothing.

    If the stored record or the sentence splitter changes, this fails rather than
    letting the validation quietly measure sentences the harness never sees.
    """
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    answers = {case["id"]: case["answer"] for case in record["cases"]}
    labelled = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["sentences"]

    assert 25 <= len(labelled) <= 40
    for sentence in labelled:
        assert sentence["text"] in split_sentences(answers[sentence["case"]]), sentence
        assert sentence["label"] in HAND_LABELS, sentence
        assert isinstance(sentence["compound"], bool), sentence


def test_each_labelled_sentence_is_loaded_with_the_chunks_its_answer_was_written_from():
    """The Judge must see what the generator saw, not today's retrieval."""
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    chunks = {case["id"]: case["chunks"] for case in record["cases"]}

    items = load_validation_set()

    assert len(items) == len(json.loads(VALIDATION_PATH.read_text())["sentences"])
    for item in items:
        assert item["chunks"] == chunks[item["case"]]


# ---------------------------------------------------------------------------
# Comparing the Judge with the hand labels
# ---------------------------------------------------------------------------

CHUNKS = ["David works at Booz Allen Hamilton.", "The corpus holds 19 works."]


def labelled(text, label, compound=False):
    return {"case": "c", "text": text, "label": label, "compound": compound, "chunks": CHUNKS}


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
