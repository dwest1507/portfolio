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


def fingerprint(rows: list) -> str:
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


def write_record(record: dict, path: Path) -> None:
    """Write a Floors record. Only the recalibrate command calls this."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
