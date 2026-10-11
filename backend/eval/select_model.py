"""Choose the generation model by ADR-0008's rule: the cheapest unless the data can see otherwise.

Each candidate is compared with the model it would replace by ADR-0006's test: only the
pairs where the two disagree carry information, and a difference counts only when their
split is too lopsided to be chance.

It reads three judged runs, as `judge_generation.py --output` writes them, of answers
written from the same stored contexts (`run_generation.py --contexts`), so the model is
the only variable. The choice is made on `dev` and confirmed on `holdout`:

    uv run --frozen python eval/select_model.py runs/groq.json runs/luna.json runs/sol.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.generation import compare, fmt, score  # (needs the sys.path line above)
from eval.publish_generation import PRICES_PER_MILLION

#: The metrics the rule decides on: a model distinguishably worse on either is not chosen.
GATED = ("faithfulness", "declineAccuracy")

#: Breaks a tie between the gated metrics, and never justifies an upgrade alone.
TIEBREAK = "factRecall"


def select_model(groq: dict, luna: dict, sol: dict) -> dict:
    """Which model the rule picks from three judged runs over the same cases and contexts.

    1. Luna replaces Groq unless distinguishably worse on Faithfulness or Decline accuracy.
    2. Sol replaces Luna only if distinguishably better on either. Better on one and worse
       on the other is a tie, which Fact Recall breaks: Sol only if distinguishably ahead.

    The rule says nothing of Sol once Luna is rejected, so that is left to a person.
    """
    luna_vs_groq = compare(luna, groq)
    sol_vs_luna = compare(sol, luna)
    comparisons = {"luna-vs-groq": luna_vs_groq, "sol-vs-luna": sol_vs_luna}
    if any(luna_vs_groq[metric]["outcome"] == "behind" for metric in GATED):
        return {"chosen": "groq", "comparisons": comparisons}

    gated = {sol_vs_luna[metric]["outcome"] for metric in GATED}
    if "ahead" in gated and "behind" in gated:
        upgrade = sol_vs_luna[TIEBREAK]["outcome"] == "ahead"
    else:
        upgrade = "ahead" in gated
    return {"chosen": "sol" if upgrade else "luna", "comparisons": comparisons}


#: USD per 1M (input, output) tokens: OpenAI's published prices, and the Groq baseline's
#: free tier. Groq's paid tier is no longer offered (ADR-0008), so it has no price.
PRICES = {**PRICES_PER_MILLION, "openai/gpt-oss-120b": (0.0, 0.0)}


def cost_per_answer(run: dict) -> float:
    """Mean billed cost of one answer in USD, from each case's billed usage.

    Unlike the published cost, it is not rounded: two models' costs are compared here.
    Every input token is priced as uncached, an upper bound.
    """
    input_price, output_price = PRICES[run["record"]["requestedModel"]]
    cases = run["cases"]
    cost = sum(
        case["usage"]["prompt_tokens"] * input_price
        + case["usage"]["completion_tokens"] * output_price
        for case in cases
    )
    return cost / 1_000_000 / len(cases)


def in_split(run: dict, split: str) -> dict:
    return {**run, "cases": [case for case in run["cases"] if case["split"] == split]}


def report(runs: dict[str, dict], split: str) -> str:
    """One split's metrics and cost per model, each comparison, and the rule's choice."""
    runs = {name: in_split(run, split) for name, run in runs.items()}
    decision = select_model(**runs)
    lines = [
        f"{split} ({len(runs['groq']['cases'])} cases)",
        "",
        "  Model                 Fact Recall  Faithfulness  Decline acc.  $/answer",
    ]
    for run in runs.values():
        metrics = score(run["cases"])
        lines.append(
            f"  {run['record']['requestedModel']:<20}  {fmt(metrics['factRecall']):>11}  "
            f"{fmt(metrics['faithfulness']):>12}  {fmt(metrics['declineAccuracy']):>12}  "
            f"{cost_per_answer(run):.6f}"
        )
    lines.append("")
    for pairing, comparison in decision["comparisons"].items():
        lines.append(f"  {pairing}:")
        for metric, result in comparison.items():
            lines.append(
                f"    {metric:<16} won {result['won']:>2}, lost {result['lost']:>2}: "
                f"{result['outcome']}"
            )
    lines += ["", f"  Chosen: {decision['chosen']}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groq", type=Path, help="The judged Groq baseline.")
    parser.add_argument("luna", type=Path, help="gpt-6-luna, judged, on the baseline's contexts.")
    parser.add_argument("sol", type=Path, help="gpt-6.1-sol, judged, on the baseline's contexts.")
    args = parser.parse_args()
    runs = {
        name: json.loads(getattr(args, name).read_text(encoding="utf-8"))
        for name in ("groq", "luna", "sol")
    }
    for split in ("dev", "holdout"):
        print(report(runs, split), end="\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
