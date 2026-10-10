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
    VALID_CATEGORIES,
    answerable_cases,
    check_thresholds,
    describe_cases,
    evaluate_arm,
    is_relevant,
    overbroad_phrases,
    retrievers_for_arms,
    select_cases,
)

from eval.publish import ARMS, shipped_arm_id

GOLDEN = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
CASES = GOLDEN["cases"]
ANSWERABLE = answerable_cases(CASES)


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

    def test_unknown_split_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown split"):
            select_cases(CASES, "test")

    def test_founding_55_splits_remain_frozen(self):
        direct_cases = [c for c in CASES if c.get("category") == "direct"]
        dev_count = len([c for c in direct_cases if c["split"] == "dev"])
        holdout_count = len([c for c in direct_cases if c["split"] == "holdout"])
        assert dev_count == 33
        assert holdout_count == 22


# ---------------------------------------------------------------------------
# Query categories
# ---------------------------------------------------------------------------


class TestCategories:
    def test_all_founding_cases_are_direct(self):
        direct_cases = [c for c in CASES if c.get("category") == "direct"]
        assert len(direct_cases) == 55

    def test_paraphrase_batch_is_present(self):
        paraphrase_cases = [c for c in CASES if c.get("category") == "paraphrase"]
        assert 15 <= len(paraphrase_cases) <= 20

    def test_conceptual_batch_is_present(self):
        conceptual_cases = [c for c in CASES if c.get("category") == "conceptual"]
        assert 15 <= len(conceptual_cases) <= 20

    def test_categories_have_balanced_representation(self):
        direct = [c for c in CASES if c.get("category") == "direct"]
        paraphrase = [c for c in CASES if c.get("category") == "paraphrase"]
        conceptual = [c for c in CASES if c.get("category") == "conceptual"]

        assert len(direct) == 55
        assert 15 <= len(paraphrase) <= 20
        assert 15 <= len(conceptual) <= 20
        assert len(ANSWERABLE) == len(direct) + len(paraphrase) + len(conceptual)

    def test_every_answerable_case_has_a_valid_category(self):
        for case in ANSWERABLE:
            assert case.get("category") in VALID_CATEGORIES

    def test_every_answerable_case_relevant_phrases_match_at_least_one_chunk(self):
        from run_eval import relevant_ids

        from app.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        for case in ANSWERABLE:
            matched = relevant_ids(pipeline.chunks, case["relevant_phrases"])
            assert len(matched) > 0, f"Case {case['id']} matches no chunks in corpus"

    def test_an_unlabelled_case_category_is_an_error(self):
        with pytest.raises(ValueError, match="no valid category"):
            select_cases(
                [{"id": "orphan", "split": "dev", "question": "?", "relevant_phrases": []}],
                "all",
            )

    def test_an_invalid_category_is_rejected(self):
        with pytest.raises(ValueError, match="no valid category"):
            select_cases(
                [
                    {
                        "id": "bad",
                        "split": "dev",
                        "category": "unknown",
                        "question": "?",
                        "relevant_phrases": [],
                    }
                ],
                "all",
            )


# ---------------------------------------------------------------------------
# Relevance matching
# ---------------------------------------------------------------------------


class TestWordStartMatching:
    """A Relevant Phrase matches only where it begins a word. A raw substring match let
    `no` mark 63 of 120 chunks relevant, which made the case a free hit for every arm."""

    def test_a_phrase_does_not_match_inside_a_word(self):
        assert not is_relevant("I know some technology.", ["no"])

    def test_a_phrase_matches_as_a_word_of_its_own(self):
        assert is_relevant("There is no TACOM owned data package.", ["no"])

    def test_a_punctuated_phrase_does_not_match_inside_a_longer_label(self):
        assert not is_relevant("SKILLS ACQUIRED FROM ENGINEER: Python", ["R:"])
        assert is_relevant("R: tidyverse, Shiny", ["R:"])

    def test_a_phrase_still_matches_when_the_chunk_extends_its_last_word(self):
        assert is_relevant("He enjoys mentoring junior engineers.", ["mentor"])
        assert is_relevant("Rate limiting protects the endpoint.", ["rate limit"])

    def test_a_word_start_may_follow_punctuation(self):
        assert is_relevant(
            "time series data (Prognostic and Predictive Maintenance).", ["Predictive Maintenance"]
        )


def _corpus(n_matching: int, size: int = 20) -> list[dict]:
    """A corpus of `size` chunks, the first `n_matching` of which mention FastAPI."""
    return [
        {"text": "Built with FastAPI." if i < n_matching else f"Unrelated chunk {i}."}
        for i in range(size)
    ]


def _case(*phrases: str) -> dict:
    return {"id": "c", "relevant_phrases": list(phrases)}


class TestBreadthLint:
    """A phrase that marks a large share of the Corpus relevant is a labelling defect, not
    a label: it hands every arm a hit regardless of what it retrieved."""

    def test_flags_a_phrase_matching_more_than_the_maximum_share(self):
        flagged = overbroad_phrases(_corpus(4), [_case("FastAPI")], allowed=[])
        assert [f["phrase"] for f in flagged] == ["FastAPI"]

    def test_a_phrase_at_the_maximum_share_passes(self):
        assert overbroad_phrases(_corpus(3), [_case("FastAPI")], allowed=[]) == []

    def test_an_allow_listed_phrase_is_not_flagged(self):
        assert overbroad_phrases(_corpus(20), [_case("FastAPI")], allowed=["fastapi"]) == []

    def test_the_committed_golden_set_has_no_overbroad_phrase(self):
        """The lint over the real labels and the real Corpus. A failure here means a label
        is broad enough to make its case a free hit: narrow the phrase to what the question
        and Corpus text justify, or, if it is broad but correct, allow-list it in
        golden_set.json with the reason."""
        from app.rag.pipeline import RAGPipeline

        chunks = RAGPipeline().chunks
        allowed = list(GOLDEN["breadthAllowList"]["phrases"])
        assert overbroad_phrases(chunks, CASES, allowed) == []


# ---------------------------------------------------------------------------
# Evaluation per-category
# ---------------------------------------------------------------------------


class TestEvaluateArm:
    def test_evaluate_arm_calculates_per_category_metrics(self):
        pipeline = MagicMock()
        pipeline.chunks = [
            {"text": "direct hit"},
            {"text": "paraphrase target"},
        ]

        # retriever returns chunk 0 for question "q1" (hit for direct),
        # chunk 0 for question "q2" (miss for paraphrase where relevant is chunk 1)
        def mock_sparse(query, top_k=5):
            return [0]

        pipeline.sparse_search.side_effect = mock_sparse

        test_cases = [
            {
                "id": "c1",
                "split": "dev",
                "category": "direct",
                "question": "q1",
                "relevant_phrases": ["direct hit"],
            },
            {
                "id": "c2",
                "split": "dev",
                "category": "paraphrase",
                "question": "q2",
                "relevant_phrases": ["paraphrase target"],
            },
        ]

        result = evaluate_arm(pipeline, "bm25", test_cases, top_k=5)

        assert "by_category" in result
        assert "direct" in result["by_category"]
        assert "paraphrase" in result["by_category"]

        # direct: hit@5 = 1.0, mrr = 1.0
        assert result["by_category"]["direct"]["hit@5"] == 1.0
        assert result["by_category"]["direct"]["mrr"] == 1.0

        # paraphrase: hit@5 = 0.0, mrr = 0.0
        assert result["by_category"]["paraphrase"]["hit@5"] == 0.0
        assert result["by_category"]["paraphrase"]["mrr"] == 0.0

        # aggregate summary: hit@5 = 0.5, mrr = 0.5
        assert result["summary"]["hit@5"] == 0.5
        assert result["summary"]["mrr"] == 0.5

        # individual case records preserve category
        assert [c["category"] for c in result["cases"]] == ["direct", "paraphrase"]


# ---------------------------------------------------------------------------
# Out-of-Scope Cases
# ---------------------------------------------------------------------------


def _answerable(case_id: str, *phrases: str) -> dict:
    return {
        "id": case_id,
        "split": "dev",
        "category": "direct",
        "question": f"question {case_id}",
        "relevant_phrases": list(phrases),
        "required_facts": [f"David knows about {case_id}."],
    }


def _out_of_scope(case_id: str) -> dict:
    return {
        "id": case_id,
        "split": "dev",
        "answerable": False,
        "question": f"question {case_id}",
    }


class TestOutOfScopeCases:
    """A question the Corpus cannot answer has nothing for retrieval to find. It is left
    out of retrieval scoring on purpose, by its own label — not by the "matches no chunk"
    error, which must stay loud for a broken label on an answerable case."""

    def _pipeline(self) -> MagicMock:
        pipeline = MagicMock()
        pipeline.chunks = [{"text": "Booz Allen Hamilton"}, {"text": "FastAPI backend"}]
        pipeline.sparse_search.return_value = [0]
        return pipeline

    def test_an_out_of_scope_case_is_not_scored_for_retrieval(self):
        pipeline = self._pipeline()
        cases = [_answerable("employer", "Booz Allen Hamilton"), _out_of_scope("salary")]

        result = evaluate_arm(pipeline, "bm25", cases, top_k=5)

        assert [c["id"] for c in result["cases"]] == ["employer"]
        assert result["summary"]["hit@5"] == 1.0
        pipeline.sparse_search.assert_called_once_with("question employer", top_k=5)

    def test_a_broken_label_on_an_answerable_case_still_fails_loudly(self):
        cases = [_out_of_scope("salary"), _answerable("typo", "Booz Alen Hamilton")]

        with pytest.raises(ValueError, match="'typo' matches no chunk"):
            evaluate_arm(self._pipeline(), "bm25", cases, top_k=5)

    def test_the_run_summary_counts_out_of_scope_cases_separately(self):
        """Skipped on purpose is still visible: the summary says how many were skipped."""
        cases = [_answerable("a", "x"), _answerable("b", "y"), _out_of_scope("salary")]
        assert describe_cases(cases) == "2 answerable + 1 out-of-scope"

    def test_the_committed_golden_set_has_out_of_scope_cases_in_both_splits(self):
        """Decline accuracy needs questions to decline. They share the Split rule (checked
        against the recorded labels above), so some land in each portion."""
        out_of_scope = [c for c in CASES if c.get("answerable") is False]
        assert 18 <= len(out_of_scope) <= 22
        assert {c["split"] for c in out_of_scope} == {"dev", "holdout"}
        select_cases(CASES, "all")  # every case, of both kinds, is well-formed


class TestGoldenCaseValidation:
    """`select_cases` is where a malformed case is caught, before any arm runs."""

    def test_accepts_the_generation_fields_on_both_kinds_of_case(self):
        answerable = {
            **_answerable("employer", "Booz Allen Hamilton"),
            "answerable": True,
            "required_facts": ["David works at Booz Allen Hamilton."],
            "origin": "visitor",
        }
        out_of_scope = {**_out_of_scope("salary"), "origin": "authored"}

        assert select_cases([answerable, out_of_scope], "all") == [answerable, out_of_scope]

    def test_an_out_of_scope_case_needs_no_query_category(self):
        """A Query Category describes how a question's phrasing relates to the Corpus;
        a question the Corpus cannot answer has no such relationship to describe."""
        assert select_cases([_out_of_scope("salary")], "dev") == [_out_of_scope("salary")]

    def test_rejects_an_answerable_case_with_no_relevant_phrases(self):
        """Forgetting `answerable: false` must not turn a case into a silent skip, and
        forgetting its phrases must not turn it into an Out-of-Scope Case."""
        with pytest.raises(ValueError, match="no Relevant Phrases: forgot"):
            select_cases([_answerable("forgot")], "all")

    @pytest.mark.parametrize("facts", [{"required_facts": []}, {"required_facts": None}])
    def test_rejects_an_answerable_case_with_no_required_facts(self, facts):
        """Fact Recall is the share of a case's Required Facts an answer conveys, so an
        answerable case with none could never be scored and would drop out silently."""
        with pytest.raises(ValueError, match="no Required Facts: forgot"):
            select_cases([{**_answerable("forgot", "Booz Allen Hamilton"), **facts}], "all")

    def test_rejects_an_answerable_case_missing_the_required_facts_field(self):
        case = _answerable("forgot", "Booz Allen Hamilton")
        del case["required_facts"]
        with pytest.raises(ValueError, match="no Required Facts: forgot"):
            select_cases([case], "all")

    @pytest.mark.parametrize(
        "field", [{"relevant_phrases": ["salary"]}, {"required_facts": ["David earns X."]}]
    )
    def test_rejects_an_out_of_scope_case_that_carries_labels(self, field):
        """Labels on a question the Corpus cannot answer contradict the case itself."""
        with pytest.raises(ValueError, match="Out-of-Scope cases carry labels: salary"):
            select_cases([{**_out_of_scope("salary"), **field}], "all")

    def test_every_committed_required_fact_is_a_self_contained_sentence(self):
        """A Required Fact is judged on its own, beside an answer, with no question in
        view: one that opens on "He" or "It" leaves the Judge guessing who or what it
        is about."""
        leaning_on_context = {"he", "she", "it", "they", "this", "that", "these", "those"}
        malformed = [
            (case["id"], fact)
            for case in ANSWERABLE
            for fact in case["required_facts"]
            if not (
                fact[:1].isupper()
                and fact.endswith(".")
                and fact.split()[0].lower() not in leaning_on_context
            )
        ]
        assert not malformed

    def test_rejects_an_unknown_case_origin(self):
        """Visitor-origin results are reported separately, so a misspelt origin would
        quietly move a case out of that report."""
        with pytest.raises(ValueError, match="no valid origin: typo"):
            select_cases([{**_out_of_scope("typo"), "origin": "vistor"}], "all")
