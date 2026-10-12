"""Validate the Judge against hand-labelled answer sentences before it gates a build.

Each sentence in `judge_validation.json` is one the harness judges, taken from a stored
answer and labelled by hand against the chunks that answer was written from (ADR-0007).
Prints how often Jev reaches each label's verdict, then every disagreement, split by
whether the sentence makes one claim or several:

    uv run --frozen python eval/validate_judge.py --output validation-run.json

Held-out sentences are left out, so tuning the Judge's questions never sees Jev's
judgments of them. The final measurement judges them too, three times, and checks the
pass bar against the median:

    uv run --frozen python eval/validate_judge.py --final --output validation-run.json

With --declines it validates the Decline judgment instead, against whole answers labelled
with whether they Decline (#86), and checks its own bar (DECLINE_PASS_BAR) the same way:

    uv run --frozen python eval/validate_judge.py --declines --final --output declines-run.json

Needs JEV_API_KEY, and OPENAI_CI_API_KEY for the model that splits sentences into claims
(eval/splitter.py). Labels still marked "draft" have not been reviewed by David, and are
not measured against unless asked to with --draft: for sentences the whole set carries
one status, and each Decline label carries its own.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
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


#: The final measurement runs this many times and checks the bar against the median of
#: each measure, as David decided (#81): splits and Jev's borderline judgments vary from
#: run to run, so one run could pass or fail on noise. Three, as in the spread study.
FINAL_RUNS = 3


def median_of(reports: list[dict], bar: dict[str, float] = PASS_BAR) -> dict:
    """Each measure of `bar`, as its median over `reports`; None if any run lacks it."""
    medians = {}
    for measure in bar:
        values = [report[measure] for report in reports]
        medians[measure] = None if None in values else statistics.median(values)
    return medians


def missed_bar(report: dict, bar: dict[str, float] = PASS_BAR) -> list[str]:
    """The measures in `report` below `bar`. A measure with nothing to measure misses it."""
    return [
        measure
        for measure, least in bar.items()
        if report[measure] is None or report[measure] < least
    ]


#: What kind of answer a Decline label is on. A hedged answer says something is not
#: available and also gives something: part of what was asked (not a Decline, per
#: CONTEXT.md), or only what is near it (a Decline). That is where Jev has been wrong.
DECLINE_KINDS = ("decline", "answer", "hedged")


def load_decline_labels(
    path: Path = VALIDATION_PATH, held_out: bool = False, draft: bool = False
) -> list[dict]:
    """The answer-level Decline labels, each with the question and answer it is about.

    Held-out labels are left out unless asked for, as for sentences. So are labels still
    marked draft: David has not reviewed them, so they cannot decide whether the Judge
    may gate.
    """
    validation = json.loads(path.read_text(encoding="utf-8"))
    return [
        label
        for label in validation["declines"]
        if (held_out or not label.get("heldOut")) and (draft or not label.get("draft"))
    ]


def compare_declines(items: list[dict], judge: Judge) -> dict:
    """How often the Judge agrees with the hand label on whether an answer Declines.

    Disagreements are listed and counted per kind of answer, so errors on partial and
    hedged answers stand out from errors on clear ones.
    """
    tally = {kind: {"answers": 0, "disagreements": 0} for kind in DECLINE_KINDS}
    agreed, held_out, disagreements = [], [], []
    for item in items:
        verdict = judge.declines(item["question"], item["answer"])
        agrees = verdict == item["declines"]
        agreed.append(agrees)
        if item.get("heldOut"):
            held_out.append(agrees)
        tally[item["kind"]]["answers"] += 1
        if not agrees:
            tally[item["kind"]]["disagreements"] += 1
            disagreements.append(
                {
                    "case": item["case"],
                    "run": item["run"],
                    "kind": item["kind"],
                    "question": item["question"],
                    "answer": item["answer"],
                    "hand": item["declines"],
                    "judge": verdict,
                }
            )
    return {
        "answers": len(items),
        "declineAgreement": share(agreed),
        "heldOutDeclineAgreement": share(held_out),
        **tally,
        "disagreements": disagreements,
    }


#: What the Decline judgment must reach before Decline accuracy gates anything (#86):
#: agreement on held-out answers, against the median of `FINAL_RUNS` runs.
DECLINE_PASS_BAR = {"heldOutDeclineAgreement": 0.9}


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
        help="The final measurement: also judge the held-out labels, and check the bar.",
    )
    parser.add_argument(
        "--declines",
        action="store_true",
        help="Measure the Decline judgment against the answer-level labels instead.",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    from openai import OpenAI

    from eval.judge import JevJudge
    from eval.publish import _git_commit
    from eval.splitter import OpenAISplitter

    if args.declines:
        items = load_decline_labels(held_out=args.final, draft=args.draft)
        drafts = sum(1 for item in items if item.get("draft"))
        status = f"{drafts} draft" if drafts else "reviewed"
        if not items:
            raise SystemExit("FAIL — no reviewed Decline labels. Pass --draft to measure.")
        measure, report_on, bar = compare_declines, print_decline_report, DECLINE_PASS_BAR
    else:
        status = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))["status"]
        if status != "reviewed" and not args.draft:
            raise SystemExit(
                f"FAIL — the labels are {status}, not reviewed. Pass --draft to measure."
            )
        items = load_validation_set(held_out=args.final)
        measure, report_on, bar = compare, print_report, PASS_BAR

    load_dotenv(BACKEND_ROOT / ".env")
    splitter = OpenAISplitter(OpenAI(api_key=os.environ["OPENAI_CI_API_KEY"], max_retries=6))
    judge = JevJudge(os.environ["JEV_API_KEY"], splitter)

    scope = "with" if args.final else "without"
    print(
        f"Judge: {judge.model}, claims split by {splitter.model} | "
        f"{len(items)} {status} {'Decline ' if args.declines else ''}hand labels, "
        f"{scope} held-out\n"
    )
    reports = []
    for run in range(FINAL_RUNS if args.final else 1):
        if args.final:
            print(f"Run {run + 1} of {FINAL_RUNS}")
        reports.append(measure(items, judge))
        report_on(reports[-1])
    print(f"\nJudge usage: {judge.usage}")
    print(f"Splitter usage: {splitter.usage}")

    median = median_of(reports, bar) if args.final else None
    if median is not None:
        print("\nPass bar, against the median of the runs:")
        for name, least in bar.items():
            runs = "  ".join(shown(report[name]) for report in reports)
            print(f"  {name:<26} runs {runs}  median {shown(median[name])}  (bar {least:.0%})")
    if args.output:
        document = {
            "judge": judge.model,
            "splitter": splitter.model,
            "judgment": "declines" if args.declines else "sentences",
            "labels": status,
            "commit": _git_commit(),
            "judgedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            **({"runs": reports, "median": median} if args.final else reports[0]),
        }
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    if median is not None:
        missed = missed_bar(median, bar)
        print(f"\n{'FAIL — below the bar: ' + ', '.join(missed) if missed else 'PASS'}")
        return 1 if missed else 0
    return 0


def print_decline_report(report: dict) -> None:
    print(f"  Decline agreement           {shown(report['declineAgreement'])}")
    print(f"  Held-out Decline agreement  {shown(report['heldOutDeclineAgreement'])}")
    for kind in DECLINE_KINDS:
        tally = report[kind]
        print(f"  {kind:<8} answers: {tally['disagreements']} of {tally['answers']} disagree")
    print(f"\nDisagreements ({len(report['disagreements'])}):")
    for d in report["disagreements"]:
        hand = "Declines" if d["hand"] else "answers"
        judge = "Declines" if d["judge"] else "answers"
        print(f"  {d['case']} ({d['kind']}, {d['run']} run): hand {hand}, Jev {judge}")
        print(f"    Q: {d['question']}")
        print(f"    A: {' '.join(d['answer'].split())}")
    print()


def print_report(report: dict) -> None:
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
    print()


def shown(value: float | None) -> str:
    return "none" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
