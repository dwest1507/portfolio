"""Turn a judged generation run into the published generation results document.

The retrieval document (`frontend/data/evalResults.json`, eval/publish.py) says whether
the right text reached the model. This one says how well the chatbot answered from it:
Fact Recall, Faithfulness, Decline accuracy and cost per answer, judged by the pinned
Judge (ADR-0007). It is a separate file because it is a separate measurement, made by a
paid, non-deterministic harness on a narrower trigger.

The document has two sections, each with its own provenance, because they come from
different runs: `shippedArm`, written by the generation gate on pushes to `main`, and
`comparison`, written by the manually triggered comparison run of Candidate Arms. A run
replaces only its own section, so rows from different runs never share one table.

Generation metrics move on an unchanged commit. Each is rounded to the step the spread
study derived for it, read from the committed generation Floors record
(eval/floors/generation.json, ADR-0012), and a section is rewritten only when a rounded
number, or what was measured, changed. So noise alone never produces a results commit.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from eval.generation import compare, score
from eval.publish import ARM_SPEC_BY_ID, CANDIDATE, _git_commit, _run_url, shipped_arm_id
from eval.recalibration import GENERATION_FLOORS_PATH, read_record

#: Bumped whenever a section gains or changes a measured field, so a document from
#: before the change is not compared with one from after.
SCHEMA_VERSION = 1

#: Where the document lands. Committed by CI; the portfolio page renders it.
GENERATION_RESULTS_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "data" / "generationResults.json"
)

#: The sections, each written by a different run.
SECTIONS = ("shippedArm", "comparison")

#: Only the held-out split is published: decisions are made on `dev` (ADR-0004).
PUBLISHED_SPLIT = "holdout"


def steps() -> dict[str, float]:
    """Each published metric's rounding step, from its own held-out run-to-run range in the
    spread study. They live in the generation Floors record beside the Floors, written by
    `eval/recalibrate.py generation` alone (ADR-0012), never in code.
    """
    return dict(read_record(GENERATION_FLOORS_PATH)["steps"])


#: OpenAI's standard prices in USD per million tokens, as (input, output), from
#: https://developers.openai.com/api/docs/pricing on 2026-10-11. Reasoning tokens bill as
#: output. Cached input is cheaper, so a cost from these is an upper bound.
PRICES_PER_MILLION = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
}

#: The fields that carry the Shipped Arm section's measurement. Everything else in a
#: section is provenance (when, which commit, which CI run), which moves on every run by
#: construction.
MEASURED_KEYS = (
    "split",
    "arm",
    "armLabel",
    "generationModel",
    "reasoningEffort",
    "judge",
    "splitter",
    "corpusChunks",
    "questions",
    "answerable",
    "outOfScope",
    "metrics",
    "steps",
    "costPerAnswerUsd",
)

#: The fields that carry the Comparison section's measurement: what every row shares,
#: and the rows, each with its metrics, cost and comparison with the Shipped Arm.
COMPARISON_MEASURED_KEYS = (
    "split",
    "shippedArm",
    "generationModel",
    "reasoningEffort",
    "judge",
    "splitter",
    "corpusChunks",
    "questions",
    "answerable",
    "outOfScope",
    "steps",
    "arms",
)

#: Each section's measured fields, by section name.
SECTION_MEASURED_KEYS = {"shippedArm": MEASURED_KEYS, "comparison": COMPARISON_MEASURED_KEYS}


def build_section(
    run: dict,
    *,
    arm: str,
    requested_model: str,
    reasoning_effort: str | None,
    corpus_chunks: int,
) -> dict:
    """One section of the document, from a judged run's held-out cases.

    `run` is what run_generation returns with a Judge. The run may cover every split
    (the gate judges the whole Golden Set); only its held-out cases are published.
    """
    spec = ARM_SPEC_BY_ID.get(arm)
    if spec is None:
        raise ValueError(f"Arm {arm!r} has no entry in ARM_SPECS, so it cannot be published.")
    cases = _held_out(run)["cases"]
    answerable = sum(case["answerable"] for case in cases)
    return {
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "commit": _git_commit(),
        "runUrl": _run_url(),
        "split": PUBLISHED_SPLIT,
        "arm": spec.id,
        "armLabel": spec.label,
        # The model the provider reports answering with, not the one requested.
        "generationModel": ", ".join(sorted({case["model"] for case in cases})),
        "reasoningEffort": reasoning_effort,
        "judge": run["judge"],
        "splitter": run["splitter"],
        "corpusChunks": corpus_chunks,
        "questions": len(cases),
        "answerable": answerable,
        "outOfScope": len(cases) - answerable,
        "metrics": _rounded_metrics(cases),
        "steps": steps(),
        "costPerAnswerUsd": cost_per_answer(cases, requested_model),
    }


def build_comparison_section(
    runs: dict[str, dict],
    *,
    requested_model: str,
    reasoning_effort: str | None,
    corpus_chunks: int,
) -> dict:
    """The Comparison section, from a judged run per Candidate Arm (eval/compare_arms.py).

    One row per Arm, in registry order, each with its held-out metrics and cost, and,
    for every Arm but the Shipped Arm, the pairs it won and lost against the Shipped Arm
    on each metric ADR-0009's rule reads, with ADR-0006's outcome. The runs cover every
    split; only held-out cases are published, so the outcomes here confirm a decision
    made on `dev` rather than make it.
    """
    shipped = shipped_arm_id()
    unknown = [arm for arm in runs if arm not in ARM_SPEC_BY_ID]
    if unknown:
        raise ValueError(f"Arm(s) {', '.join(unknown)} have no entry in ARM_SPECS.")
    reference = [arm for arm in runs if ARM_SPEC_BY_ID[arm].eligibility != CANDIDATE]
    if reference:
        raise ValueError(
            f"Reference Arm(s) {', '.join(reference)} are never run through generation "
            "(ADR-0007), so they are not published."
        )
    if shipped not in runs:
        raise ValueError(f"The comparison needs the Shipped Arm, {shipped}, to compare with.")

    held_out = {arm: _held_out(run) for arm, run in runs.items()}
    baseline = held_out[shipped]
    rows = []
    for spec in (ARM_SPEC_BY_ID[arm] for arm in ARM_SPEC_BY_ID if arm in runs):
        run = held_out[spec.id]
        rows.append(
            {
                "arm": spec.id,
                "armLabel": spec.label,
                "eligibility": spec.eligibility,
                "shipped": spec.shipped,
                "metrics": _rounded_metrics(run["cases"]),
                "costPerAnswerUsd": cost_per_answer(run["cases"], requested_model),
                "vsShipped": None if spec.shipped else compare(run, baseline),
            }
        )
    cases = baseline["cases"]
    answerable = sum(case["answerable"] for case in cases)
    return {
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "commit": _git_commit(),
        "runUrl": _run_url(),
        "split": PUBLISHED_SPLIT,
        "shippedArm": shipped,
        "generationModel": ", ".join(
            sorted({case["model"] for run in held_out.values() for case in run["cases"]})
        ),
        "reasoningEffort": reasoning_effort,
        "judge": runs[shipped]["judge"],
        "splitter": runs[shipped]["splitter"],
        "corpusChunks": corpus_chunks,
        "questions": len(cases),
        "answerable": answerable,
        "outOfScope": len(cases) - answerable,
        "steps": steps(),
        "arms": rows,
    }


def _held_out(run: dict) -> dict:
    return {**run, "cases": [case for case in run["cases"] if case["split"] == PUBLISHED_SPLIT]}


def _rounded_metrics(cases: list[dict]) -> dict:
    metrics = score(cases)
    return {m: round_to_step(metrics[m], step) for m, step in steps().items()}


def round_to_step(value: float | None, step: float) -> float | None:
    """`value` to the nearest multiple of `step`, halves up. None stays None.

    Decimal, because binary floats put halves on the wrong side: 0.75 / 0.1 is
    7.4999999999999991 as a float, which would round 0.75 down to 0.7.
    """
    if value is None:
        return None
    steps = (Decimal(str(value)) / Decimal(str(step))).quantize(Decimal(1), ROUND_HALF_UP)
    return float(steps * Decimal(str(step)))


def cost_per_answer(cases: list[dict], requested_model: str) -> float | None:
    """Mean billed USD per answer, to one significant figure.

    Billed tokens move with every reworded answer, so the cost is published only to the
    digit that survives that noise.
    """
    if requested_model not in PRICES_PER_MILLION:
        raise ValueError(
            f"No price is recorded for {requested_model!r}; add it to PRICES_PER_MILLION "
            "rather than publish a cost nothing priced."
        )
    if not cases:
        return None
    input_price, output_price = PRICES_PER_MILLION[requested_model]
    total = sum(
        case["usage"]["prompt_tokens"] * input_price
        + case["usage"]["completion_tokens"] * output_price
        for case in cases
    )
    return float(f"{total / len(cases) / 1_000_000:.1g}")


def _measurement(name: str, section: dict | None) -> dict | None:
    if section is None:
        return None
    return {k: section.get(k) for k in SECTION_MEASURED_KEYS[name]}


def _empty_document() -> dict:
    return {"schemaVersion": SCHEMA_VERSION, **dict.fromkeys(SECTIONS)}


def write_section(name: str, section: dict, path: Path) -> tuple[dict, bool]:
    """Publish `section` as `name` unless it measures exactly what the file already holds.

    Returns the document now on disk and whether it was written. The other section is
    left exactly as it was, provenance included.

    As for retrieval (eval/publish.py, write_results_document), a section carrying a
    `runUrl` replaces one without, even when nothing measured moved, so a local run's
    unattested provenance is not what the page keeps forever. A file that cannot be
    parsed, or that has another schema version, is replaced.
    """
    if name not in SECTIONS:
        raise ValueError(f"Unknown section {name!r}; expected one of {', '.join(SECTIONS)}.")

    document = _empty_document()
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict) and existing.get("schemaVersion") == SCHEMA_VERSION:
            document = existing
            current = existing.get(name)
            attests = current is not None and not current.get("runUrl") and bool(section["runUrl"])
            if not attests and _measurement(name, current) == _measurement(name, section):
                return existing, False

    document = {**document, name: section}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return document, True
