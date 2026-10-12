"""Recalibration: the Floors records, their fingerprints and their fixed rules (ADR-0012).

A Floor is re-derived only when what it measures with changes: the Golden Set, or the
instrument. Never because the system being measured changed. It is derived by a fixed
rule, written by the recalibrate command alone (`eval/recalibrate.py`), into a committed
Floors record per gate, and that record carries a fingerprint of everything the Floors
depend on. A gate whose fingerprint no longer matches refuses to compare anything.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

#: The message a gate fails with when its Floors record no longer matches what it measures
#: with. Reported on its own, never alongside a below-Floor failure.
STALE = "Floors stale: Recalibrate"

#: One committed Floors record per gate. Only `eval/recalibrate.py` writes them.
FLOORS_DIR = Path(__file__).resolve().parent / "floors"
RETRIEVAL_FLOORS_PATH = FLOORS_DIR / "retrieval.json"
GENERATION_FLOORS_PATH = FLOORS_DIR / "generation.json"

#: The retrieval rule's tolerance, in answerable cases: a Floor sits this many questions'
#: worth below the measurement. Retrieval is deterministic, so this is a tolerance for a
#: small real loss, not headroom for noise (story 89).
RETRIEVAL_TOLERATED_CASES = 2

#: The step a retrieval Floor is rounded down to.
RETRIEVAL_STEP = 0.005

#: The retrieval rule's name, as its record states it.
RETRIEVAL_RULE = (
    "measured − 2/n, rounded down to 0.005; n = answerable cases on the full Golden Set; "
    "Shipped Arm only"
)


def fingerprint(rows: list | dict) -> str:
    """A stable hash over already-canonicalized rows."""
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def round_down(value: float, step: float) -> float:
    """`value` rounded down to a multiple of `step`.

    The small tolerance keeps a value already on a step from rounding down past it.
    """
    return round(math.floor(value / step + 1e-9) * step, 6)


def retrieval_floor(measured: float, n: int) -> float:
    """The retrieval rule: the measurement less two cases' worth (2/n), rounded down to 0.005."""
    return round_down(measured - RETRIEVAL_TOLERATED_CASES / n, RETRIEVAL_STEP)


def retrieval_fingerprint(cases: list[dict]) -> str:
    """The retrieval Floors' fingerprint: each case's question, Relevant Phrases and
    `answerable`, sorted by case id.

    Nothing else a case carries can move a retrieval metric, so nothing else is hashed:
    a Required Fact edit must never stale the retrieval Floors (story 88).
    """
    return fingerprint(
        [
            {
                "question": case["question"],
                "relevantPhrases": sorted(case.get("relevant_phrases", [])),
                "answerable": case.get("answerable", True),
            }
            for case in sorted(cases, key=lambda case: case["id"])
        ]
    )


def retrieval_record(result: dict, cases: list[dict], commit: str) -> dict:
    """The retrieval Floors record for one Measured Run of the Shipped Arm.

    `result` is the Shipped Arm's result over the full Golden Set, as `evaluate_arm`
    returns it; `metrics` are the gated ones. n is the number of cases the metrics were
    averaged over, which is the answerable cases: Out-of-Scope Cases are never scored for
    retrieval. The record carries the inputs as well as the Floors, so anyone can redo
    the arithmetic and see that no Floor was chosen.
    """
    n = len(result["cases"])
    measured = {metric: round(value, 6) for metric, value in result["summary"].items()}
    return {
        "gate": "retrieval",
        "writtenBy": "eval/recalibrate.py retrieval — never edit by hand (ADR-0012)",
        "rule": RETRIEVAL_RULE,
        "arm": result["arm"],
        "inputs": {"n": n, "measured": measured},
        "floors": {metric: retrieval_floor(value, n) for metric, value in measured.items()},
        "fingerprint": retrieval_fingerprint(cases),
        "commit": commit,
    }


#: How many judged runs the generation rule is built for. Three understated the noise
#: (story 90), so the study is five, and the recalibrate command takes no other number.
GENERATION_RUNS = 5

#: The generation rule's name, as its record states it (ADR-0007's variance rule, ADR-0012).
GENERATION_RULE = (
    "five judged runs of the Shipped Arm over the full Golden Set; step = the smallest of "
    "0.005/0.01/0.02/0.05/0.1 no smaller than the metric's held-out range; Floor = lowest "
    "run − max(2 × range, step) over all cases, rounded down to the step"
)


def generation_instrument() -> dict:
    """What the generation gate measures with today: a change to any of it is a Recalibration.

    The Judge version, the wording of every Judge question, the Judge's filler cutoff
    (`FACTUAL_BELOW`), the model that splits sentences into claims and its reasoning
    effort, and the generation model and reasoning effort the gate answers with
    (production's defaults). The cutoff and the splitter's effort decide which sentences
    count and what claims get judged, so changing either is a new instrument (owner
    decision, 2026-10-11, #91). Imported here, not at the top, so the retrieval gate never
    loads the generation harness.
    """
    # From their source, not `eval.run_generation`, which imports `eval.run_eval` and so
    # this module: the cycle CodeQL flagged (py/cyclic-import).
    from app.config import DEFAULT_OPENAI_MODEL
    from app.llm import REASONING_EFFORT
    from eval.judge import (
        CONVEYS_QUESTION,
        DECLINES_QUESTION,
        FACTUAL_BELOW,
        FACTUAL_QUESTION,
        JEV_MODEL,
        SUPPORT_QUESTION,
    )
    from eval.splitter import SPLITTER_MODEL, SPLITTER_REASONING_EFFORT

    return {
        "judge": JEV_MODEL,
        "judgeQuestions": {
            "supports": SUPPORT_QUESTION,
            "factual": FACTUAL_QUESTION,
            "conveys": CONVEYS_QUESTION,
            "declines": DECLINES_QUESTION,
        },
        "splitter": SPLITTER_MODEL,
        "splitterReasoningEffort": SPLITTER_REASONING_EFFORT,
        "factualBelow": FACTUAL_BELOW,
        "generationModel": DEFAULT_OPENAI_MODEL,
        "reasoningEffort": REASONING_EFFORT,
    }


def generation_fingerprint(cases: list[dict], instrument: dict) -> str:
    """The generation Floors' fingerprint: each case's question, Required Facts and
    `answerable`, sorted by case id, plus the instrument (`generation_instrument`).

    Relevant Phrases are left out: a retrieval label repair must never force a paid
    generation study (story 88).
    """
    return fingerprint(
        {
            "cases": [
                {
                    "question": case["question"],
                    "requiredFacts": sorted(case.get("required_facts", [])),
                    "answerable": case.get("answerable", True),
                }
                for case in sorted(cases, key=lambda case: case["id"])
            ],
            "instrument": instrument,
        }
    )


def generation_record(
    runs: list[dict], cases: list[dict], instrument: dict, arm: str, commit: str
) -> dict:
    """The generation Floors record for five judged runs of the Shipped Arm over `cases`.

    Each published metric's rounding step comes from its own held-out range, and each
    gated metric's Floor from its range over every case (eval/variance.py). The record
    carries every run's values and range as well as the steps and Floors, so anyone can
    redo the arithmetic and see that no Floor was chosen.
    """
    from eval.variance import derive

    derived = derive(runs)

    def rounded(spread: dict) -> dict:
        return {
            "values": [round(value, 6) for value in spread["values"]],
            "range": round(spread["range"], 6),
        }

    return {
        "gate": "generation",
        "writtenBy": "eval/recalibrate.py generation — never edit by hand (ADR-0012)",
        "rule": GENERATION_RULE,
        "arm": arm,
        "inputs": {
            "runs": [
                {"generated": run.get("record", {}).get("commit"), "judged": run.get("commit")}
                for run in runs
            ],
            "holdout": {m: rounded(s) for m, s in derived["spread"]["holdout"].items()},
            "all": {m: rounded(derived["spread"]["all"][m]) for m in derived["floors"]},
        },
        "steps": derived["steps"],
        "floors": derived["floors"],
        "fingerprint": generation_fingerprint(cases, instrument),
        "commit": commit,
    }


def generation_staleness(record: dict, cases: list[dict], instrument: dict) -> str | None:
    """None when `record` describes `cases` (the whole Golden Set) and `instrument`;
    otherwise the gate's failure: "Floors stale: Recalibrate", and what to do about it.

    A record that predates fingerprints carries none, and is stale.
    """
    expected = generation_fingerprint(cases, instrument)
    if record["fingerprint"] == expected:
        return None
    found = (record["fingerprint"] or "none")[:19]
    return (
        f"{STALE}. The Golden Set or the generation instrument no longer matches the "
        f"generation Floors record (record {found}…, now {expected[:19]}…). Run the "
        "five-run spread study and `uv run --frozen python eval/recalibrate.py generation "
        "<five judged runs>` in this same change (ADR-0012)."
    )


def assert_generation_record_current(
    record: dict, golden_cases: list[dict], instrument: dict | None = None
) -> None:
    """The ordinary test suite's free check (story 87): fails with the gate's own
    "Floors stale: Recalibrate" before any paid run starts."""
    instrument = instrument if instrument is not None else generation_instrument()
    stale = generation_staleness(record, golden_cases, instrument)
    assert stale is None, stale


def write_record(record: dict, path: Path) -> None:
    """Write a Floors record. Only the recalibrate command calls this."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
