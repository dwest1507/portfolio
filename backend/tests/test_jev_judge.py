"""Tests for the Jev adapter: the requests it sends, not Jev's answers.

The adapter is thin, and judging is tested through the harness with a fake Judge
(test_generation_harness.py). What is pinned down here is what a fake cannot show: that
every request names the exact Judge version, and that an answer from any other version is
refused rather than recorded (ADR-0007).
"""

from __future__ import annotations

import json

import httpx
import pytest

from eval.generation import RELATIONS, Relation
from eval.judge import JEV_MODEL, JEV_URL, JevJudge, JudgeVersionChanged


def jev_answering(answer: dict, model: str = "jev-1.13.0", requests: list | None = None):
    """An httpx client whose transport answers every question with `answer`."""

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if requests is not None:
            requests.append((request, body))
        return httpx.Response(
            200,
            json={
                "model": model,
                "answers": {key: answer for key in body["questions"]},
                "usage": {"input_tokens": 120, "output_tokens": 3},
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handle))


class WholeSentence:
    """A splitter that returns each sentence as its one claim."""

    model = "whole-sentence-1"

    def __call__(self, question, sentence):
        return [sentence]


def test_the_judge_is_pinned_to_an_exact_version():
    assert JEV_MODEL == "jev-1.13.0"


def test_claims_come_from_the_splitter_the_judge_was_given():
    """Jev returns judgments, not text, so another model splits sentences into claims."""

    class Halves:
        model = "halves-1"

        def __call__(self, question, sentence):
            return [f"{question}: first half", f"{question}: second half"]

    judge = JevJudge("test-key", Halves(), client=jev_answering({"type": "noul", "noul": 0.7}))

    assert judge.claims("q", "A and B.") == ["q: first half", "q: second half"]
    assert judge.splitter_model == "halves-1"


@pytest.mark.parametrize(("noul", "factual"), [(0.9, True), (0.3, True), (0.1, False)])
def test_a_sentence_is_filler_only_when_jev_is_confident_it_is(noul, factual):
    """A factual sentence dropped as filler is never checked, which flatters Faithfulness.

    Filler kept as factual only counts against it, so the doubtful middle is kept.
    """
    judge = JevJudge(
        "test-key", WholeSentence(), client=jev_answering({"type": "noul", "noul": noul})
    )

    assert judge.is_factual("The system enforces several safeguards.") is factual


def test_a_support_judgment_asks_jev_about_one_sentence_against_one_chunk():
    requests = []
    answer = {
        "type": "choice",
        "choice": "supports",
        "probabilities": {"supports": 0.9, "contradicts": 0.02, "says_nothing": 0.08},
        "confidence": 0.85,
    }
    judge = JevJudge("test-key", WholeSentence(), client=jev_answering(answer, requests=requests))

    relation = judge.relation("David works at Booz Allen.", "I work at Booz Allen Hamilton.")

    assert relation == Relation("supports", answer["probabilities"])
    [(request, body)] = requests
    assert str(request.url) == JEV_URL
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body["model"] == "jev-1.13.0"
    assert body["state"] == {
        "claim": "David works at Booz Allen.",
        "section": "I work at Booz Allen Hamilton.",
    }
    [question] = body["questions"].values()
    assert question["type"] == "choice"
    assert tuple(question["criteria"]) == RELATIONS


@pytest.mark.parametrize(
    ("ask", "state"),
    [
        (
            lambda judge: judge.is_factual("David is a Lead AI Engineer."),
            {"sentence": "David is a Lead AI Engineer."},
        ),
        (
            lambda judge: judge.conveys(
                "He works at Booz Allen.", "David works at Booz Allen Hamilton."
            ),
            {"answer": "He works at Booz Allen.", "fact": "David works at Booz Allen Hamilton."},
        ),
        (
            lambda judge: judge.declines("Where is David based?", "I don't have that information."),
            {"question": "Where is David based?", "answer": "I don't have that information."},
        ),
    ],
)
def test_yes_no_judgments_ask_one_noul_question_and_answer_yes_above_even_odds(ask, state):
    requests = []
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_answering({"type": "noul", "noul": 0.7}, requests=requests),
    )

    assert ask(judge) is True
    [(_, body)] = requests
    assert body["model"] == "jev-1.13.0"
    assert body["state"] == state
    [question] = body["questions"].values()
    assert question["type"] == "noul"


def test_an_answer_from_any_other_judge_version_is_refused():
    """A silently upgraded Judge makes runs incomparable, so it fails the run instead."""
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_answering({"type": "noul", "noul": 0.7}, model="jev-1.14.0"),
    )

    with pytest.raises(JudgeVersionChanged, match="jev-1.14.0"):
        judge.is_factual("David is a Lead AI Engineer.")


def test_billed_usage_is_totalled_across_judgments():
    judge = JevJudge(
        "test-key", WholeSentence(), client=jev_answering({"type": "noul", "noul": 0.2})
    )

    judge.is_factual("Happy to help!")
    judge.is_factual("Anything else?")

    assert judge.usage == {"input_tokens": 240, "output_tokens": 6}
