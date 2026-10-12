"""Recalibrate a gate: re-derive its Floors by the gate's fixed rule and write its record.

The only writer of the Floors records in eval/floors/ (ADR-0012). Run it in the same
change as whatever made it necessary: a change to the Golden Set or to the instrument
that measures it. Never to make a Corpus, prompt, chunking or retrieval-code change
pass its gate; the gates exist to judge those.

    uv run --frozen python eval/recalibrate.py retrieval

`retrieval` measures the Shipped Arm over the full Golden Set and applies the retrieval
rule: each gated metric less two answerable cases' worth (2/n), rounded down to 0.005.
It is free and deterministic, so it needs no keys and gives the same Floors every time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.publish import _git_commit, shipped_arm_id  # (needs the sys.path line above)
from eval.recalibration import (
    RETRIEVAL_FLOORS_PATH,
    RETRIEVAL_RULE,
    retrieval_record,
    write_record,
)
from eval.run_eval import (
    DEFAULT_TOP_K,
    GATED_METRICS,
    GATED_SPLIT,
    GOLDEN_SET_PATH,
    build_pipeline,
    describe_cases,
    evaluate_arm,
    select_cases,
)


def recalibrate_retrieval(result: dict, cases: list[dict], path: Path, commit: str) -> dict:
    """Derive the retrieval Floors from the Shipped Arm's Measured Run and write the record.

    `result` is the Shipped Arm's run over `cases`, the full Golden Set. Only the gated
    metrics get Floors.
    """
    if result["arm"] != shipped_arm_id():
        raise ValueError(
            f"Only the Shipped Arm ({shipped_arm_id()}) has Floors; got a run of {result['arm']!r}."
        )
    gated = {**result, "summary": {m: result["summary"][m] for m in GATED_METRICS}}
    record = retrieval_record(gated, cases, commit)
    write_record(record, path)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=["retrieval"], help="The gate to recalibrate.")
    parser.parse_args()

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], GATED_SPLIT)
    pipeline = build_pipeline()
    arm = shipped_arm_id()
    print(
        f"Recalibrating the retrieval gate: {arm} over {describe_cases(cases)} questions "
        f"({GATED_SPLIT}), {len(pipeline.chunks)} chunks\n"
    )

    result = evaluate_arm(pipeline, arm, cases, DEFAULT_TOP_K)
    record = recalibrate_retrieval(result, cases, RETRIEVAL_FLOORS_PATH, _git_commit())

    n = record["inputs"]["n"]
    print(f"Rule: {RETRIEVAL_RULE}")
    for metric, floor in record["floors"].items():
        measured = record["inputs"]["measured"][metric]
        print(f"  {metric}: {measured:.6f} − 2/{n} = {measured - 2 / n:.6f} → Floor {floor}")
    print(f"\nWrote {RETRIEVAL_FLOORS_PATH.relative_to(BACKEND_ROOT)} at {record['commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
