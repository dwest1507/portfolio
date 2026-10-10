"""Capture the Groq generation baseline: every Golden Set case, answered by the Shipped Arm.

Runs both Splits, answerable and Out-of-Scope Cases alike, through production retrieval
and the current Groq model, and commits what each answer was written from. Nothing is
judged here: the record keeps the exact retrieved chunks so a Judge can score it later,
and OpenAI candidates can replay identical contexts, leaving the model as the only
variable (ADR-0007, ADR-0008).

Groq's free tier is shared with visitors: 8k tokens/min and 200k tokens/day. Calls are
paced to the per-minute limit, and the run stops before passing its token budget. Each
answer is written to the record as it arrives, so a run that stops partway resumes where
it left off:

    uv run --frozen python eval/run_generation.py              # capture or resume
    uv run --frozen python eval/run_generation.py --token-budget 50000
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.generation import (  # (needs the sys.path line above)
    TokenBudgetExhausted,
    groq_generator,
    run_generation,
    throttled,
    total_usage,
)
from eval.publish import _git_commit, shipped_arm_id
from eval.run_eval import GOLDEN_SET_PATH, describe_cases, select_cases

BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "groq.json"

# Groq's free tier allows 8,000 tokens a minute. Pacing a little under it leaves room
# for a visitor's question during the run.
TOKENS_PER_MINUTE = 7000

# Groq's free tier allows 200,000 tokens a day, shared with visitors. A full run measured
# ~1.3-1.6k tokens a case, ~160k for the whole Golden Set.
DEFAULT_TOKEN_BUDGET = 180_000


def load_record(path: Path, header: dict) -> dict:
    """The record to resume, or a fresh one. Refuses to mix runs that measured different things."""
    if not path.exists():
        return {**header, "cases": [], "usage": {}}
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in ("provider", "requestedModel", "arm", "temperature", "maxTokens", "corpusChunks"):
        if record.get(key) != header[key]:
            raise SystemExit(
                f"FAIL — {path.name} was measured with {key}={record.get(key)!r}, this run "
                f"has {header[key]!r}. Resuming would mix two measurements; move the file "
                "aside to start over."
            )
    return record


def save_record(path: Path, record: dict, order: list[str]) -> None:
    """Write the record with cases in Golden Set order, so a resumed run diffs cleanly."""
    position = {case_id: i for i, case_id in enumerate(order)}
    record["cases"].sort(key=lambda c: position[c["id"]])
    record["usage"] = total_usage(record["cases"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-budget",
        type=int,
        default=DEFAULT_TOKEN_BUDGET,
        help=f"Stop before this run spends more tokens (default: {DEFAULT_TOKEN_BUDGET:,}).",
    )
    args = parser.parse_args()

    from groq import Groq

    from app.config import GROQ_API_KEY, GROQ_MODEL
    from app.llm import MAX_TOKENS, TEMPERATURE
    from app.rag.pipeline import RAGPipeline

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], "all")
    pipeline = RAGPipeline()

    header = {
        "description": (
            "Groq generation baseline: each Golden Set case answered by the Shipped Arm, "
            "with the chunks it was answered from. Unjudged. See docs/evaluation.md."
        ),
        "provider": "groq",
        "requestedModel": GROQ_MODEL,
        "arm": shipped_arm_id(),
        "temperature": TEMPERATURE,
        "maxTokens": MAX_TOKENS,
        "corpusChunks": len(pipeline.chunks),
        "commit": _git_commit(),
        "measuredAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    record = load_record(BASELINE_PATH, header)
    done = {c["id"] for c in record["cases"]}
    pending = [c for c in cases if c["id"] not in done]
    order = [c["id"] for c in cases]

    print(
        f"Golden set: {describe_cases(cases)} | {len(done)} recorded, {len(pending)} to go | "
        f"{GROQ_MODEL} on the {header['arm']} arm\n"
    )

    # Groq's own retries honour its retry-after header, which is what a brief overrun of
    # the per-minute limit returns.
    client = Groq(api_key=GROQ_API_KEY, max_retries=6)
    generate = throttled(
        groq_generator(client, GROQ_MODEL),
        tokens_per_minute=TOKENS_PER_MINUTE,
        token_budget=args.token_budget,
    )

    def on_case(result: dict) -> None:
        record["cases"].append(result)
        save_record(BASELINE_PATH, record, order)
        print(
            f"  [{len(record['cases'])}/{len(cases)}] {result['id']}: "
            f"{result['usage']['total_tokens']} tokens ({result['model']})"
        )

    try:
        run_generation(pending, pipeline.retrieve, generate, on_case=on_case)
    except TokenBudgetExhausted as exc:
        print(f"\nStopped: {exc}\nRerun tomorrow to resume.")
        return 1

    save_record(BASELINE_PATH, record, order)
    print(f"\nRecorded {len(record['cases'])} cases; usage {record['usage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
