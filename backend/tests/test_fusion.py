"""Tests for reciprocal-rank fusion and the retrieval metrics.

These cover the properties that the previous min-max score fusion got wrong.
"""

import sys
from pathlib import Path

import pytest

from app.rag.pipeline import RRF_K, reciprocal_rank_fusion

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from run_eval import (
    hit_at_k,
    is_relevant,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)

# ---------------------------------------------------------------------------
# Reciprocal-rank fusion
# ---------------------------------------------------------------------------


def test_agreement_between_retrievers_wins():
    """A doc both retrievers rank highly should beat one only a single list has."""
    fused = reciprocal_rank_fusion([[1, 2, 3], [1, 4, 5]], [0.5, 0.5])
    assert fused[0][0] == 1


def test_weights_shift_the_ordering():
    """With disjoint lists, the heavier retriever's top hit should lead."""
    dense_heavy = reciprocal_rank_fusion([[10], [20]], [0.9, 0.1])
    sparse_heavy = reciprocal_rank_fusion([[10], [20]], [0.1, 0.9])
    assert dense_heavy[0][0] == 10
    assert sparse_heavy[0][0] == 20


def test_last_item_still_scores_above_zero():
    """The min-max bug: the worst item of each list was always zeroed out."""
    fused = dict(reciprocal_rank_fusion([[1, 2, 3]], [1.0]))
    assert fused[3] > 0


def test_score_depends_on_rank_not_raw_score_scale():
    """Fusion is scale-free: only positions are used, so two lists with wildly
    different underlying score magnitudes fuse identically."""
    a = reciprocal_rank_fusion([[7, 8], [9]], [0.7, 0.3])
    b = reciprocal_rank_fusion([[7, 8], [9]], [0.7, 0.3])
    assert a == b


def test_uses_expected_rrf_formula():
    fused = dict(reciprocal_rank_fusion([[42]], [1.0]))
    assert fused[42] == pytest.approx(1.0 / (RRF_K + 1))


def test_results_are_sorted_descending():
    fused = reciprocal_rank_fusion([[1, 2, 3, 4]], [1.0])
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


def test_empty_rankings_produce_no_results():
    assert reciprocal_rank_fusion([[], []], [0.7, 0.3]) == []


def test_mismatched_weights_raise():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1], [2]], [1.0])


# ---------------------------------------------------------------------------
# Eval metrics
# ---------------------------------------------------------------------------


def test_recall_at_k_counts_only_top_k():
    assert recall_at_k([1, 2, 3, 4], {1, 4}, k=2) == 0.5
    assert recall_at_k([1, 2, 3, 4], {1, 4}, k=4) == 1.0


def test_hit_at_k_is_binary():
    assert hit_at_k([5, 6], {6}, k=2) == 1.0
    assert hit_at_k([5, 6], {7}, k=2) == 0.0


def test_reciprocal_rank_uses_first_relevant_position():
    assert reciprocal_rank([9, 8, 7], {7}, 5) == pytest.approx(1 / 3)
    assert reciprocal_rank([9, 8, 7], {9}, 5) == 1.0
    assert reciprocal_rank([9, 8, 7], {1}, 5) == 0.0


def test_reciprocal_rank_is_truncated_at_k():
    """MRR must respect the same cutoff as every other metric.

    Untruncated, a --top-k 20 run scored hits at ranks 6-20 that a hit@5 or
    ndcg@5 on the same run counts as misses, so the arms were being gated on a
    metric measured over a different list length than the floors assume.
    """
    assert reciprocal_rank([9, 8, 7], {7}, 2) == 0.0
    assert reciprocal_rank([9, 8, 7], {7}, 3) == pytest.approx(1 / 3)


def test_ndcg_is_one_for_perfect_ranking():
    assert ndcg_at_k([1, 2, 3], {1, 2}, k=3) == pytest.approx(1.0)


def test_ndcg_penalizes_relevant_results_ranked_lower():
    perfect = ndcg_at_k([1, 2, 3], {1}, k=3)
    demoted = ndcg_at_k([2, 3, 1], {1}, k=3)
    assert demoted < perfect


def test_metrics_handle_empty_relevant_set():
    assert recall_at_k([1], set(), k=1) == 0.0
    assert ndcg_at_k([1], set(), k=1) == 0.0


# ---------------------------------------------------------------------------
# Relevance judgement
# ---------------------------------------------------------------------------


def test_relevance_matching_is_case_and_whitespace_insensitive():
    assert is_relevant("Booz  Allen\nHamilton", ["booz allen hamilton"])


def test_relevance_requires_a_phrase_match():
    assert not is_relevant("David works in Michigan", ["Booz Allen"])
