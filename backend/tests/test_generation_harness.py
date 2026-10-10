"""Tests for the generation harness entry point (ADR-0007).

The retriever and generator are injected, so these run with fakes: no index, no model,
no API key. What they pin down is what a Measured Run of generation records, because a
recorded context is what lets a later Judge, or a different generator, replay the run.
"""

from __future__ import annotations

import pytest

from eval.generation import (
    Generation,
    Relation,
    TokenBudgetExhausted,
    format_report,
    replay,
    run_generation,
    throttled,
)

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


# ---------------------------------------------------------------------------
# Judging answers
# ---------------------------------------------------------------------------


class FakeJudge:
    """A Judge returning scripted judgments, one method per judgment.

    Unscripted judgments take the least eventful answer: a sentence is factual, a chunk
    says nothing about it, a fact is not conveyed, an answer does not decline.
    """

    model = "fake-judge-1.0.0"

    def __init__(self, filler=(), relations=None, conveyed=(), declining=()):
        self.filler = set(filler)
        self.relations = relations or {}
        self.conveyed = set(conveyed)
        self.declining = set(declining)
        self.calls = []

    def is_factual(self, sentence):
        self.calls.append(("is_factual", sentence))
        return sentence not in self.filler

    def relation(self, sentence, chunk):
        self.calls.append(("relation", sentence, chunk))
        return Relation(self.relations.get((sentence, chunk), "says_nothing"), {})

    def conveys(self, answer, fact):
        self.calls.append(("conveys", fact))
        return fact in self.conveyed

    def declines(self, question, answer):
        self.calls.append(("declines", answer))
        return answer in self.declining


def answering(answers: dict[str, str]):
    """A generator answering each question with a scripted answer."""

    def generate(question: str, chunks: list[str]) -> Generation:
        return Generation(text=answers[question], usage={"total_tokens": 1}, model="fake-model-1")

    return generate


def retrieving(chunks):
    return lambda question: chunks


EMPLOYER_CASE = {
    "id": "employer-current",
    "split": "dev",
    "question": "Where does David currently work?",
    "required_facts": [
        "David currently works at Booz Allen Hamilton.",
        "David is a Lead AI Engineer.",
    ],
}
EMPLOYER_CHUNKS = [
    "David works at Booz Allen Hamilton.",
    "In 2026 he became a Lead AI Engineer.",
]


def test_filler_is_left_out_of_faithfulness():
    """A pleasantry is neither supported nor unsupported: it states nothing about David."""
    answer = "David works at Booz Allen Hamilton. Happy to share more!"
    judge = FakeJudge(
        filler={"Happy to share more!"},
        relations={("David works at Booz Allen Hamilton.", EMPLOYER_CHUNKS[0]): "supports"},
    )

    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: answer}),
        judge=judge,
    )

    assert run["metrics"]["faithfulness"] == 1.0
    assert run["metrics"]["factualSentences"] == 1


def test_a_sentence_is_supported_when_any_one_chunk_supports_it():
    """Each sentence is judged against each chunk alone; support from one is enough."""
    first = "David works at Booz Allen Hamilton."
    second = "He is a Lead AI Engineer."
    third = "He has published three papers."
    judge = FakeJudge(
        relations={
            (first, EMPLOYER_CHUNKS[0]): "supports",
            (second, EMPLOYER_CHUNKS[1]): "supports",
        },
    )

    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: f"{first} {second} {third}"}),
        judge=judge,
    )

    assert run["metrics"]["faithfulness"] == pytest.approx(2 / 3)
    judged_pairs = [call[1:] for call in judge.calls if call[0] == "relation"]
    assert sorted(judged_pairs) == sorted(
        (sentence, chunk) for sentence in (first, second, third) for chunk in EMPLOYER_CHUNKS
    )


def test_each_contradiction_is_listed_with_its_sentence_and_chunk():
    """Each one is a false statement about David, so each is listed for review, not averaged."""
    wrong = "David works at Deloitte."
    judge = FakeJudge(relations={(wrong, EMPLOYER_CHUNKS[0]): "contradicts"})

    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: f"{wrong} He is a Lead AI Engineer."}),
        judge=judge,
    )

    assert run["contradictions"] == [
        {"case": "employer-current", "sentence": wrong, "chunk": EMPLOYER_CHUNKS[0]},
    ]
    assert run["metrics"]["contradictions"] == 1


def test_the_cli_report_lists_each_contradiction_after_the_metrics():
    wrong = "David works at Deloitte."
    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: wrong}),
        judge=FakeJudge(relations={(wrong, EMPLOYER_CHUNKS[0]): "contradicts"}),
    )

    report = format_report(run)

    assert "Judge: fake-judge-1.0.0" in report
    assert "Faithfulness" in report and "Fact Recall" in report and "Decline accuracy" in report
    assert (
        "Contradictions (1):\n"
        "  employer-current: David works at Deloitte.\n"
        "    contradicted by: David works at Booz Allen Hamilton."
    ) in report


def test_fact_recall_is_the_share_of_required_facts_the_answers_convey():
    """Judged on meaning: the answer below never says "currently", and still conveys it."""
    answer = "David works at Booz Allen Hamilton."
    judge = FakeJudge(conveyed={"David currently works at Booz Allen Hamilton."})

    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: answer}),
        judge=judge,
    )

    assert run["cases"][0]["facts"] == [
        {"fact": "David currently works at Booz Allen Hamilton.", "conveyed": True},
        {"fact": "David is a Lead AI Engineer.", "conveyed": False},
    ]
    assert run["metrics"]["factRecall"] == 0.5


def test_answers_are_judged_one_self_contained_sentence_at_a_time():
    """Split in code, in the shapes the chatbot actually answers in.

    A list item alone ("SQLite") states nothing, so each one is judged with the line that
    introduces it. Markdown emphasis is not part of the claim, and "e.g." ends no sentence.
    """
    answer = (
        "David has worked with the following databases:\n"
        "\n"
        "- **SQLite**\n"
        "- **Amazon DynamoDB** (for work projects)\n"
        "\n"
        "He uses SlowAPI (e.g., in the chatbot backend) to limit requests. It is keyed by IP."
    )
    judge = FakeJudge()

    run_generation(
        [EMPLOYER_CASE],
        retrieving([]),
        answering({EMPLOYER_CASE["question"]: answer}),
        judge=judge,
    )

    assert [call[1] for call in judge.calls if call[0] == "is_factual"] == [
        "David has worked with the following databases: SQLite",
        "David has worked with the following databases: Amazon DynamoDB (for work projects)",
        "He uses SlowAPI (e.g., in the chatbot backend) to limit requests.",
        "It is keyed by IP.",
    ]


def test_a_table_is_judged_one_row_at_a_time_with_its_column_headings():
    """A row's cells mean something only under their headings, and a row is one claim."""
    answer = (
        "David's tools:\n"
        "| Context | Tools |\n"
        "|---|---|\n"
        "| Work | • Windsurf IDE<br>• Terraform (IaC) |\n"
        "| Personal projects | VS Code. Claude Code |\n"
    )
    judge = FakeJudge()

    run_generation(
        [EMPLOYER_CASE],
        retrieving([]),
        answering({EMPLOYER_CASE["question"]: answer}),
        judge=judge,
    )

    assert [call[1] for call in judge.calls if call[0] == "is_factual"] == [
        "David's tools: Context: Work; Tools: Windsurf IDE, Terraform (IaC)",
        "David's tools: Context: Personal projects; Tools: VS Code. Claude Code",
    ]


SALARY_CASE = {
    "id": "oos-salary-expectations",
    "answerable": False,
    "split": "holdout",
    "question": "What salary range is David looking for?",
}
DECLINE = "I'm sorry, but the provided information doesn't include that."


def test_a_declined_fair_question_conveys_none_of_its_required_facts():
    """The Judge is weak on negation, so a Decline is never judged for support or facts.

    Declining a fair question is a failure twice over: it counts against Decline
    accuracy, and it conveys none of the Required Facts, so Fact Recall falls. A Decline
    states nothing, so it leaves Faithfulness with nothing to measure.
    """
    judge = FakeJudge(declining={DECLINE})

    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: DECLINE}),
        judge=judge,
    )

    assert [call[0] for call in judge.calls] == ["declines"]
    assert run["cases"][0]["declined"] is True
    assert run["metrics"]["declineAccuracy"] == 0.0
    assert run["metrics"]["answeredAnswerable"] == 0.0
    assert run["cases"][0]["facts"] == [
        {"fact": "David currently works at Booz Allen Hamilton.", "conveyed": False},
        {"fact": "David is a Lead AI Engineer.", "conveyed": False},
    ]
    assert run["metrics"]["factRecall"] == 0.0
    assert run["metrics"]["faithfulness"] is None


def test_out_of_scope_cases_are_scored_only_on_declining():
    """An Out-of-Scope Case has no Required Facts, and whatever it answered is not checked
    for support: the only question is whether it declined."""
    answered_case = {**SALARY_CASE, "id": "oos-answered", "question": "What car does David drive?"}
    judge = FakeJudge(declining={DECLINE})

    run = run_generation(
        [SALARY_CASE, answered_case],
        retrieving(EMPLOYER_CHUNKS),
        answering(
            {
                SALARY_CASE["question"]: DECLINE,
                answered_case["question"]: "David drives a red Honda Civic.",
            }
        ),
        judge=judge,
    )

    assert [call[0] for call in judge.calls] == ["declines", "declines"]
    assert [r["declined"] for r in run["cases"]] == [True, False]
    assert run["metrics"]["declinedOutOfScope"] == 0.5
    assert run["metrics"]["declineAccuracy"] == 0.5
    assert run["metrics"]["factualSentences"] == 0


def test_decline_accuracy_counts_both_directions():
    """Declining out of scope and answering in scope are both correct."""
    judge = FakeJudge(declining={DECLINE})

    run = run_generation(
        [EMPLOYER_CASE, SALARY_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering(
            {
                EMPLOYER_CASE["question"]: "David works at Booz Allen Hamilton.",
                SALARY_CASE["question"]: DECLINE,
            }
        ),
        judge=judge,
    )

    assert run["metrics"]["declineAccuracy"] == 1.0
    assert run["metrics"]["answeredAnswerable"] == 1.0
    assert run["metrics"]["declinedOutOfScope"] == 1.0


def test_a_judged_run_records_the_judge_version_that_answered():
    """A Judge that changed silently would make two Measured Runs incomparable."""
    run = run_generation(
        [EMPLOYER_CASE],
        retrieving(EMPLOYER_CHUNKS),
        answering({EMPLOYER_CASE["question"]: "David works at Booz Allen Hamilton."}),
        judge=FakeJudge(),
    )

    assert run["judge"] == "fake-judge-1.0.0"


# ---------------------------------------------------------------------------
# Judging a stored record
# ---------------------------------------------------------------------------

STORED_RECORD = {
    "provider": "groq",
    "cases": [
        {
            "id": "employer-current",
            "split": "dev",
            "answerable": True,
            "question": "Where does David currently work?",
            "chunks": ["Stored chunk: David works at Booz Allen Hamilton."],
            "answer": "David works at Booz Allen Hamilton.",
            "usage": {"prompt_tokens": 900, "completion_tokens": 30, "total_tokens": 930},
            "model": "openai/gpt-oss-120b",
        }
    ],
}


def test_a_stored_record_is_judged_on_its_own_answers_and_chunks_without_regenerating():
    """The baseline keeps the exact contexts, so judging it later calls no model but the
    Judge, and judges what the model was actually shown."""
    answer = "David works at Booz Allen Hamilton."
    stored_chunk = STORED_RECORD["cases"][0]["chunks"][0]
    judge = FakeJudge(relations={(answer, stored_chunk): "supports"})

    run = run_generation([EMPLOYER_CASE], *replay(STORED_RECORD), judge=judge)

    case = run["cases"][0]
    assert case["answer"] == answer
    assert case["chunks"] == [stored_chunk]
    assert case["model"] == "openai/gpt-oss-120b"
    assert case["usage"]["total_tokens"] == 930
    assert run["metrics"]["faithfulness"] == 1.0


def test_replaying_a_case_the_record_never_answered_fails_loudly():
    """A Golden Set case missing from the record would otherwise shrink the run unseen."""
    retrieve, _ = replay(STORED_RECORD)

    with pytest.raises(KeyError, match="What salary range"):
        retrieve(SALARY_CASE["question"])
