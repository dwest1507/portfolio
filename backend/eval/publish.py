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

# Bumped to 2 when the document gained `split`: a v1 file records a run over the whole
# golden set, which is not the same measurement as a v2 held-out run and must not be
# compared with one.
SCHEMA_VERSION = 2

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
        technical=(
            "BM25 over stemmed, stopword-filtered terms. Needs no embedding model, which "
            "is why the production image ships none. Matches RAGPipeline.retrieve."
        ),
        shipped=True,
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
            "Cross-encoder re-ranking of the fused candidates: hybrid_search over 2×k "
            "candidates → cross-encoder narrows to k. Shipped until the harness measured "
            "it against the keyword arm."
        ),
    ),
    Arm(
        id="bm25+rerank",
        label="Keyword, then re-ranked",
        description=(
            "Takes the keyword results alone and has the slower second model re-read them "
            "against the question, with no meaning-based search involved at all."
        ),
        technical=(
            "Cross-encoder re-ranking of BM25 candidates. The arm that answers whether the "
            "dense stage contributes anything the re-ranker cannot recover on its own."
        ),
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
    split: str = "all",
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
        "split": split,
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
    "split",
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

    The one exception to that rule is a document with no `runUrl`. Skipping the rewrite
    preserves provenance, which is right for a CI run replacing a CI run and wrong for the
    first CI run replacing a local one: a developer's `--publish` records a bare commit and
    no run link, and if the numbers do not move, that unattested provenance is what the
    public page keeps forever. So a run that carries a `runUrl` may replace one that does
    not, even when nothing measured changed. It happens at most once per published
    measurement — the replacement has a `runUrl` of its own — so the "nothing to commit"
    branch stays reachable.

    A file that cannot be parsed is treated as absent and overwritten; a corrupt
    published document is not worth preserving.
    """
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        # True when a CI-attested run is replacing a local one; see the docstring.
        attests = existing is not None and not existing.get("runUrl") and bool(document["runUrl"])
        if (
            existing is not None
            and not attests
            and _measurement(existing) == _measurement(document)
        ):
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
    """The arm scoring highest on `metric`. Ties resolve to the earliest arm listed.

    Use `leading_arm_ids` wherever a tie should be visible. The shipped arm is first in
    ARM_SPECS, so a positional tie-break here silently resolves every tie in production's
    favour — which is the one direction this write-up cannot afford to round.
    """
    return max(document["arms"], key=lambda a: a["metrics"].get(metric, float("-inf")))


def leading_arm_ids(document: dict, metric: str) -> list[str]:
    """Every arm tied for the best score on `metric`, in listed order.

    A tie is a real result and gets rendered as one. `bm25` and `bm25+rerank` currently
    both take hit@5 = 1.000; highlighting only the first would report the arm that ships
    as beating an arm it merely matched.
    """
    best = leading_arm(document, metric)["metrics"].get(metric, float("-inf"))
    return [a["id"] for a in document["arms"] if a["metrics"].get(metric) == best]


def verdict_line(document: dict) -> str:
    """One sentence naming the shipped arm and the arm that currently leads.

    Generated rather than written so it cannot drift from the table above it. When the
    shipped configuration is also the leading one, it says so instead of manufacturing a
    contrast.
    """
    metric = document["gatingMetric"]
    shipped = next((a for a in document["arms"] if a["shipped"]), None)
    leader = leading_arm(document, metric)
    leaders = leading_arm_ids(document, metric)

    if shipped is None:
        return (
            f"{leader['label']} leads on {metric} "
            f"({leader['metrics'][metric]:.3f}). No arm is flagged as shipped."
        )

    if shipped["id"] in leaders:
        # A tie is named rather than rounded into a win. The shipped arm is listed
        # first, so "leads" would otherwise be how every tie reads.
        others = [a["label"] for a in document["arms"] if a["id"] in leaders and a is not shipped]
        score = f"{shipped['metrics'][metric]:.3f}"
        if not others:
            return f"Production runs {shipped['label']}, which also leads on {metric} ({score})."
        # Arm labels contain commas, so the tied names go last rather than mid-sentence.
        return (
            f"Production runs {shipped['label']}, tied for the lead on {metric} "
            f"({score}) with {', '.join(others)}."
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

    # Every arm tied for a column's best is bolded, not just the first one listed —
    # "Best score per column in bold" has to mean it.
    bests = {m: set(leading_arm_ids(document, m)) for m in metrics}

    rows = []
    for arm in document["arms"]:
        cells = []
        for m in metrics:
            value = f"{arm['metrics'][m]:.3f}"
            cells.append(f"**{value}**" if arm["id"] in bests[m] else value)
        shipped = " _(shipped)_" if arm["shipped"] else ""
        rows.append(f"| `{arm['id']}`{shipped} | " + " | ".join(cells) + " |")

    split = document.get("split", "all")
    described = (
        f"{document['goldenQuestions']} golden questions"
        if split == "all"
        else f"the {document['goldenQuestions']} held-out golden questions"
        if split == "holdout"
        else f"{document['goldenQuestions']} {split} golden questions"
    )
    provenance = (
        f"Measured on {document['corpusChunks']} chunks and {described} at `{document['commit']}`"
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
