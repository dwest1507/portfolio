"""Validate the Judge against hand-labelled answer sentences before it gates a build.

Each sentence in `judge_validation.json` is one the harness judges, taken from a stored
answer and labelled by hand against the chunks that answer was written from (ADR-0007).
Prints how often Jev reaches each label's verdict, then every disagreement, split by
whether the sentence makes one claim or several:

    uv run --frozen python eval/validate_judge.py --output validation-run.json

Held-out sentences are left out, so tuning the Judge's questions never sees Jev's
judgments of them. The final measurement judges them too, and checks the pass bar:

    uv run --frozen python eval/validate_judge.py --final --output validation-run.json

Needs JEV_API_KEY, and OPENAI_CI_API_KEY for the model that splits sentences into claims
(eval/splitter.py). Labels still marked "draft" have not been reviewed by David, and are
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

from eval.generation import (  # (needs the sys.path line above)
    ClaimJudgment,
    Judge,
    judge_sentence,
)

VALIDATION_PATH = Path(__file__).resolve().parent / "judge_validation.json"
REPO_ROOT = Path(__file__).resolve().parents[2]

#: What a hand label can say of a sentence, given its answer's chunks.
HAND_LABELS = ("filler", "supported", "contradicted", "says_nothing")


def load_validation_set(path: Path = VALIDATION_PATH, held_out: bool = False) -> list[dict]:
    """The labelled sentences, each with its case's question and the chunks its answer
    was written from.

    Held-out sentences are left out unless asked for: they are kept out of tuning the
    Judge's questions, and judged only in the final measurement.
    """
    validation = json.loads(path.read_text(encoding="utf-8"))
    record = json.loads((REPO_ROOT / validation["record"]).read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in record["cases"]}
    return [
        {
            **sentence,
            "question": cases[sentence["case"]]["question"],
            "chunks": cases[sentence["case"]]["chunks"],
        }
        for sentence in validation["sentences"]
        if held_out or not sentence.get("heldOut")
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
    held_out_unsupported, supported, across = [], [], []
    for item in items:
        claims = judge_sentence(item["question"], item["text"], item["chunks"], judge)
        verdict = judge_verdict(claims)
        contradicts = claims is not None and any(
            relation.label == "contradicts" for claim in claims for relation in claim.relations
        )
        faithful = verdict == HAND_VERDICT[item["label"]]
        contradiction = contradicts == (item["label"] == "contradicted")
        faithful_agreed += faithful
        contradiction_agreed += contradiction
        if item.get("heldOut") and HAND_VERDICT[item["label"]] == "unsupported":
            held_out_unsupported.append(faithful)
        if item["label"] == "supported":
            supported.append(faithful)
        if item.get("acrossChunks"):
            across.append(faithful)
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
                    "claims": None
                    if claims is None
                    else [
                        {
                            "claim": claim.claim,
                            "supported": claim.supported,
                            "relations": [relation.label for relation in claim.relations],
                        }
                        for claim in claims
                    ],
                }
            )
    return {
        "sentences": len(items),
        "faithfulnessAgreement": faithful_agreed / len(items),
        "contradictionAgreement": contradiction_agreed / len(items),
        "heldOutUnsupportedCaught": share(held_out_unsupported),
        "supportedKept": share(supported),
        "acrossChunksKept": share(across),
        **tally,
        "disagreements": disagreements,
    }


#: What the Judge must reach before Faithfulness gates anything, set by David before the
#: final run (#81). Shares, not counts, so the bar holds as the labelled set grows.
PASS_BAR = {
    # Held-out unsupported sentences called unsupported. At 10 of 12 this is the least
    # that shows, at 95% confidence, the Judge catches more than half of them.
    "heldOutUnsupportedCaught": 0.83,
    # Supported sentences still called supported: catching inventions must not cost this.
    "supportedKept": 0.90,
    # Of those, the ones only several chunks together support: a strict `supports`, asked
    # one chunk at a time, would fail these.
    "acrossChunksKept": 0.80,
    "faithfulnessAgreement": 0.85,
}


def missed_bar(report: dict) -> list[str]:
    """The measures in `report` below the bar. A measure with no sentences misses it."""
    return [
        measure
        for measure, bar in PASS_BAR.items()
        if report[measure] is None or report[measure] < bar
    ]


def share(agreed: list[bool]) -> float | None:
    """The share of these sentences the Judge agreed on, or None if there are none."""
    return sum(agreed) / len(agreed) if agreed else None


#: The verdict Faithfulness reaches for each hand label.
HAND_VERDICT = {
    "filler": "filler",
    "supported": "supported",
    "contradicted": "unsupported",
    "says_nothing": "unsupported",
}


def judge_verdict(claims: list[ClaimJudgment] | None) -> str:
    """The verdict a judged run reaches: supported if some chunk supports every claim."""
    if claims is None:
        return "filler"
    return "supported" if all(claim.supported for claim in claims) else "unsupported"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", action="store_true", help="Measure against draft labels.")
    parser.add_argument("--output", type=Path, help="Also write the report here, as JSON.")
    parser.add_argument(
        "--final",
        action="store_true",
        help="The final measurement: also judge the held-out sentences, and check the bar.",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    from openai import OpenAI

    from eval.judge import JevJudge
    from eval.publish import _git_commit
    from eval.splitter import OpenAISplitter

    status = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["status"]
    if status != "reviewed" and not args.draft:
        raise SystemExit(f"FAIL — the labels are {status}, not reviewed. Pass --draft to measure.")

    load_dotenv(BACKEND_ROOT / ".env")
    splitter = OpenAISplitter(OpenAI(api_key=os.environ["OPENAI_CI_API_KEY"], max_retries=6))
    judge = JevJudge(os.environ["JEV_API_KEY"], splitter)
    report = compare(load_validation_set(held_out=args.final), judge)

    scope = "with" if args.final else "without"
    print(
        f"Judge: {judge.model}, claims split by {splitter.model} | "
        f"{report['sentences']} {status} hand labels, {scope} held-out\n"
    )
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
        for claim in d["claims"] or []:
            mark = "supported" if claim["supported"] else "unsupported"
            print(f"      {mark:<11} {claim['claim']}  {claim['relations']}")
    if args.final:
        print("\nPass bar:")
        for measure, bar in PASS_BAR.items():
            value = report[measure]
            shown = "none" if value is None else f"{value:.3f}"
            print(f"  {measure:<26} {shown:>6}  (bar {bar:.0%})")
    print(f"\nJudge usage: {judge.usage}")
    print(f"Splitter usage: {splitter.usage}")
    if args.output:
        document = {
            "judge": judge.model,
            "splitter": splitter.model,
            "labels": status,
            "commit": _git_commit(),
            "judgedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            **report,
        }
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    if args.final:
        missed = missed_bar(report)
        print(f"\n{'FAIL — below the bar: ' + ', '.join(missed) if missed else 'PASS'}")
        return 1 if missed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
