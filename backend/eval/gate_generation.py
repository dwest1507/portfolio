"""Generation gate: answer the whole Golden Set with the Shipped Arm, judge it, check the Floors.

Every case is retrieved with production retrieval (the Shipped Arm), answered by the
OpenAI model the Floors were measured on, and judged by the pinned Judge. The run fails
if Faithfulness or Decline accuracy falls below its Floor (`FLOORS` in eval/generation.py,
ADR-0007). Fact Recall and Contradictions are printed but not gated.

With --publish, the held-out cases of the same run are published as the Shipped Arm
section of frontend/data/generationResults.json, unless the rounded measurement is
unchanged. A run below a Floor publishes nothing.

    uv run --frozen python eval/gate_generation.py
    uv run --frozen python eval/gate_generation.py --publish --output judged.json

Needs OPENAI_CI_API_KEY (generation and the claim splitter) and JEV_API_KEY (the Judge):
CI's own keys, never production's. A run costs a few cents. Cases are answered and
judged eight at a time (`--workers`), so a run takes minutes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

from eval.generation import (  # (needs the sys.path line above)
    FLOORS,
    add_workers_argument,
    format_report,
    gate_failures,
    openai_generator,
    run_generation,
)
from eval.judge import JevJudge
from eval.publish import shipped_arm_id
from eval.publish_generation import GENERATION_RESULTS_PATH, build_section, write_section
from eval.run_eval import GOLDEN_SET_PATH, describe_cases, select_cases
from eval.run_generation import OPENAI_MODEL, OPENAI_REASONING_EFFORT
from eval.splitter import OpenAISplitter

#: The keys the gate needs. CI maps its own secrets onto these.
REQUIRED_KEYS = ("OPENAI_CI_API_KEY", "JEV_API_KEY")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the held-out results as the Shipped Arm section when the gate passes.",
    )
    parser.add_argument("--output", type=Path, help="Also write the judged run here, as JSON.")
    add_workers_argument(parser)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    load_dotenv()
    missing = [key for key in REQUIRED_KEYS if not os.environ.get(key)]
    if missing:
        print(f"FAIL — the generation gate needs {', '.join(missing)}.")
        return 1

    from openai import OpenAI

    from app.rag.pipeline import RAGPipeline

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], "all")
    pipeline = RAGPipeline()
    arm = shipped_arm_id()
    client = OpenAI(api_key=os.environ["OPENAI_CI_API_KEY"], max_retries=6)
    generate = openai_generator(client, OPENAI_MODEL, OPENAI_REASONING_EFFORT)
    splitter = OpenAISplitter(client)
    judge = JevJudge(os.environ["JEV_API_KEY"], splitter)

    print(f"Golden set: {describe_cases(cases)} | {OPENAI_MODEL} on the {arm} arm\n")

    def on_case(result: dict) -> None:
        verdict = "declined" if result["declined"] else f"{len(result['sentences'])} factual"
        print(f"  {result['id']}: {verdict}", flush=True)

    run = run_generation(
        cases, pipeline.retrieve, generate, judge=judge, on_case=on_case, workers=args.workers
    )
    print()
    print(format_report(run))
    print(f"\nGeneration usage: {run['usage']}")
    print(f"Judge usage: {judge.reported_usage}")
    print(f"Splitter usage ({run['splitter']}): {splitter.usage}")
    if args.output:
        args.output.write_text(
            json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")

    floors = ", ".join(f"{metric} ≥ {floor}" for metric, floor in FLOORS.items())
    failures = gate_failures(run["metrics"])
    if failures:
        print(f"\nFAIL — below the generation Floors ({floors}):")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"\nOK — generation Floors met ({floors}).")

    if args.publish:
        section = build_section(
            run,
            arm=arm,
            requested_model=OPENAI_MODEL,
            reasoning_effort=OPENAI_REASONING_EFFORT,
            corpus_chunks=len(pipeline.chunks),
        )
        _, written = write_section("shippedArm", section, GENERATION_RESULTS_PATH)
        state = "published" if written else "unchanged after rounding; not rewritten"
        print(f"Shipped Arm section {state}: {GENERATION_RESULTS_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
