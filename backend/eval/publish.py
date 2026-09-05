"""Turn a measured run into the artefacts that publish it.

The public write-up and `docs/evaluation.md` both report retrieval metrics. Neither
transcribes them by hand: CI runs the harness, writes the measured run to
`frontend/data/evalResults.json`, regenerates the table in `docs/evaluation.md`, and
commits both. See docs/adr/0001-generated-eval-results.md.

Keeping this separate from run_eval.py means the document shape, the markdown rendering,
and the verdict can be tested without loading a pipeline or downloading model weights.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

BEGIN_MARKER = "<!-- eval:begin -->"
END_MARKER = "<!-- eval:end -->"


@dataclass(frozen=True)
class Arm:
    """One retrieval configuration, and how to describe it to each audience.

    An arm's identity and its descriptions live together because they change together:
    adding or retiring an arm is a single edit here, and the public page picks up the
    new row with no frontend change.
    """

    id: str
    label: str
    #: Written for a non-specialist reader of the portfolio page.
    description: str
    #: The implementation detail that description deliberately leaves out.
    technical: str
    #: True for the one arm that mirrors what RAGPipeline.retrieve actually runs.
    shipped: bool = False


ARM_SPECS: tuple[Arm, ...] = (
    Arm(
        id="bm25",
        label="Keyword only",
        description=(
            "Matches the words in the question against the words in the document, with no "
            "machine learning involved."
        ),
        technical="BM25 over stemmed, stopword-filtered terms. Needs no embedding model.",
    ),
    Arm(
        id="dense",
        label="Meaning only",
        description=(
            "Matches on meaning rather than wording, so it can find a passage that answers "
            "the question without repeating any of its words."
        ),
        technical="FAISS inner-product search over normalized all-mpnet-base-v2 embeddings.",
    ),
    Arm(
        id="hybrid",
        label="Both combined",
        description="Runs both of the above and merges their rankings into one list.",
        technical="Weighted reciprocal-rank fusion of the sparse and dense rankings.",
    ),
    Arm(
        id="rerank",
        label="Both combined, then re-ranked",
        description=(
            "Takes the merged list and has a second, slower model re-read each candidate "
            "against the question to put the best one first."
        ),
        technical=(
            "Cross-encoder re-ranking of the fused candidates. Matches "
            "RAGPipeline.retrieve: hybrid_search(candidates_k) → rerank(top_k)."
        ),
        shipped=True,
    ),
)

ARMS: tuple[str, ...] = tuple(a.id for a in ARM_SPECS)

ARM_SPEC_BY_ID: dict[str, Arm] = {a.id: a for a in ARM_SPECS}


def shipped_arm_id() -> str:
    """The arm mirroring production. Exactly one arm carries the flag; see tests."""
    shipped = [a.id for a in ARM_SPECS if a.shipped]
    if len(shipped) != 1:
        raise ValueError(f"Expected exactly one shipped arm, found {shipped}.")
    return shipped[0]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _git_commit() -> str:
    """Short SHA of the commit being measured.

    Prefers GITHUB_SHA so a CI run records the commit it checked out rather than
    whatever the runner's git state happens to say.
    """
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:7]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError, FileNotFoundError:
        return "unknown"


def _run_url() -> str | None:
    """Link to the CI job that produced the numbers, when there is one."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


# ---------------------------------------------------------------------------
# The measured-run document
# ---------------------------------------------------------------------------


def build_results_document(
    results: list[dict],
    *,
    corpus_chunks: int,
    golden_questions: int,
    top_k: int,
    gating_metric: str,
) -> dict:
    """Assemble the published measured run from raw per-arm harness output.

    Metric names travel with the document rather than being assumed by the reader, so a
    run at a different cutoff publishes hit@10 without a frontend change.
    """
    metric_names = list(results[0]["summary"].keys()) if results else []

    arms = []
    for r in results:
        spec = ARM_SPEC_BY_ID.get(r["arm"])
        if spec is None:
            raise ValueError(
                f"Arm {r['arm']!r} has no entry in ARM_SPECS, so it cannot be published. "
                "Add one alongside its implementation."
            )
        arms.append(
            {
                "id": spec.id,
                "label": spec.label,
                "description": spec.description,
                "technical": spec.technical,
                "shipped": spec.shipped,
                "metrics": {m: round(r["summary"][m], 4) for m in metric_names},
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "commit": _git_commit(),
        "runUrl": _run_url(),
        "corpusChunks": corpus_chunks,
        "goldenQuestions": golden_questions,
        "topK": top_k,
        "gatingMetric": gating_metric,
        "metricNames": metric_names,
        "arms": arms,
    }


#: The fields that carry the measurement. Everything outside this set is provenance —
#: when it changed, and which run produced it — which moves on every run by construction.
MEASURED_KEYS = (
    "schemaVersion",
    "corpusChunks",
    "goldenQuestions",
    "topK",
    "gatingMetric",
    "metricNames",
    "arms",
)


def _measurement(document: dict) -> dict:
    return {k: document.get(k) for k in MEASURED_KEYS}


def write_results_document(document: dict, path: Path) -> tuple[dict, bool]:
    """Publish `document` unless it measures exactly what the file already holds.

    Returns the document now on disk and whether it was written.

    The rewrite is conditional because `generatedAt` and `commit` change on every run
    whether or not a single metric moved. Writing unconditionally made the publishing
    job's "results unchanged; nothing to commit" branch unreachable: the file always
    differed, so every push to main landed a commit asserting a re-measurement that had
    found nothing. Comparing on MEASURED_KEYS alone means an unchanged run leaves the
    file — provenance included — exactly as it was, and the commit history records the
    runs where a number actually moved.

    A file that cannot be parsed is treated as absent and overwritten; a corrupt
    published document is not worth preserving.
    """
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if existing is not None and _measurement(existing) == _measurement(document):
            return existing, False

    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False: the arm descriptions contain "→", and \u2192 in a published
    # JSON file is noise for anyone reading it.
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return document, True


# ---------------------------------------------------------------------------
# Derived claims
# ---------------------------------------------------------------------------


def leading_arm(document: dict, metric: str) -> dict:
    """The arm scoring highest on `metric`. Ties resolve to the earliest arm listed."""
    return max(document["arms"], key=lambda a: a["metrics"].get(metric, float("-inf")))


def verdict_line(document: dict) -> str:
    """One sentence naming the shipped arm and the arm that currently leads.

    Generated rather than written so it cannot drift from the table above it. When the
    shipped configuration is also the leading one, it says so instead of manufacturing a
    contrast.
    """
    metric = document["gatingMetric"]
    shipped = next((a for a in document["arms"] if a["shipped"]), None)
    leader = leading_arm(document, metric)

    if shipped is None:
        return (
            f"{leader['label']} leads on {metric} "
            f"({leader['metrics'][metric]:.3f}). No arm is flagged as shipped."
        )

    if shipped["id"] == leader["id"]:
        return (
            f"Production runs {shipped['label']}, which also leads on {metric} "
            f"({shipped['metrics'][metric]:.3f})."
        )

    return (
        f"Production runs {shipped['label']}. On the current corpus, {leader['label']} "
        f"leads on {metric} ({leader['metrics'][metric]:.3f} vs "
        f"{shipped['metrics'][metric]:.3f})."
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def metric_label(metric: str) -> str:
    """Display name for a metric column. Mirrors metricLabel() in data/evalResults.ts."""
    return "MRR" if metric == "mrr" else metric


def render_markdown(document: dict) -> str:
    """The generated block for docs/evaluation.md: provenance, table, verdict."""
    metrics = document["metricNames"]
    header = "| Arm | " + " | ".join(metric_label(m) for m in metrics) + " |"
    align = "|-----|" + "|".join(["---------:"] * len(metrics)) + "|"

    bests = {m: leading_arm(document, m)["id"] for m in metrics}

    rows = []
    for arm in document["arms"]:
        cells = []
        for m in metrics:
            value = f"{arm['metrics'][m]:.3f}"
            cells.append(f"**{value}**" if bests[m] == arm["id"] else value)
        shipped = " _(shipped)_" if arm["shipped"] else ""
        rows.append(f"| `{arm['id']}`{shipped} | " + " | ".join(cells) + " |")

    provenance = (
        f"Measured on {document['corpusChunks']} chunks and "
        f"{document['goldenQuestions']} golden questions at `{document['commit']}`"
    )
    if document["runUrl"]:
        provenance += f" — [CI run]({document['runUrl']})"
    provenance += "."

    return "\n".join(
        [
            "<!-- Generated by eval/publish.py. Do not edit by hand; edits are overwritten. -->",
            "",
            provenance,
            "",
            header,
            align,
            *rows,
            "",
            f"**{verdict_line(document)}**",
            "",
            "Best score per column in bold.",
        ]
    )


def update_markdown_block(path: Path, document: dict) -> bool:
    """Replace the marked block in `path`. Returns True if the file changed.

    Missing markers are an error rather than an append: silently adding a second table to
    a document that already has one is worse than failing.
    """
    text = path.read_text(encoding="utf-8")
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"{path} is missing the {BEGIN_MARKER} / {END_MARKER} markers that delimit "
            "the generated results block."
        )

    updated = (
        text[: start + len(BEGIN_MARKER)] + "\n" + render_markdown(document) + "\n" + text[end:]
    )
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True
