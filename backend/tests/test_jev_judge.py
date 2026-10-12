"""Tests for the Jev adapter: the requests it sends, not Jev's answers.

The adapter is thin, and judging is tested through the harness with a fake Judge
(test_generation_harness.py). What is pinned down here is what a fake cannot show: that
every request names the exact Judge version, that an answer from any other version is
refused rather than recorded (ADR-0007), and that rate-limited requests are retried with
jittered backoff and counted in the reported usage.
"""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

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


# ---------------------------------------------------------------------------
# Retries under rate limits
# ---------------------------------------------------------------------------


def jev_limited(statuses: list[int], retry_after: str | None = None):
    """An httpx client answering with each of `statuses` in turn, then 200 for good.

    A limited response carries `retry_after` as its Retry-After header, when given.
    """
    statuses = list(statuses)

    def handle(request: httpx.Request) -> httpx.Response:
        if statuses:
            headers = {"Retry-After": retry_after} if retry_after is not None else {}
            return httpx.Response(statuses.pop(0), headers=headers)
        return httpx.Response(
            200,
            json={
                "model": JEV_MODEL,
                "answers": {"judgment": {"type": "noul", "noul": 0.7}},
                "usage": {"input_tokens": 120, "output_tokens": 3},
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handle))


@pytest.mark.parametrize("draw", [0.0, 0.5, 0.999])
def test_a_rate_limited_request_waits_a_jittered_interval_and_then_succeeds(draw):
    """Workers limited together must not retry together, so the wait is randomised.

    The first retry waits between 1 and 2 seconds, wherever the random draw lands.
    """
    sleeps = []
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_limited([429]),
        sleep=sleeps.append,
        random=lambda: draw,
    )

    assert judge.is_factual("David is a Lead AI Engineer.") is True
    [wait] = sleeps
    assert 1.0 <= wait < 2.0
    assert wait == pytest.approx(1.0 + draw)


@pytest.mark.parametrize(
    "retry_after",
    ["30", "Wed, 21 Oct 2026 07:28:30 GMT"],  # seconds, or a date 30 seconds after `now`
)
def test_a_retry_after_header_is_honoured(retry_after):
    """The server's own wait is never cut short; jitter still spreads what follows it."""
    now = 1792567680.0  # Wed, 21 Oct 2026 07:28:00 GMT
    sleeps = []
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_limited([429], retry_after=retry_after),
        sleep=sleeps.append,
        random=lambda: 0.5,
        clock=lambda: now,
    )

    assert judge.is_factual("David is a Lead AI Engineer.") is True
    [wait] = sleeps
    assert wait == pytest.approx(45.0)


def test_a_retry_after_shorter_than_the_backoff_does_not_shorten_it():
    sleeps = []
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_limited([529, 529, 529], retry_after="0"),
        sleep=sleeps.append,
        random=lambda: 0.0,
    )

    judge.is_factual("David is a Lead AI Engineer.")

    assert sleeps == [1.0, 2.0, 4.0]


def test_retries_are_reported_with_the_billed_usage():
    """A rate limit shows up as a number in the run's usage, not as an unexplained slow run."""
    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=jev_limited([429, 529]),
        sleep=lambda seconds: None,
    )

    judge.is_factual("David is a Lead AI Engineer.")
    judge.is_factual("He leads a team.")

    assert judge.reported_usage == {"input_tokens": 240, "output_tokens": 6, "retries": 2}


def test_the_retry_count_is_exact_under_concurrent_use():
    """Eight workers share one Judge, so no retry may be lost to a race between them."""
    seen = set()
    seen_lock = threading.Lock()

    def handle(request: httpx.Request) -> httpx.Response:
        sentence = json.loads(request.content)["state"]["sentence"]
        with seen_lock:
            first = sentence not in seen
            seen.add(sentence)
        if first:  # every sentence is limited once, then answered
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "model": JEV_MODEL,
                "answers": {"judgment": {"type": "noul", "noul": 0.7}},
                "usage": {"input_tokens": 120, "output_tokens": 3},
            },
        )

    judge = JevJudge(
        "test-key",
        WholeSentence(),
        client=httpx.Client(transport=httpx.MockTransport(handle)),
        sleep=lambda seconds: None,
    )
    sentences = [f"Sentence {n}." for n in range(400)]
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # switch threads as often as possible, to surface a race
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(judge.is_factual, sentences))
    finally:
        sys.setswitchinterval(interval)

    assert judge.reported_usage == {
        "input_tokens": 120 * 400,
        "output_tokens": 3 * 400,
        "retries": 400,
    }
