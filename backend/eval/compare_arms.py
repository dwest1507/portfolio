"""Comparison run: every Candidate Arm through generation, compared with the Shipped Arm.

The evidence the Shipped Arm decision rests on (ADR-0009): each Candidate Arm, the
Shipped Arm among them, retrieves for every Golden Set case on both Splits, the OpenAI
model the Floors were measured on answers from what it retrieved, and the pinned Judge
scores each answer. Reference Arms are never run: they can't ship, so generation budget
spent on them buys nothing (ADR-0007).

Each Candidate Arm is compared with the Shipped Arm by ADR-0006's test on every metric
the rule reads: Fact Recall, Faithfulness and Decline accuracy. The decision is made on
`dev`, whose report is printed and kept in the judged run (`--output`, a CI artifact);
only `holdout` is published, as the Comparison section of
frontend/data/generationResults.json (`--publish`).

    uv run --frozen python eval/compare_arms.py --output comparison.json
    uv run --frozen python eval/compare_arms.py --publish --output comparison.json

Needs OPENAI_CI_API_KEY and JEV_API_KEY, as the generation gate does. It runs four Arms
through the whole Golden Set, so it costs about four gate runs; it runs only on demand.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

from eval.generation import (  # (needs the sys.path line above)
    Generator,
    Judge,
    Retriever,
    compare,
    fmt,
    openai_generator,
    run_generation,
    score,
)
from eval.judge import JevJudge
from eval.publish import ARM_SPECS, CANDIDATE, shipped_arm_id
from eval.publish_generation import (
    GENERATION_RESULTS_PATH,
    build_comparison_section,
    write_section,
)
from eval.run_eval import (
    DEFAULT_TOP_K,
    GOLDEN_SET_PATH,
    build_pipeline,
    describe_cases,
    retrievers_for_arms,
    select_cases,
)
from eval.run_generation import OPENAI_MODEL, OPENAI_REASONING_EFFORT
from eval.splitter import OpenAISplitter

#: The keys the run needs, as for the generation gate. CI maps its own secrets onto these.
REQUIRED_KEYS = ("OPENAI_CI_API_KEY", "JEV_API_KEY")


def candidate_arms() -> list[str]:
    """The Arms eligible to ship, in registry order (ADR-0009)."""
    return [arm.id for arm in ARM_SPECS if arm.eligibility == CANDIDATE]


def compare_arms(
    cases: list[dict],
    retrievers: dict[str, Retriever],
    generate: Generator,
    judge: Judge,
    on_case: Callable[[str, dict], None] | None = None,
) -> dict[str, dict]:
    """A judged run per Candidate Arm over `cases`, keyed by Arm ID.

    `retrievers` may hold every Arm; only the Candidate Arms' are called. `on_case`
    receives each Arm's ID and each case's result as soon as it is recorded.
    """
    arms = candidate_arms()
    missing = [arm for arm in arms if arm not in retrievers]
    if missing:
        raise ValueError(f"No retriever for Candidate Arm(s): {', '.join(missing)}.")

    runs = {}
    for arm in arms:
        report = None if on_case is None else (lambda result, arm=arm: on_case(arm, result))
        runs[arm] = run_generation(cases, retrievers[arm], generate, judge=judge, on_case=report)
    return runs


def in_split(run: dict, split: str) -> dict:
    return {**run, "cases": [case for case in run["cases"] if case["split"] == split]}


def format_comparison(runs: dict[str, dict], split: str) -> str:
    """One split's metrics per Arm, then each Arm's won/lost against the Shipped Arm.

    On `dev` this is the report ADR-0009's rule is applied to; on `holdout` it is the
    confirmation, which is also what `--publish` puts on the page.
    """
    shipped = shipped_arm_id()
    runs = {arm: in_split(run, split) for arm, run in runs.items()}
    lines = [
        f"{split} ({len(runs[shipped]['cases'])} cases)",
        "",
        "  Arm                             Fact Recall  Faithfulness  Decline acc.",
    ]
    for arm, run in runs.items():
        metrics = score(run["cases"])
        name = f"{arm} (shipped)" if arm == shipped else arm
        lines.append(
            f"  {name:<30}  {fmt(metrics['factRecall']):>11}  "
            f"{fmt(metrics['faithfulness']):>12}  {fmt(metrics['declineAccuracy']):>12}"
        )
    for arm, run in runs.items():
        if arm == shipped:
            continue
        lines += ["", f"  {arm} vs {shipped}:"]
        for metric, result in compare(run, runs[shipped]).items():
            lines.append(
                f"    {metric:<16} won {result['won']:>2}, lost {result['lost']:>2}: "
                f"{result['outcome']}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the held-out results as the Comparison section.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Also write every Arm's judged run, on both splits, here as JSON.",
    )
    args = parser.parse_args()

    load_dotenv()
    missing = [key for key in REQUIRED_KEYS if not os.environ.get(key)]
    if missing:
        print(f"FAIL — the comparison run needs {', '.join(missing)}.")
        return 1

    from openai import OpenAI

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], "all")
    pipeline = build_pipeline()
    by_id = retrievers_for_arms(pipeline, DEFAULT_TOP_K)
    # The retrieval harness's Arms return chunk IDs; generation is shown their text.
    retrievers = {
        arm: (lambda question, ids=ids: [pipeline.chunks[i]["text"] for i in ids(question)])
        for arm, ids in by_id.items()
    }
    client = OpenAI(api_key=os.environ["OPENAI_CI_API_KEY"], max_retries=6)
    generate = openai_generator(client, OPENAI_MODEL, OPENAI_REASONING_EFFORT)
    splitter = OpenAISplitter(client)
    judge = JevJudge(os.environ["JEV_API_KEY"], splitter)

    arms = candidate_arms()
    print(f"Golden set: {describe_cases(cases)} | {OPENAI_MODEL} on {', '.join(arms)}\n")

    def on_case(arm: str, result: dict) -> None:
        verdict = "declined" if result["declined"] else f"{len(result['sentences'])} factual"
        print(f"  {arm} {result['id']}: {verdict}", flush=True)

    runs = compare_arms(cases, retrievers, generate, judge, on_case=on_case)
    for split in ("dev", "holdout"):
        print()
        print(format_comparison(runs, split))
    print(f"\nJudge usage: {judge.usage}")
    print(f"Splitter usage: {splitter.usage}")
    if args.output:
        record = {
            "requestedModel": OPENAI_MODEL,
            "reasoningEffort": OPENAI_REASONING_EFFORT,
            "shippedArm": shipped_arm_id(),
            "arms": runs,
        }
        args.output.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")

    if args.publish:
        section = build_comparison_section(
            runs,
            requested_model=OPENAI_MODEL,
            reasoning_effort=OPENAI_REASONING_EFFORT,
            corpus_chunks=len(pipeline.chunks),
        )
        _, written = write_section("comparison", section, GENERATION_RESULTS_PATH)
        state = "published" if written else "unchanged after rounding; not rewritten"
        print(f"Comparison section {state}: {GENERATION_RESULTS_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
