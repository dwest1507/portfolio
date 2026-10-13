"""Tests for the manual comparison run of Candidate Arms through generation (ADR-0009).

A fake generator and a fake Judge stand in for OpenAI and Jev, and each Arm's retriever is
a stub, so no model is called: what these pin down is which Arms run, what each run
records, and how the Arms are compared with the Shipped Arm.
"""

from __future__ import annotations

import pytest

from eval import compare_arms as compare_arms_module
from eval.compare_arms import compare_arms, format_comparison
from eval.generation import Generation, Relation
from eval.publish import ARM_SPECS, CANDIDATE, REFERENCE, Arm, shipped_arm_id

CANDIDATES = [a.id for a in ARM_SPECS if a.eligibility == CANDIDATE]
REFERENCES = [a.id for a in ARM_SPECS if a.eligibility == REFERENCE]

#: None is measured at present (ADR-0013), so the filter is tested against one made up.
CEILING = Arm(
    id="ceiling",
    label="Quality ceiling",
    description="An Arm too heavy to ship, kept to show what is possible.",
    technical="A stand-in for a deliberately added Reference Arm.",
    eligibility=REFERENCE,
)


class FakeJudge:
    """Supports a claim when its chunk says `good`; declines when the answer says `none`."""

    model = "jev-test"
    splitter_model = "splitter-test"

    def is_factual(self, sentence: str) -> bool:
        return True

    def claims(self, question: str, sentence: str) -> list[str]:
        return [sentence]

    def relation(self, claim: str, chunk: str) -> Relation:
        if "good" in chunk:
            return Relation("supports", {"supports": 0.9})
        return Relation("says_nothing", {"says_nothing": 0.9})

    def conveys(self, answer: str, fact: str) -> bool:
        return "good" in answer

    def declines(self, question: str, answer: str) -> bool:
        return "none" in answer


def generate(question: str, chunks: list[str]) -> Generation:
    """Repeats the context, or declines when there is none."""
    text = " ".join(chunks) + "." if chunks else "There is none."
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    return Generation(text=text, usage=usage, model="gpt-test")


def case(case_id: str, split: str = "dev", answerable: bool = True) -> dict:
    return {
        "id": case_id,
        "split": split,
        "answerable": answerable,
        "question": f"Question {case_id}?",
        "required_facts": ["A fact."] if answerable else [],
    }


def retriever(chunk: str):
    return lambda question: [chunk]


def refusing(arm: str):
    def retrieve(question: str) -> list[str]:
        raise AssertionError(f"Reference Arm {arm} was run through generation.")

    return retrieve


def all_retrievers(**chunks: str) -> dict:
    """A retriever for every Arm: Candidates return `chunks[arm]` (default `good`),
    Reference Arms fail the test if called."""
    retrievers = {arm: refusing(arm) for arm in REFERENCES}
    for arm in CANDIDATES:
        retrievers[arm] = retriever(chunks.get(arm, "good"))
    return retrievers


class TestCompareArms:
    def test_runs_every_candidate_arm(self):
        runs = compare_arms([case("a")], all_retrievers(), generate, FakeJudge())

        assert sorted(runs) == sorted(CANDIDATES)

    def test_runs_no_reference_arm(self, monkeypatch):
        """Reference Arms can't ship, so no API budget is spent on them (story 55)."""
        monkeypatch.setattr(compare_arms_module, "ARM_SPECS", (*ARM_SPECS, CEILING))
        retrievers = {**all_retrievers(), CEILING.id: refusing(CEILING.id)}

        runs = compare_arms([case("a")], retrievers, generate, FakeJudge())

        assert sorted(runs) == sorted(CANDIDATES)

    def test_the_shipped_arm_is_among_the_runs(self):
        """It is what every Candidate Arm is compared with."""
        runs = compare_arms([case("a")], all_retrievers(), generate, FakeJudge())

        assert shipped_arm_id() in runs

    def test_each_run_answers_from_its_own_arms_retrieval(self):
        runs = compare_arms(
            [case("a")], all_retrievers(**{"onnx-dense": "bad"}), generate, FakeJudge()
        )

        assert runs["onnx-dense"]["cases"][0]["chunks"] == ["bad"]
        assert runs[shipped_arm_id()]["cases"][0]["chunks"] == ["good"]

    def test_each_run_is_judged_on_every_split(self):
        """Dev decides and holdout confirms, so both are measured (ADR-0009)."""
        cases = [case("a", split="dev"), case("b", split="holdout")]

        runs = compare_arms(cases, all_retrievers(), generate, FakeJudge())

        for run in runs.values():
            assert [c["split"] for c in run["cases"]] == ["dev", "holdout"]
            assert run["judge"] == "jev-test"
            assert "metrics" in run

    def test_refuses_when_a_candidate_arm_has_no_retriever(self):
        retrievers = all_retrievers()
        del retrievers["onnx-hybrid"]

        with pytest.raises(ValueError, match="onnx-hybrid"):
            compare_arms([case("a")], retrievers, generate, FakeJudge())


class TestFormatComparison:
    """The `dev` report is what the Shipped Arm decision is read from (ADR-0009)."""

    def runs(self):
        cases = [case(f"d{i}", split="dev") for i in range(8)] + [case("h", split="holdout")]
        # onnx-dense retrieves nothing, so it declines all eight dev questions.
        retrievers = all_retrievers()
        retrievers["onnx-dense"] = lambda question: []
        return compare_arms(cases, retrievers, generate, FakeJudge())

    def test_reports_only_the_requested_split(self):
        report = format_comparison(self.runs(), "dev")

        assert report.startswith("dev (8 cases)")

    def test_lists_every_candidate_arm_and_marks_the_shipped_one(self):
        report = format_comparison(self.runs(), "dev")

        for arm in CANDIDATES:
            assert arm in report
        assert f"{shipped_arm_id()} (shipped)" in report

    def test_reports_each_arms_won_and_lost_against_the_shipped_arm(self):
        """Declining all eight answerable questions bm25 answered: lost 8, p = 0.008."""
        report = format_comparison(self.runs(), "dev")

        assert "onnx-dense vs bm25:" in report
        assert "declineAccuracy  won  0, lost  8: behind" in report
        assert "onnx-hybrid vs bm25:" in report
        assert "declineAccuracy  won  0, lost  0: indistinguishable" in report
