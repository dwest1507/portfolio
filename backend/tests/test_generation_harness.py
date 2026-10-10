"""Tests for the generation harness entry point (ADR-0007).

The retriever and generator are injected, so these run with fakes: no index, no model,
no API key. What they pin down is what a Measured Run of generation records, because a
recorded context is what lets a later Judge, or a different generator, replay the run.
"""

from __future__ import annotations

import pytest

from eval.generation import Generation, TokenBudgetExhausted, run_generation, throttled

CASES = [
    {
        "id": "employer-current",
        "split": "dev",
        "category": "direct",
        "question": "Where does David currently work?",
        "relevant_phrases": ["Booz Allen Hamilton"],
    },
    {
        "id": "oos-salary-expectations",
        "answerable": False,
        "split": "holdout",
        "question": "What salary range is David looking for?",
    },
]

CHUNKS = {
    "Where does David currently work?": ["David works at Booz Allen Hamilton."],
    "What salary range is David looking for?": [],
}


def fake_retrieve(question: str) -> list[str]:
    return CHUNKS[question]


def fake_generate(question: str, chunks: list[str]) -> Generation:
    answer = chunks[0] if chunks else "I don't have that information."
    return Generation(
        text=answer,
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        model="fake-model-1",
    )


def test_each_case_records_its_answer_context_usage_and_model():
    """Everything a later Judge or a replaying generator needs, per case."""
    run = run_generation(CASES, fake_retrieve, fake_generate)

    assert run["cases"] == [
        {
            "id": "employer-current",
            "split": "dev",
            "answerable": True,
            "question": "Where does David currently work?",
            "chunks": ["David works at Booz Allen Hamilton."],
            "answer": "David works at Booz Allen Hamilton.",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "model": "fake-model-1",
        },
        {
            "id": "oos-salary-expectations",
            "split": "holdout",
            "answerable": False,
            "question": "What salary range is David looking for?",
            "chunks": [],
            "answer": "I don't have that information.",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "model": "fake-model-1",
        },
    ]


def test_the_run_totals_the_usage_it_was_billed_for():
    """Billed usage, summed, is what a run costs against a provider's daily allowance."""
    run = run_generation(CASES, fake_retrieve, fake_generate)

    assert run["usage"] == {"prompt_tokens": 200, "completion_tokens": 40, "total_tokens": 240}


def test_each_answer_is_handed_over_as_it_is_recorded():
    """An interrupted run keeps the answers already paid for, so it can resume."""
    recorded = []

    def generate_once(question, chunks):
        if recorded:
            raise TokenBudgetExhausted("out of tokens")
        return fake_generate(question, chunks)

    with pytest.raises(TokenBudgetExhausted):
        run_generation(CASES, fake_retrieve, generate_once, on_case=recorded.append)

    assert [r["id"] for r in recorded] == ["employer-current"]


# ---------------------------------------------------------------------------
# Throttling to a free tier
# ---------------------------------------------------------------------------


class FakeClock:
    """A clock that only moves when the code under test sleeps, or a call takes time."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def billing(tokens: int, clock: FakeClock, call_seconds: float = 0.0, starts=None):
    """A generator billing `tokens` per answer, noting when each call started."""

    def generate(question: str, chunks: list[str]) -> Generation:
        if starts is not None:
            starts.append(clock.now)
        clock.now += call_seconds
        return Generation(text="ok", usage={"total_tokens": tokens}, model="fake-model-1")

    return generate


def test_calls_are_paced_to_the_tokens_per_minute_limit():
    """2,000 tokens at 8,000 a minute: the next call waits a quarter of a minute."""
    clock, starts = FakeClock(), []
    generate = throttled(
        billing(2000, clock, starts=starts),
        tokens_per_minute=8000,
        clock=clock,
        sleep=clock.sleep,
    )

    for _ in range(3):
        generate("q", [])

    assert starts == [0.0, 15.0, 30.0]


def test_time_spent_generating_counts_towards_the_wait():
    """A call slower than its token allowance leaves nothing to wait for."""
    clock, starts = FakeClock(), []
    generate = throttled(
        billing(2000, clock, call_seconds=20.0, starts=starts),
        tokens_per_minute=8000,
        clock=clock,
        sleep=clock.sleep,
    )

    generate("q", [])
    generate("q", [])

    assert starts == [0.0, 20.0]


def test_a_call_that_would_overspend_the_token_budget_is_never_made():
    """The daily allowance is shared with visitors, so the run stops short of the budget.

    The next call is assumed to cost as much as the largest so far: 2,000 + 2,000 spent,
    and another 2,000 would pass 5,000.
    """
    clock, starts = FakeClock(), []
    generate = throttled(
        billing(2000, clock, starts=starts),
        tokens_per_minute=8000,
        token_budget=5000,
        clock=clock,
        sleep=clock.sleep,
    )

    generate("q", [])
    generate("q", [])
    with pytest.raises(TokenBudgetExhausted):
        generate("q", [])

    assert len(starts) == 2
