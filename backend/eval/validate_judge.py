"""Validate the Judge against hand-labelled answer sentences before it gates a build.

Each sentence in `judge_validation.json` is one the harness judges, taken from a stored
answer and labelled by hand against the chunks that answer was written from (ADR-0007).
Prints how often Jev reaches each label's verdict, then every disagreement, split by
whether the sentence makes one claim or several:

    uv run --frozen python eval/validate_judge.py --output validation-run.json

Needs JEV_API_KEY. Labels still marked "draft" have not been reviewed by David, and are
not measured against unless asked to with --draft.
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

from eval.generation import Judge, judge_sentence  # (needs the sys.path line above)

VALIDATION_PATH = Path(__file__).resolve().parent / "judge_validation.json"
REPO_ROOT = Path(__file__).resolve().parents[2]

#: What a hand label can say of a sentence, given its answer's chunks.
HAND_LABELS = ("filler", "supported", "contradicted", "says_nothing")


def load_validation_set(path: Path = VALIDATION_PATH) -> list[dict]:
    """The labelled sentences, each with the chunks its answer was written from."""
    validation = json.loads(path.read_text(encoding="utf-8"))
    record = json.loads((REPO_ROOT / validation["record"]).read_text(encoding="utf-8"))
    chunks = {case["id"]: case["chunks"] for case in record["cases"]}
    return [
        {**sentence, "chunks": chunks[sentence["case"]]} for sentence in validation["sentences"]
    ]


def compare(items: list[dict], judge: Judge) -> dict:
    """How often the Judge reaches each hand label's verdict, and where it does not.

    Two agreements are reported, each for something a judged run outputs. Faithfulness
    agreement: filler, supported, or unsupported, where a contradicted sentence and one
    the chunks say nothing about are both unsupported. Contradiction agreement: whether a
    Contradiction is listed. A sentence counts as one disagreement if either differs.
    """
    disagreements = []
    faithful_agreed = contradiction_agreed = 0
    tally = {"compound": {"sentences": 0, "disagreements": 0}}
    tally["single"] = {"sentences": 0, "disagreements": 0}
    for item in items:
        relations = judge_sentence(item["text"], item["chunks"], judge)
        verdict = judge_verdict(relations)
        contradicts = relations is not None and "contradicts" in relations
        faithful = verdict == HAND_VERDICT[item["label"]]
        contradiction = contradicts == (item["label"] == "contradicted")
        faithful_agreed += faithful
        contradiction_agreed += contradiction
        group = tally["compound" if item["compound"] else "single"]
        group["sentences"] += 1
        if not (faithful and contradiction):
            group["disagreements"] += 1
            disagreements.append(
                {
                    "case": item["case"],
                    "text": item["text"],
                    "compound": item["compound"],
                    "hand": item["label"],
                    "judge": verdict,
                    "judgeContradicts": contradicts,
                    "relations": relations,
                }
            )
    return {
        "sentences": len(items),
        "faithfulnessAgreement": faithful_agreed / len(items),
        "contradictionAgreement": contradiction_agreed / len(items),
        **tally,
        "disagreements": disagreements,
    }


#: The verdict Faithfulness reaches for each hand label.
HAND_VERDICT = {
    "filler": "filler",
    "supported": "supported",
    "contradicted": "unsupported",
    "says_nothing": "unsupported",
}


def judge_verdict(relations: list[str] | None) -> str:
    """The verdict a judged run reaches: supported if any one chunk supports the sentence."""
    if relations is None:
        return "filler"
    return "supported" if "supports" in relations else "unsupported"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", action="store_true", help="Measure against draft labels.")
    parser.add_argument("--output", type=Path, help="Also write the report here, as JSON.")
    args = parser.parse_args()

    from dotenv import load_dotenv

    from eval.judge import JevJudge
    from eval.publish import _git_commit

    status = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["status"]
    if status != "reviewed" and not args.draft:
        raise SystemExit(f"FAIL — the labels are {status}, not reviewed. Pass --draft to measure.")

    load_dotenv(BACKEND_ROOT / ".env")
    judge = JevJudge(os.environ["JEV_API_KEY"])
    report = compare(load_validation_set(), judge)

    print(f"Judge: {judge.model} | {report['sentences']} {status} hand labels\n")
    print(f"  Faithfulness agreement   {report['faithfulnessAgreement']:.3f}")
    print(f"  Contradiction agreement  {report['contradictionAgreement']:.3f}")
    for group in ("compound", "single"):
        tally = report[group]
        print(f"  {group:<8} sentences: {tally['disagreements']} of {tally['sentences']} disagree")
    print(f"\nDisagreements ({len(report['disagreements'])}):")
    for d in report["disagreements"]:
        listed = ", Contradiction listed" if d["judgeContradicts"] else ""
        kind = "compound" if d["compound"] else "single"
        print(f"  {d['case']} ({kind}): hand {d['hand']}, Jev {d['judge']}{listed}")
        print(f"    {d['text']}")
        print(f"    relations: {d['relations']}")
    print(f"\nJudge usage: {judge.usage}")
    if args.output:
        document = {
            "judge": judge.model,
            "labels": status,
            "commit": _git_commit(),
            "judgedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            **report,
        }
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
