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
import math
import os
import random
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Bumped to 2 when the document gained `split`: a v1 file records a run over the whole
# golden set, which is not the same measurement as a v2 held-out run and must not be
# compared with one.
# Bumped to 3 when the document gained `categories` and per-arm `byCategory` breakdowns
# to segment in-vocabulary direct queries from paraphrases and conceptual questions.
# Bumped to 4 when each arm gained `vsShipped` — questions won and lost against the
# shipped arm and the sign-test outcome (ADR-0006) — and `mrrInterval`. A v3 verdict named
# whichever arm scored highest; a v4 verdict names only differences beyond sampling noise.
SCHEMA_VERSION = 4

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
# Comparison against the shipped arm
# ---------------------------------------------------------------------------

#: An arm is called ahead of or behind the shipped arm only below this p-value.
SIGNIFICANCE = 0.05


def sign_test_p(won: int, lost: int) -> float:
    """Exact two-sided sign test (McNemar's exact test) on the discordant questions.

    Under the null hypothesis that neither arm is better, each question only one of them
    hit is a fair coin toss between them. The p-value is the probability of a split at
    least as lopsided as `won`/`lost`.
    """
    n = won + lost
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(won, lost) + 1)) / 2**n
    return min(1.0, 2 * tail)


def compare_with_shipped(cases: list[dict], shipped_cases: list[dict], metric: str) -> dict:
    """Questions this arm won and lost against the shipped arm, and whether it matters.

    Only the questions the two arms disagree on carry information about which is better
    (ADR-0006): a question both hit, or both missed, is the same for either arm. The split
    of the rest is called `ahead` or `behind` only when it is too lopsided to be chance;
    otherwise the arms are `indistinguishable` on this sample.
    """
    shipped_hits = {c["id"]: bool(c[metric]) for c in shipped_cases}
    won = lost = 0
    for case in cases:
        mine, theirs = bool(case[metric]), shipped_hits.get(case["id"])
        if theirs is None or mine == theirs:
            continue
        if mine:
            won += 1
        else:
            lost += 1

    if sign_test_p(won, lost) >= SIGNIFICANCE:
        outcome = "indistinguishable"
    else:
        outcome = "ahead" if won > lost else "behind"
    return {"won": won, "lost": lost, "outcome": outcome}


#: Resamples per bootstrap interval, and the seed that makes a re-run reproduce it.
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0


def bootstrap_interval(values: list[float]) -> list[float] | None:
    """95% percentile-bootstrap interval for the mean of `values`.

    Seeded, so the same per-question outcomes always give the same interval: an
    interval that moved on every run would rewrite docs/evaluation.md with nothing
    re-measured. Published in docs/evaluation.md only, never on the page (ADR-0006).
    """
    if not values:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(BOOTSTRAP_RESAMPLES))
    lo = means[int(0.025 * BOOTSTRAP_RESAMPLES)]
    hi = means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    return [round(lo, 4), round(hi, 4)]


# ---------------------------------------------------------------------------
# The measured-run document
# ---------------------------------------------------------------------------


def build_results_document(
    results: list[dict],
    corpus_chunks: int,
    golden_questions: int,
    top_k: int,
    gating_metric: str,
    split: str = "all",
    category_counts: dict[str, int] | None = None,
) -> dict:
    """Assemble the published measured run from raw per-arm harness output.

    Metric names travel with the document rather than being assumed by the reader, so a
    run at a different cutoff publishes hit@10 without a frontend change.
    """
    metric_names = list(results[0]["summary"].keys()) if results else []
    categories = sorted({cat for r in results for cat in r.get("by_category", {})})

    if category_counts is None:
        category_counts = {}
        if results and "cases" in results[0]:
            for c in results[0]["cases"]:
                cat = c.get("category")
                if cat:
                    category_counts[cat] = category_counts.get(cat, 0) + 1

    shipped_cases = next(
        (r.get("cases", []) for r in results if r["arm"] == shipped_arm_id()), None
    )

    arms = []
    for r in results:
        spec = ARM_SPEC_BY_ID.get(r["arm"])
        if spec is None:
            raise ValueError(
                f"Arm {r['arm']!r} has no entry in ARM_SPECS, so it cannot be published. "
                "Add one alongside its implementation."
            )
        by_category = {}
        for cat in categories:
            if cat in r.get("by_category", {}):
                by_category[cat] = {
                    m: round(r["by_category"][cat][m], 4)
                    for m in metric_names
                    if m in r["by_category"][cat]
                }
        compared = compared_by_category = None
        if not spec.shipped and shipped_cases is not None:
            cases = r.get("cases", [])
            compared = compare_with_shipped(cases, shipped_cases, gating_metric)
            compared_by_category = {
                cat: compare_with_shipped(
                    [c for c in cases if c.get("category") == cat], shipped_cases, gating_metric
                )
                for cat in sorted({c["category"] for c in cases if c.get("category")})
            }
        arms.append(
            {
                "id": spec.id,
                "label": spec.label,
                "description": spec.description,
                "technical": spec.technical,
                "shipped": spec.shipped,
                "metrics": {m: round(r["summary"][m], 4) for m in metric_names},
                "byCategory": by_category,
                "mrrInterval": bootstrap_interval([c["mrr"] for c in r.get("cases", [])]),
                "vsShipped": compared,
                "vsShippedByCategory": compared_by_category,
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
        "categories": categories,
        "categoryCounts": category_counts,
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
    "categories",
    "categoryCounts",
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


def sample_phrase(document: dict) -> str:
    """The measured questions in a phrase: "the 33 held-out questions"."""
    n, split = document["goldenQuestions"], document.get("split", "all")
    noun = "question" if n == 1 else "questions"
    if split == "all":
        return f"all {n} {noun}"
    if split == "holdout":
        return f"the {n} held-out {noun}"
    return f"the {n} {split} {noun}"


def verdict_line(document: dict) -> str:
    """One sentence placing every arm against the shipped arm on the gating metric.

    Generated rather than written so it cannot drift from the table above it. An arm is
    named ahead or behind only when the questions it disagrees with the shipped arm on are
    too lopsided to be sampling noise (ADR-0006); otherwise the sentence says no arm is
    distinguishable and gives the sample size that makes that the usual answer.
    """
    metric = document["gatingMetric"]
    shipped = next((a for a in document["arms"] if a["shipped"]), None)
    if shipped is None:
        return "No arm is flagged as shipped, so no arm is compared against production."

    opening = f"Production runs {shipped['label']}."
    others = [a for a in document["arms"] if a is not shipped]
    if not others:
        return f"{opening} No other arm was measured."

    def named(outcome: str) -> list[str]:
        # The won/lost counts sit in parentheses straight after each label, which also
        # keeps a label containing a comma from reading as two arms.
        return [
            f"{a['label']} (won {a['vsShipped']['won']}, lost {a['vsShipped']['lost']})"
            for a in others
            if (a.get("vsShipped") or {}).get("outcome") == outcome
        ]

    ahead, behind = named("ahead"), named("behind")
    sample = f"Across {sample_phrase(document)}"
    if not ahead and not behind:
        return f"{opening} {sample}, no other arm is distinguishable from it on {metric}."

    clauses = []
    if ahead:
        clauses.append(f"{_join(ahead)} {_be(ahead)} distinguishably ahead of it on {metric}")
    if behind:
        where = "" if ahead else f" on {metric}"
        lead = "" if ahead else "distinguishably "
        clauses.append(f"{_join(behind)} {_be(behind)} {lead}behind it{where}")
    return f"{opening} {sample}, {', and '.join(clauses)}."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _be(items: list[str]) -> str:
    return "is" if len(items) == 1 else "are"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def metric_label(metric: str) -> str:
    """Display name for a metric column. Mirrors metricLabel() in data/evalResults.ts."""
    return "MRR" if metric == "mrr" else metric


def render_markdown(document: dict) -> str:
    """The generated block for docs/evaluation.md: provenance, table, verdict."""
    metrics = document["metricNames"]
    header = (
        "| Arm | "
        + " | ".join(metric_label(m) for m in metrics)
        + " | MRR 95% CI | vs shipped (won / lost) |"
    )
    align = "|-----|" + "|".join(["---------:"] * (len(metrics) + 2)) + "|"

    # Every arm tied for a column's best is bolded, not just the first one listed —
    # "Best score per column in bold" has to mean it.
    bests = {m: set(leading_arm_ids(document, m)) for m in metrics}

    rows = []
    for arm in document["arms"]:
        cells = []
        for m in metrics:
            value = f"{arm['metrics'][m]:.3f}"
            cells.append(f"**{value}**" if arm["id"] in bests[m] else value)
        interval = arm.get("mrrInterval")
        cells.append(f"{interval[0]:.3f}–{interval[1]:.3f}" if interval else "—")
        vs = arm.get("vsShipped")
        cells.append(f"{vs['won']} / {vs['lost']}" if vs else "—")
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
