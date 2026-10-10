"""Judge a stored generation record, such as the Groq baseline, without regenerating it.

Each case is replayed from the record: the Judge sees the answer the model gave and the
exact chunks it was given, so the only model called is the Judge. Prints Fact Recall,
Faithfulness and Decline accuracy, then lists every Contradiction (ADR-0007):

    uv run --frozen python eval/judge_generation.py                  # the Groq baseline
    uv run --frozen python eval/judge_generation.py --split holdout --output judged.json

Needs JEV_API_KEY. Jev bills per input token: judging the whole baseline costs well under
a cent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

from eval.generation import format_report, replay, run_generation
from eval.judge import JevJudge
from eval.publish import _git_commit
from eval.run_eval import GOLDEN_SET_PATH, SPLITS, select_cases
from eval.run_generation import BASELINE_PATH

#: What a judged run carries over from the record it judged: what was measured, and when.
RECORD_KEYS = ("provider", "requestedModel", "arm", "temperature", "maxTokens", "corpusChunks")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record",
        type=Path,
        default=BASELINE_PATH,
        help="The stored generation record to judge (default: the Groq baseline).",
    )
    parser.add_argument("--split", choices=SPLITS, default="all")
    parser.add_argument("--output", type=Path, help="Also write the judged run here, as JSON.")
    args = parser.parse_args()

    load_dotenv()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], args.split)
    judge = JevJudge(os.environ["JEV_API_KEY"])

    def on_case(result: dict) -> None:
        verdict = "declined" if result["declined"] else f"{len(result['sentences'])} factual"
        print(f"  {result['id']}: {verdict}", flush=True)

    run = run_generation(cases, *replay(record), judge=judge, on_case=on_case)
    print()
    judged = {
        "record": {
            "path": str(args.record.resolve().relative_to(BACKEND_ROOT.parent)),
            **{key: record.get(key) for key in RECORD_KEYS},
            "commit": record.get("commit"),
            "measuredAt": record.get("measuredAt"),
        },
        "split": args.split,
        "judge": run["judge"],
        "judgeUsage": judge.usage,
        "commit": _git_commit(),
        "judgedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "metrics": run["metrics"],
        "contradictions": run["contradictions"],
        "cases": run["cases"],
    }

    print(format_report(run))
    print(f"\nJudge usage: {judge.usage}")
    if args.output:
        args.output.write_text(
            json.dumps(judged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
