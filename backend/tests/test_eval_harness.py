"""Tests for the evaluation harness's two moving parts: which arms exist, and which
golden questions a run is allowed to look at.

Neither needs a pipeline or any model weights. Both are places where a mistake is
silent rather than loud — an arm implemented but never published, a question that
drifts out of the held-out portion — so they are checked here rather than noticed on
a public page.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from run_eval import (
    GATED_SPLIT,
    GOLDEN_SET_PATH,
    PUBLISHED_SPLIT,
    THRESHOLDS,
    check_thresholds,
    retrievers_for_arms,
    select_cases,
)

from eval.publish import ARMS, shipped_arm_id

GOLDEN = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
CASES = GOLDEN["cases"]


def _drawn_into_holdout(case_id: str) -> bool:
    """The documented split rule, recomputed from golden_set.json's own record of it."""
    salt = GOLDEN["splits"]["salt"]
    digest = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()
    return digest < GOLDEN["splits"]["holdoutBelow"]


# ---------------------------------------------------------------------------
# Arms
# ---------------------------------------------------------------------------


class TestArmRegistry:
    def test_every_published_arm_has_a_retriever(self):
        """The failure this prevents: an arm described on the public page that the
        harness cannot run, which surfaces only when someone selects it."""
        assert set(retrievers_for_arms(MagicMock(), top_k=5)) == set(ARMS)

    def test_bm25_rerank_skips_the_dense_stage_entirely(self):
        """The arm that decided #23. If it ever routes through hybrid_search it is
        measuring the thing it exists to be the control for."""
        pipeline = MagicMock()
        pipeline.sparse_search.return_value = [3, 1, 2]
        pipeline.rerank.return_value = [1, 3]

        assert retrievers_for_arms(pipeline, top_k=5)["bm25+rerank"]("q") == [1, 3]
        pipeline.sparse_search.assert_called_once_with("q", top_k=10)
        pipeline.dense_search.assert_not_called()
        pipeline.hybrid_search.assert_not_called()

    def test_reranking_arms_hand_the_cross_encoder_twice_the_cutoff(self):
        """Re-ranking five candidates into five slots can only reorder, never rescue, so
        a re-ranking arm has to be handed more candidates than it returns."""
        pipeline = MagicMock()
        retrievers_for_arms(pipeline, top_k=5)["rerank"]("q")
        pipeline.hybrid_search.assert_called_once_with("q", top_k=10)


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def _result(arm: str, hit: float = 0.99, mrr: float = 0.99) -> dict:
    return {"arm": arm, "summary": {"hit@5": hit, "mrr": mrr}}


class TestGate:
    def test_gates_the_shipped_arm(self):
        assert set(THRESHOLDS) == {shipped_arm_id()}

    def test_passes_when_the_shipped_arm_clears_its_floors(self, capsys):
        assert check_thresholds([_result(shipped_arm_id())], top_k=5) == 0

    def test_fails_when_the_shipped_arm_drops(self, capsys):
        assert check_thresholds([_result(shipped_arm_id(), hit=0.1)], top_k=5) == 1
        assert "below threshold" in capsys.readouterr().out

    def test_a_run_that_gates_nothing_fails(self, capsys):
        """An ungated arm on its own is not a passing build; it is no build at all."""
        assert check_thresholds([_result("dense")], top_k=5) == 1
        out = capsys.readouterr().out
        assert "NOT GATED" in out and "gated nothing" in out

    def test_refuses_to_gate_a_single_split(self, capsys):
        """Floors are calibrated on the whole set. A split is a smaller sample against
        the same absolute numbers, which fails on noise or passes by luck."""
        assert check_thresholds([_result(shipped_arm_id())], top_k=5, split="holdout") == 1
        assert f"calibrated on the {GATED_SPLIT} golden set" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Golden-set splits
# ---------------------------------------------------------------------------


class TestSplits:
    def test_dev_and_holdout_partition_the_set(self):
        dev = select_cases(CASES, "dev")
        holdout = select_cases(CASES, "holdout")
        assert len(dev) + len(holdout) == len(CASES) == len(select_cases(CASES, "all"))
        assert not {c["id"] for c in dev} & {c["id"] for c in holdout}

    def test_the_published_split_is_not_the_split_decisions_are_made_on(self):
        """The entire point. If these were ever the same string, every published number
        would be the score of a configuration chosen against those same questions."""
        assert PUBLISHED_SPLIT != "dev"
        assert PUBLISHED_SPLIT != GATED_SPLIT

    def test_the_recorded_split_matches_the_documented_rule(self):
        """The split is frozen in the file so it survives edits to the questions — which
        also means a hand-edit would go unnoticed. Recomputing the published rule catches
        an inconvenient question quietly moved across the line.
        """
        assert {c["id"] for c in CASES if c["split"] == "holdout"} == {
            c["id"] for c in CASES if _drawn_into_holdout(c["id"])
        }

    def test_the_rule_cannot_move_a_case_when_the_set_grows(self):
        """Why the boundary is a hash threshold and not "the first 40% by rank".

        A rank-based cutoff moves with the size of the set, so adding one question
        reshuffles cases across the boundary — and the test above would then demand that
        the frozen labels be rewritten to match, quietly moving held-out questions into
        `dev`. That is the leak the split exists to prevent, arriving through the check
        meant to protect it. This rule reads one id at a time, so a case's split is
        decided by its own id and nothing else.
        """
        before = {c["id"]: _drawn_into_holdout(c["id"]) for c in CASES}

        grown = CASES + [{"id": f"hypothetical-question-{i}"} for i in range(40)]
        after = {c["id"]: _drawn_into_holdout(c["id"]) for c in grown}

        assert all(after[case_id] == was_held for case_id, was_held in before.items())

    def test_an_unlabelled_case_is_an_error_not_a_silent_exclusion(self):
        with pytest.raises(ValueError, match="no valid split"):
            select_cases([{"id": "orphan", "question": "?", "relevant_phrases": []}], "all")

    def test_an_unknown_split_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown split"):
            select_cases(CASES, "test")
