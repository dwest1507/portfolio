"""Run-to-run spread of the generation metrics, and the rounding step and Floors set from it.

The same commit, judged or generated and judged three times, does not give the same
numbers twice (ADR-0007). This reads judged runs, as `judge_generation.py --output`
writes them, and derives:

- the rounding step for published metrics, from the held-out spread, because held-out is
  what is published: the smallest round step no smaller than any metric's range;
- the Faithfulness and Decline accuracy Floors, from the spread over every case, because
  the gate runs on the full Golden Set: twice the range below the lowest run, and at
  least one step, rounded down to the step.

    uv run --frozen python eval/variance.py runs/judged-1.json runs/judged-2.json ...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.generation import score  # (needs the sys.path line above)

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


def step_size(ranges: dict[str, float]) -> float:
    """The smallest round step no smaller than the largest range, or the largest step."""
    largest = max(ranges.values())
    return next((step for step in STEPS if step >= largest), STEPS[-1])


def floor(values: list[float], spread_range: float, step: float) -> float:
    """Twice the range below the lowest run, at least one step, rounded down to the step."""
    headroom = max(2 * spread_range, step)
    # The small tolerance keeps a value already on a step from rounding down past it.
    return round(math.floor((min(values) - headroom) / step + 1e-9) * step, 6)


def derive(runs: list[dict]) -> dict:
    """The spreads, rounding step and Floors these runs support."""
    holdout = spread(runs, "holdout")
    every = spread(runs, "all")
    step = step_size({metric: holdout[metric]["range"] for metric in PUBLISHED})
    floors = {
        metric: floor(every[metric]["values"], every[metric]["range"], step) for metric in GATED
    }
    return {"spread": {"holdout": holdout, "all": every}, "step": step, "floors": floors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+", help="Judged runs of one commit.")
    args = parser.parse_args()

    runs = [json.loads(path.read_text(encoding="utf-8")) for path in args.runs]
    derived = derive(runs)
    for split, metrics in derived["spread"].items():
        print(f"{split}:")
        for metric, measured in metrics.items():
            values = ", ".join(f"{value:.4f}" for value in measured["values"])
            print(f"  {metric:<16} {values}  (range {measured['range']:.4f})")
    print(f"\nRounding step: {derived['step']}")
    for metric, value in derived["floors"].items():
        print(f"Floor, {metric}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
