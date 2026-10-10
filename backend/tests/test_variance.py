"""Tests for run-to-run spread, and the rounding step and Floors derived from it (ADR-0007).

Judged runs are given as literals, so no Judge or generator is called: what these pin
down is the arithmetic that turns three runs' spread into published and gated numbers.
"""

from __future__ import annotations

import pytest

from eval.variance import floor, spread, step_size


def judged_case(split, supported, factual=1, declined=False, answerable=True):
    """One judged case: `supported` of its `factual` sentences supported."""
    return {
        "split": split,
        "answerable": answerable,
        "declined": declined,
        "sentences": [{"supported": i < supported} for i in range(factual)],
        "facts": [{"fact": "David works at Booz Allen Hamilton.", "conveyed": True}],
        "contradictions": [],
    }


def test_spread_is_each_metrics_range_across_runs_on_one_split():
    """Held-out spread sets the rounding step, because held-out is what is published."""
    runs = [
        {"cases": [judged_case("holdout", 1), judged_case("holdout", 1), judged_case("dev", 0)]},
        {"cases": [judged_case("holdout", 1), judged_case("holdout", 0), judged_case("dev", 1)]},
        {"cases": [judged_case("holdout", 0), judged_case("holdout", 0), judged_case("dev", 1)]},
    ]

    holdout = spread(runs, "holdout")
    every = spread(runs, "all")

    assert holdout["faithfulness"] == {"values": [1.0, 0.5, 0.0], "range": 1.0}
    assert every["faithfulness"]["values"] == pytest.approx([2 / 3, 2 / 3, 1 / 3])
    assert holdout["declineAccuracy"] == {"values": [1.0, 1.0, 1.0], "range": 0.0}


@pytest.mark.parametrize(
    ("largest_range", "step"),
    [(0.0, 0.005), (0.004, 0.005), (0.008, 0.01), (0.01, 0.01), (0.031, 0.05), (0.2, 0.1)],
)
def test_the_step_is_the_smallest_round_step_covering_the_largest_range(largest_range, step):
    """A step no smaller than the noise keeps noise alone from moving a published number."""
    ranges = {"faithfulness": largest_range / 2, "factRecall": largest_range}

    assert step_size(ranges) == step


@pytest.mark.parametrize(
    ("values", "spread_range", "step", "expected"),
    [
        # Two ranges below the lowest run, already on a step.
        ([0.97, 0.98, 0.99], 0.02, 0.01, 0.93),
        # No spread observed: one step of headroom, not none.
        ([0.95, 0.95, 0.95], 0.0, 0.01, 0.94),
        # 0.944 - 0.024 = 0.920, rounded down to a step of 0.02.
        ([0.944, 0.95, 0.956], 0.012, 0.02, 0.92),
        # 0.9 - 0.03 = 0.87, rounded down to a step of 0.02.
        ([0.9, 0.91, 0.915], 0.015, 0.02, 0.86),
    ],
)
def test_a_floor_sits_two_ranges_below_the_lowest_run_rounded_down_to_the_step(
    values, spread_range, step, expected
):
    """Three runs understate the noise, so the Floor leaves twice the observed range."""
    assert floor(values, spread_range, step) == pytest.approx(expected)
