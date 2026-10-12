"""Tests for Recalibration: the Floors record, its fingerprint and its fixed rule (ADR-0012).

A Floor is derived from a measurement by a fixed rule and written by the recalibrate
command alone. These check that the rule reproduces its worked example, that the
fingerprint follows exactly the case fields a Floor depends on, and that the committed
retrieval record still describes the committed Golden Set.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.publish import shipped_arm_id
from eval.recalibrate import recalibrate_retrieval
from eval.recalibration import (
    RETRIEVAL_FLOORS_PATH,
    RETRIEVAL_RULE,
    read_record,
    retrieval_fingerprint,
    retrieval_floor,
)
from eval.run_eval import GATED_METRICS, GOLDEN_SET_PATH, answerable_cases


def _case(case_id: str, **fields) -> dict:
    case = {
        "id": case_id,
        "split": "dev",
        "category": "direct",
        "question": f"What about {case_id}?",
        "relevant_phrases": [f"{case_id} phrase"],
        "required_facts": [f"David did {case_id}."],
    }
    case.update(fields)
    return case


CASES = [
    _case("alpha"),
    _case("bravo"),
    _case("charlie", answerable=False, relevant_phrases=[], required_facts=[]),
]


class TestRetrievalFingerprint:
    def test_is_stable_when_cases_are_reordered(self):
        assert retrieval_fingerprint(CASES) == retrieval_fingerprint(list(reversed(CASES)))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("question", "What else about alpha?"),
            ("relevant_phrases", ["alpha phrase", "another phrase"]),
            ("answerable", False),
        ],
    )
    def test_changes_when_a_field_retrieval_reads_changes(self, field, value):
        edited = copy.deepcopy(CASES)
        edited[0][field] = value
        assert retrieval_fingerprint(edited) != retrieval_fingerprint(CASES)

    def test_changes_when_a_case_is_added_or_removed(self):
        assert retrieval_fingerprint(CASES[:2]) != retrieval_fingerprint(CASES)
        assert retrieval_fingerprint([*CASES, _case("delta")]) != retrieval_fingerprint(CASES)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("required_facts", ["David did something else entirely."]),
            ("split", "holdout"),
            ("category", "paraphrase"),
        ],
    )
    def test_ignores_fields_retrieval_never_reads(self, field, value):
        """A Required Fact edit must never stale the retrieval Floors (story 88)."""
        edited = copy.deepcopy(CASES)
        edited[0][field] = value
        assert retrieval_fingerprint(edited) == retrieval_fingerprint(CASES)


class TestRetrievalRule:
    def test_reproduces_the_worked_example(self):
        """Spec #62: hit@5 0.865 with n = 111 gives 0.845. Two cases are 0.018, and
        0.847 rounds down to the 0.005 step."""
        assert retrieval_floor(0.865, 111) == 0.845

    def test_reproduces_todays_mrr(self):
        assert retrieval_floor(0.705, 111) == 0.685

    def test_a_value_already_on_a_step_stays_there(self):
        """0.92 − 2/50 is 0.88 exactly, which floating point would round down past."""
        assert retrieval_floor(0.92, 50) == 0.88


def _measured_run(n: int = 111, hit: float = 0.865, mrr: float = 0.705) -> dict:
    """The Shipped Arm's result as evaluate_arm returns it: one row per answerable case."""
    return {
        "arm": shipped_arm_id(),
        "summary": {"recall@5": 0.6, "hit@5": hit, "mrr": mrr, "ndcg@5": 0.6},
        "cases": [{"id": f"case-{i}"} for i in range(n)],
    }


class TestRecalibrateCommand:
    def test_writes_the_worked_example_into_the_record(self, tmp_path):
        path = tmp_path / "retrieval.json"
        recalibrate_retrieval(_measured_run(), CASES, path, commit="abc1234")

        record = read_record(path)
        assert record["floors"] == {"hit@5": 0.845, "mrr": 0.685}
        assert record["inputs"] == {"n": 111, "measured": {"hit@5": 0.865, "mrr": 0.705}}
        assert record["rule"] == RETRIEVAL_RULE
        assert record["arm"] == shipped_arm_id()
        assert record["fingerprint"] == retrieval_fingerprint(CASES)
        assert record["commit"] == "abc1234"

    def test_n_is_the_cases_the_metric_was_averaged_over(self, tmp_path):
        """Out-of-Scope Cases are never scored for retrieval, so they never count in n."""
        path = tmp_path / "retrieval.json"
        recalibrate_retrieval(_measured_run(n=50, hit=0.92, mrr=0.92), CASES, path, "abc1234")
        assert read_record(path)["floors"] == {"hit@5": 0.88, "mrr": 0.88}

    def test_refuses_a_run_of_any_arm_but_the_shipped_one(self, tmp_path):
        """Only the Shipped Arm has Floors (ADR-0004)."""
        run = {**_measured_run(), "arm": "dense"}
        with pytest.raises(ValueError, match="Shipped Arm"):
            recalibrate_retrieval(run, CASES, tmp_path / "retrieval.json", "abc1234")


class TestCommittedRetrievalRecord:
    """The committed record against the committed Golden Set: free, and before any eval job.

    A Golden Set edit made without a Recalibration fails here, on the PR that made it
    (story 87), rather than in the eval gate or weeks later on `main`.
    """

    @pytest.fixture
    def record(self) -> dict:
        return read_record(RETRIEVAL_FLOORS_PATH)

    def test_matches_the_committed_golden_set(self, record):
        golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        assert record["fingerprint"] == retrieval_fingerprint(golden["cases"]), (
            "Floors stale: Recalibrate. The Golden Set changed without a Recalibration: "
            "run `uv run --frozen python eval/recalibrate.py retrieval` in this change "
            "(ADR-0012)."
        )

    def test_its_floors_are_its_rule_applied_to_its_inputs(self, record):
        """A Floor edited by hand no longer follows from the inputs beside it."""
        n = record["inputs"]["n"]
        measured = record["inputs"]["measured"]
        assert record["floors"] == {m: retrieval_floor(v, n) for m, v in measured.items()}
        assert record["rule"] == RETRIEVAL_RULE

    def test_floors_every_gated_metric(self, record):
        assert set(record["floors"]) == set(GATED_METRICS)

    def test_n_is_the_answerable_cases_of_the_full_golden_set(self, record):
        golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        assert record["inputs"]["n"] == len(answerable_cases(golden["cases"]))

    def test_only_the_recalibrate_command_writes_it(self):
        """Nothing else may write a Floors record (story 85)."""
        backend = Path(__file__).resolve().parent.parent
        writers = {
            path.relative_to(backend).as_posix()
            for path in [*backend.glob("eval/*.py"), *backend.rglob("app/**/*.py")]
            if "write_record(" in path.read_text(encoding="utf-8")
        }
        assert writers == {"eval/recalibrate.py", "eval/recalibration.py"}
