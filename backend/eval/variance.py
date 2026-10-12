"""Run-to-run spread of the generation metrics, and the rounding step and Floors set from it.

The same commit, generated and judged several times, does not give the same numbers
twice (ADR-0007). From judged runs, as `judge_generation.py --output` writes them, this
derives:

- each published metric's rounding step, from its held-out spread, because held-out is
  what is published: the smallest round step no smaller than that metric's range;
- the Faithfulness and Decline accuracy Floors, from the spread over every case, because
  the gate runs on the full Golden Set: twice the range below the lowest run, and at
  least one of the metric's steps, rounded down to its step.

This is the generation rule. `eval/recalibrate.py generation` applies it to five judged
runs and writes the result into the generation Floors record (ADR-0012); nothing else
turns it into Floors.
"""

from __future__ import annotations

import math

from eval.generation import score

#: The published generation metrics: each needs a step no smaller than its noise.
PUBLISHED = ("factRecall", "faithfulness", "declineAccuracy")

#: The gated generation metrics, each with a Floor.
GATED = ("faithfulness", "declineAccuracy")

#: Round steps a published metric may be rounded to, smallest first.
STEPS = (0.005, 0.01, 0.02, 0.05, 0.1)


def spread(runs: list[dict], split: str) -> dict[str, dict]:
    """Each published metric's value in every run, on one split, and its range across them."""
    by_metric: dict[str, dict] = {}
    for metric in PUBLISHED:
        values = [score(cases_in(run, split))[metric] for run in runs]
        by_metric[metric] = {"values": values, "range": max(values) - min(values)}
    return by_metric


def cases_in(run: dict, split: str) -> list[dict]:
    return [case for case in run["cases"] if split == "all" or case["split"] == split]


def step_size(spread_range: float) -> float:
    """The smallest round step no smaller than one metric's range, or the largest step."""
    return next((step for step in STEPS if step >= spread_range), STEPS[-1])


def floor(values: list[float], spread_range: float, step: float) -> float:
    """Twice the range below the lowest run, at least one step, rounded down to the step."""
    headroom = max(2 * spread_range, step)
    # The small tolerance keeps a value already on a step from rounding down past it.
    return round(math.floor((min(values) - headroom) / step + 1e-9) * step, 6)


def derive(runs: list[dict]) -> dict:
    """The spreads, each metric's rounding step, and the Floors these runs support.

    Each metric's step comes from its own held-out range, so a noisy metric (Fact Recall
    moves with every reworded answer) cannot coarsen another's step or loosen its Floor.
    """
    holdout = spread(runs, "holdout")
    every = spread(runs, "all")
    steps = {metric: step_size(holdout[metric]["range"]) for metric in PUBLISHED}
    floors = {
        metric: floor(every[metric]["values"], every[metric]["range"], steps[metric])
        for metric in GATED
    }
    return {"spread": {"holdout": holdout, "all": every}, "steps": steps, "floors": floors}
