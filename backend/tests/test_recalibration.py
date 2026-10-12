"""Tests for Recalibration: the Floors record, its fingerprint and its fixed rule (ADR-0012).

A Floor is derived from a measurement by a fixed rule and written by the recalibrate
command alone. These check that each gate's rule reproduces its worked example, that each
fingerprint follows exactly the case fields (and, for generation, the instrument) its
Floors depend on, and that the committed records still describe what they gate.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval import gate_generation
from eval.publish import shipped_arm_id
from eval.recalibrate import recalibrate_generation, recalibrate_retrieval
from eval.recalibration import (
    GENERATION_FLOORS_PATH,
    GENERATION_RULE,
    RETRIEVAL_FLOORS_PATH,
    RETRIEVAL_RULE,
    assert_generation_record_current,
    generation_fingerprint,
    generation_instrument,
    read_record,
    retrieval_fingerprint,
    retrieval_floor,
)
from eval.run_eval import GATED_METRICS, GOLDEN_SET_PATH, answerable_cases
from eval.variance import GATED, PUBLISHED, step_size
from eval.variance import floor as variance_floor


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


# ---------------------------------------------------------------------------
# The generation gate
# ---------------------------------------------------------------------------

INSTRUMENT = {
    "judge": "jev-1.13.0",
    "judgeQuestions": {"declines": {"type": "noul", "instructions": "Does `answer` decline?"}},
    "splitter": "gpt-6-luna",
    "splitterReasoningEffort": "low",
    "factualBelow": 0.2,
    "generationModel": "gpt-6-luna",
    "reasoningEffort": "low",
}


class TestGenerationFingerprint:
    def test_is_stable_when_cases_are_reordered(self):
        assert generation_fingerprint(CASES, INSTRUMENT) == generation_fingerprint(
            list(reversed(CASES)), INSTRUMENT
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("question", "What else about alpha?"),
            ("required_facts", ["David did something else entirely."]),
            ("answerable", False),
        ],
    )
    def test_changes_when_a_field_generation_reads_changes(self, field, value):
        edited = copy.deepcopy(CASES)
        edited[0][field] = value
        assert generation_fingerprint(edited, INSTRUMENT) != generation_fingerprint(
            CASES, INSTRUMENT
        )

    @pytest.mark.parametrize(
        ("part", "value"),
        [
            ("judge", "jev-1.14.0"),
            ("judgeQuestions", {"declines": {"type": "noul", "instructions": "Reworded?"}}),
            ("splitter", "gpt-6.1-sol"),
            ("splitterReasoningEffort", "medium"),
            ("factualBelow", 0.3),
            ("generationModel", "gpt-6.1-sol"),
            ("reasoningEffort", "medium"),
        ],
    )
    def test_changes_when_the_instrument_changes(self, part, value):
        assert generation_fingerprint(CASES, {**INSTRUMENT, part: value}) != (
            generation_fingerprint(CASES, INSTRUMENT)
        )

    def test_a_required_fact_edit_stales_only_the_generation_floors(self):
        """Story 88: a Required Fact edit never stales the retrieval Floors."""
        edited = copy.deepcopy(CASES)
        edited[0]["required_facts"] = ["David did something else entirely."]

        assert generation_fingerprint(edited, INSTRUMENT) != (
            generation_fingerprint(CASES, INSTRUMENT)
        )
        assert retrieval_fingerprint(edited) == retrieval_fingerprint(CASES)

    def test_a_judge_question_change_stales_only_the_generation_floors(self, monkeypatch):
        """Rewording a Judge question in eval/judge.py is a new instrument for generation,
        and none at all for retrieval."""
        from eval import judge

        before = generation_fingerprint(CASES, generation_instrument())
        monkeypatch.setitem(judge.DECLINES_QUESTION, "instructions", "Is this a refusal?")

        assert generation_fingerprint(CASES, generation_instrument()) != before
        assert retrieval_fingerprint(CASES) == retrieval_fingerprint(copy.deepcopy(CASES))

    @pytest.mark.parametrize(
        ("module", "name", "value"),
        [
            ("eval.splitter", "SPLITTER_REASONING_EFFORT", "medium"),
            ("eval.judge", "FACTUAL_BELOW", 0.3),
        ],
    )
    def test_a_change_to_what_counts_as_a_claim_stales_the_generation_floors(
        self, monkeypatch, module, name, value
    ):
        """Owner decision, 2026-10-11 (#91): the splitter's reasoning effort and the
        Judge's filler cutoff change which sentences count and what claims get judged, so
        either is a new instrument."""
        import importlib

        before = generation_fingerprint(CASES, generation_instrument())
        monkeypatch.setattr(importlib.import_module(module), name, value)

        assert generation_fingerprint(CASES, generation_instrument()) != before

    def test_a_relevant_phrase_edit_stales_only_the_retrieval_floors(self):
        """Story 88: a free retrieval label repair never forces a paid generation study."""
        edited = copy.deepcopy(CASES)
        edited[0]["relevant_phrases"] = ["alpha phrase", "another phrase"]

        assert retrieval_fingerprint(edited) != retrieval_fingerprint(CASES)
        assert generation_fingerprint(edited, INSTRUMENT) == (
            generation_fingerprint(CASES, INSTRUMENT)
        )

    def test_the_current_instrument_is_the_one_the_gate_measures_with(self):
        from eval.judge import DECLINES_QUESTION, FACTUAL_BELOW, JEV_MODEL
        from eval.run_generation import OPENAI_MODEL, OPENAI_REASONING_EFFORT
        from eval.splitter import SPLITTER_MODEL, SPLITTER_REASONING_EFFORT

        instrument = generation_instrument()

        assert instrument["judge"] == JEV_MODEL
        assert instrument["judgeQuestions"]["declines"] == DECLINES_QUESTION
        assert set(instrument["judgeQuestions"]) == {"supports", "factual", "conveys", "declines"}
        assert instrument["splitter"] == SPLITTER_MODEL
        assert instrument["splitterReasoningEffort"] == SPLITTER_REASONING_EFFORT
        assert instrument["factualBelow"] == FACTUAL_BELOW
        assert instrument["generationModel"] == OPENAI_MODEL
        assert instrument["reasoningEffort"] == OPENAI_REASONING_EFFORT


def judged_case(case_id, split, *, supported=None, conveyed=None, declined=False):
    """One judged case: an answerable one with one factual sentence and one Required Fact,
    or, when `supported` is None, an Out-of-Scope Case that was or wasn't declined."""
    if supported is None:
        return {
            "id": case_id,
            "split": split,
            "answerable": False,
            "declined": declined,
            "sentences": [],
            "facts": [],
            "contradictions": [],
        }
    return {
        "id": case_id,
        "split": split,
        "answerable": True,
        "declined": False,
        "sentences": [{"supported": supported}],
        "facts": [{"fact": "f", "conveyed": bool(conveyed)}],
        "contradictions": [],
    }


def judged_run(holdout_supported, dev_supported, out_of_scope_declined, holdout_conveyed):
    """A judged run of 50 cases: 20 held-out and 20 dev answerable, 10 dev Out-of-Scope.

    Each argument is how many of that group came out right, so a run is its counts.
    """
    holdout = [
        judged_case(
            f"h{i}", "holdout", supported=i < holdout_supported, conveyed=i < holdout_conveyed
        )
        for i in range(20)
    ]
    dev = [
        judged_case(f"d{i}", "dev", supported=i < dev_supported, conveyed=True) for i in range(20)
    ]
    out = [judged_case(f"o{i}", "dev", declined=i < out_of_scope_declined) for i in range(10)]
    return {"commit": "j1", "record": {"commit": "g1"}, "cases": holdout + dev + out}


#: The worked example: five fake judged runs and what the rule makes of them.
#:
#:   Held-out Faithfulness 0.95 0.90 0.95 0.95 0.90 → range 0.05 → step 0.05
#:   Held-out Fact Recall  0.80 0.70 0.85 0.75 0.80 → range 0.15 → step 0.1
#:   Held-out Decline accuracy 1.0 every run         → range 0    → step 0.005
#:   Faithfulness, all cases 38 37 37 38 37 of 40     → lowest 0.925, range 0.025
#:     0.925 − max(2 × 0.025, 0.05) = 0.875 → Floor 0.85
#:   Decline accuracy, all cases 50 49 50 50 48 of 50 → lowest 0.96, range 0.04
#:     0.96 − max(2 × 0.04, 0.005) = 0.88 → Floor 0.88
FIVE_RUNS = [
    judged_run(19, 19, 10, 16),
    judged_run(18, 19, 9, 14),
    judged_run(19, 18, 10, 17),
    judged_run(19, 19, 10, 15),
    judged_run(18, 19, 8, 16),
]
FIVE_RUN_CASES = [
    _case(case["id"], split=case["split"], answerable=case["answerable"])
    for case in FIVE_RUNS[0]["cases"]
]


class TestGenerationRecalibrateCommand:
    def test_reproduces_the_worked_example_from_five_judged_runs(self, tmp_path):
        path = tmp_path / "generation.json"
        recalibrate_generation(FIVE_RUNS, FIVE_RUN_CASES, path, "abc1234", INSTRUMENT)

        record = read_record(path)
        assert record["steps"] == {
            "factRecall": 0.1,
            "faithfulness": 0.05,
            "declineAccuracy": 0.005,
        }
        assert record["floors"] == {"faithfulness": 0.85, "declineAccuracy": 0.88}
        assert record["inputs"]["all"]["faithfulness"] == {
            "values": [0.95, 0.925, 0.925, 0.95, 0.925],
            "range": 0.025,
        }
        assert record["inputs"]["all"]["declineAccuracy"] == {
            "values": [1.0, 0.98, 1.0, 1.0, 0.96],
            "range": 0.04,
        }
        assert record["inputs"]["holdout"]["factRecall"] == {
            "values": [0.8, 0.7, 0.85, 0.75, 0.8],
            "range": 0.15,
        }
        assert record["inputs"]["runs"] == [{"generated": "g1", "judged": "j1"}] * 5
        assert record["rule"] == GENERATION_RULE
        assert record["arm"] == shipped_arm_id()
        assert record["fingerprint"] == generation_fingerprint(FIVE_RUN_CASES, INSTRUMENT)
        assert record["commit"] == "abc1234"

    @pytest.mark.parametrize("count", [3, 4, 6])
    def test_is_built_for_five_runs(self, tmp_path, count):
        """Three runs understated the noise (story 90)."""
        runs = (FIVE_RUNS * 2)[:count]
        with pytest.raises(ValueError, match="five"):
            recalibrate_generation(runs, FIVE_RUN_CASES, tmp_path / "g.json", "abc", INSTRUMENT)

    def test_refuses_runs_that_do_not_cover_the_golden_set(self, tmp_path):
        """The fingerprint would vouch for cases the Floors were never measured on."""
        cases = [*FIVE_RUN_CASES, _case("new-case")]
        with pytest.raises(ValueError, match="new-case"):
            recalibrate_generation(FIVE_RUNS, cases, tmp_path / "g.json", "abc", INSTRUMENT)


def _generation_record(**overrides) -> dict:
    record = {
        "floors": {"faithfulness": 0.85, "declineAccuracy": 0.915},
        "fingerprint": generation_fingerprint(CASES, INSTRUMENT),
    }
    return {**record, **overrides}


class TestGenerationGate:
    def test_a_stale_record_fails_first_and_measures_nothing(self):
        """Nothing is paid for: the run would be compared with Floors from another set."""
        measured = []
        stale = _generation_record(fingerprint="sha256:from-another-golden-set")

        failures, run = gate_generation.gate(
            stale, CASES, INSTRUMENT, lambda: measured.append(1) or {"metrics": {}}
        )

        assert measured == []
        assert run is None
        assert len(failures) == 1
        assert failures[0].startswith("Floors stale: Recalibrate")

    def test_a_record_that_predates_fingerprints_is_stale(self):
        failures, _ = gate_generation.gate(
            _generation_record(fingerprint=None), CASES, INSTRUMENT, dict
        )
        assert failures[0].startswith("Floors stale: Recalibrate")

    def test_a_current_record_passes_a_run_above_its_floors(self):
        run = {"metrics": {"faithfulness": 0.9, "declineAccuracy": 0.95}}

        failures, measured = gate_generation.gate(
            _generation_record(), CASES, INSTRUMENT, lambda: run
        )

        assert failures == []
        assert measured is run

    def test_a_current_record_fails_a_run_below_its_floors(self):
        """The Floors compared are the record's, not constants in code."""
        run = {"metrics": {"faithfulness": 0.9, "declineAccuracy": 0.95}}
        record = _generation_record(floors={"faithfulness": 0.95, "declineAccuracy": 0.9})

        failures, _ = gate_generation.gate(record, CASES, INSTRUMENT, lambda: run)

        assert failures == ["faithfulness = 0.900 < 0.950"]


class TestCommittedGenerationRecord:
    """The committed generation record against the committed Golden Set and instrument."""

    @pytest.fixture
    def record(self) -> dict:
        return read_record(GENERATION_FLOORS_PATH)

    def test_a_stale_record_fails_the_ordinary_suite(self):
        """The check the committed record faces, on a record from another Golden Set."""
        golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        with pytest.raises(AssertionError, match="Floors stale: Recalibrate"):
            assert_generation_record_current(
                _generation_record(fingerprint="sha256:old"), golden["cases"]
            )

    def test_matches_the_committed_golden_set_and_instrument(self, record):
        golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        assert_generation_record_current(record, golden["cases"])

    def test_its_floors_and_steps_are_its_rule_applied_to_its_inputs(self, record):
        """A Floor or step edited by hand no longer follows from the inputs beside it."""
        inputs = record["inputs"]
        assert record["steps"] == {
            metric: step_size(spread["range"]) for metric, spread in inputs["holdout"].items()
        }
        assert record["floors"] == {
            metric: variance_floor(spread["values"], spread["range"], record["steps"][metric])
            for metric, spread in inputs["all"].items()
        }

    def test_floors_every_gated_metric_and_steps_every_published_one(self, record):
        assert set(record["floors"]) == set(GATED)
        assert set(record["steps"]) == set(PUBLISHED)

    def test_the_publisher_rounds_to_its_steps(self, record):
        from eval.publish_generation import steps

        assert steps() == record["steps"]
