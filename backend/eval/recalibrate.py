"""Recalibrate a gate: re-derive its Floors by the gate's fixed rule and write its record.

The only writer of the Floors records in eval/floors/ (ADR-0012). Run it in the same
change as whatever made it necessary: a change to the Golden Set or to the instrument
that measures it. Never to make a Corpus, prompt, chunking or retrieval-code change
pass its gate; the gates exist to judge those.

    uv run --frozen python eval/recalibrate.py retrieval
    uv run --frozen python eval/recalibrate.py generation runs/judged-{1,2,3,4,5}.json

`retrieval` measures the Shipped Arm over the full Golden Set and applies the retrieval
rule: each gated metric less two answerable cases' worth (2/n), rounded down to 0.005.
It is free and deterministic, so it needs no keys and gives the same Floors every time.

`generation` reads five judged runs of the Shipped Arm over the full Golden Set (as
`judge_generation.py --output` or `gate_generation.py --output` writes them; producing
them is the paid part) and applies the variance rule: each published metric's rounding
step from its held-out range, and each Floor twice the range below the lowest run, at
least one step, rounded down to the step. It makes no call of its own.
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
    GENERATION_FLOORS_PATH,
    GENERATION_RULE,
    GENERATION_RUNS,
    RETRIEVAL_FLOORS_PATH,
    RETRIEVAL_RULE,
    generation_instrument,
    generation_record,
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


def recalibrate_generation(
    runs: list[dict], cases: list[dict], path: Path, commit: str, instrument: dict | None = None
) -> dict:
    """Derive the generation Floors and rounding steps from five judged runs and write the record.

    `runs` are judged runs of the Shipped Arm over `cases`, the full Golden Set, made with
    `instrument` (default: today's). The command is built for five runs and refuses any
    other number, and refuses runs that skipped a case, since the record's fingerprint
    would then vouch for cases its Floors were never measured on.
    """
    if len(runs) != GENERATION_RUNS:
        raise ValueError(
            f"The generation rule is built for five judged runs ({GENERATION_RUNS}); "
            f"got {len(runs)}."
        )
    expected = {case["id"] for case in cases}
    for i, run in enumerate(runs, start=1):
        judged = {case["id"] for case in run["cases"]}
        if judged != expected:
            missing = ", ".join(sorted(expected - judged)) or "none"
            extra = ", ".join(sorted(judged - expected)) or "none"
            raise ValueError(
                f"Run {i} is not of the full Golden Set: missing {missing}; not in it {extra}."
            )
    instrument = instrument if instrument is not None else generation_instrument()
    record = generation_record(runs, cases, instrument, shipped_arm_id(), commit)
    write_record(record, path)
    return record


def _report_retrieval(record: dict) -> None:
    n = record["inputs"]["n"]
    print(f"Rule: {RETRIEVAL_RULE}")
    for metric, floor in record["floors"].items():
        measured = record["inputs"]["measured"][metric]
        print(f"  {metric}: {measured:.6f} − 2/{n} = {measured - 2 / n:.6f} → Floor {floor}")
    print(f"\nWrote {RETRIEVAL_FLOORS_PATH.relative_to(BACKEND_ROOT)} at {record['commit']}")


def main_generation(paths: list[Path]) -> int:
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], GATED_SPLIT)
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    print(f"Recalibrating the generation gate from {len(runs)} judged runs\n")
    try:
        record = recalibrate_generation(runs, cases, GENERATION_FLOORS_PATH, _git_commit())
    except ValueError as error:
        print(f"FAIL — {error}")
        return 1

    print(f"Rule: {GENERATION_RULE}")
    for split in ("holdout", "all"):
        for metric, spread in record["inputs"][split].items():
            values = ", ".join(f"{value:.4f}" for value in spread["values"])
            print(f"  {split:<8} {metric:<16} {values}  (range {spread['range']:.4f})")
    for metric, step in record["steps"].items():
        print(f"Rounding step, {metric}: {step}")
    for metric, floor in record["floors"].items():
        print(f"Floor, {metric}: {floor}")
    print(f"\nWrote {GENERATION_FLOORS_PATH.relative_to(BACKEND_ROOT)} at {record['commit']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "gate", choices=["retrieval", "generation"], help="The gate to recalibrate."
    )
    parser.add_argument("runs", type=Path, nargs="*", help="generation only: the five judged runs.")
    args = parser.parse_args()
    if args.gate == "generation":
        return main_generation(args.runs)
    if args.runs:
        parser.error("retrieval measures its own run; it takes no judged runs.")

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
    _report_retrieval(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
