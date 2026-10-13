"""Retrieval evaluation harness for the portfolio chatbot.

Answers the question the pipeline could not previously answer: does retrieval
actually work, and do the weights and stage choices earn their keep?

Runs the golden question set through each retrieval arm and reports recall@k,
MRR, and nDCG@k so the arms can be compared directly:

    bm25         keyword only (no embedding model required)
    dense        FAISS semantic only
    hybrid       weighted reciprocal-rank fusion of both
    rerank       hybrid candidates re-ordered by the cross-encoder
    bm25+rerank  keyword candidates re-ordered by the cross-encoder, no dense stage

and three Candidate Arms that run their models on ONNX Runtime instead of torch, so
production could ship them (ADR-0009). The five above are Reference Arms:

    onnx-dense           `dense` with the same embedding model on ONNX Runtime
    onnx-hybrid          `hybrid` with onnx-dense as its dense stage
    bm25+onnx-rerank-20  20 keyword candidates re-ordered by an ONNX cross-encoder

Usage:
    uv run python eval/run_eval.py                      # all arms
    uv run python eval/run_eval.py --arms bm25          # no model download
    uv run python eval/run_eval.py --check              # exit 1 if stale or below a Floor
    uv run python eval/run_eval.py --json results.json  # machine-readable output
    uv run python eval/run_eval.py --publish            # refresh the published results

A chunk counts as relevant when any of the case's `relevant_phrases` appears in
its text beginning at the start of a word (`no` does not match "know"; `mentor`
does match "mentoring"). Labelling by phrase rather than chunk ID keeps the golden
set valid when the corpus is re-chunked.

The golden set is split into `dev` and `holdout` portions (see golden_set.json).
Decide things on `dev`; `holdout` is what gets published, so a published number is
never a number something was tuned against. `--split` selects which portion runs.

Each arm is also timed: warm p50/p95 per query and the time to load its indexes and
models. The CLI and --json output show those raw timings; --publish records only their
Latency Bands (see publish.latency_band).

Out-of-Scope Cases (`answerable: false`) are questions the corpus cannot answer. They
exist for the generation eval and are skipped here by that label, then counted in the
summary line, rather than tripping the "matches no chunk" error.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.inputs import retrieval_inputs_fingerprint  # (needs the sys.path line above)
from eval.publish import (
    ARMS,
    build_results_document,
    latency_band,
    shipped_arm_id,
    update_markdown_block,
    verdict_line,
    write_results_document,
)
from eval.recalibration import (
    RETRIEVAL_FLOORS_PATH,
    STALE,
    read_record,
    retrieval_fingerprint,
)

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.json"

# Where a published run lands. Both are committed by CI; see
# docs/adr/0001-generated-eval-results.md.
RESULTS_PATH = REPO_ROOT / "frontend" / "data" / "evalResults.json"
EVALUATION_DOC_PATH = REPO_ROOT / "docs" / "evaluation.md"

# Regression Floors for `--check` live in eval/floors/retrieval.json, not here. Only
# `eval/recalibrate.py retrieval` writes them, by a fixed rule, when the Golden Set or the
# instrument changes (ADR-0012). They are Floors, never targets: tuning a parameter until
# a Floor is cleared is fitting to the Golden Set. See docs/evaluation.md.
# Floors are keyed by metric name at the default cutoff. `--check` is only meaningful
# at that cutoff, which check_floors() enforces rather than silently comparing a hit@20
# against a Floor derived for hit@5.
DEFAULT_TOP_K = 5

# The metric the published verdict is decided on: "did any grounding text reach the
# model?" is what determines whether the LLM can answer at all.
GATING_METRIC = f"hit@{DEFAULT_TOP_K}"

# The metrics the gate defends with a Floor, at the default cutoff. Deliberately not
# recall@5: several Golden cases have more than five relevant chunks, so their recall@5
# is capped below 1.0 by construction. hit@5 ("did any grounding text reach the model?")
# decides whether the LLM can answer, and MRR how far up the list it landed.
GATED_METRICS = (GATING_METRIC, "mrr")

# Golden-set portions. "all" is not a third portion, it is both of them together.
SPLITS = ("all", "dev", "holdout")

# Query Categories: lexical and conceptual relationship of questions to the Corpus.
VALID_CATEGORIES = ("direct", "paraphrase", "conceptual")

# Case Origins: whether a case was written by hand or derived from a real visitor's
# question. A case without one was authored.
VALID_ORIGINS = ("authored", "visitor")

# The two splits that are not interchangeable, and why each is what it is.
#
# `--publish` reports the HELD-OUT portion. Nothing is ever chosen against those
# questions, so the number on the public page is a measurement rather than the score
# of whatever configuration happened to win on the questions it was picked with.
# It is a smaller sample and therefore a coarser number — 22 questions move hit@5 in
# steps of ~0.045 — which is the price of it meaning what it says.
#
# `--check` gates the WHOLE set. The floors are regression detection, not a target
# anything is tuned toward, so there is no leakage to protect against and the larger
# sample makes them less twitchy.
PUBLISHED_SPLIT = "holdout"
GATED_SPLIT = "all"

# Only the SHIPPED arm is gated, and it is looked up rather than named so the gate
# follows production when the shipped arm changes.
#
# Every other arm is measured and published as a baseline for comparison, not defended
# as a quality bar. A Floor is there to stop a change degrading what a visitor is
# actually served, and nothing is served by an arm production does not run (ADR-0004).
#
# `--check` names every ungated arm explicitly, and a run that gates nothing is a
# failure, so this cannot quietly become a gate over nothing.


def metric_names_for(top_k: int) -> list[str]:
    return [f"recall@{top_k}", f"hit@{top_k}", "mrr", f"ndcg@{top_k}"]


# ---------------------------------------------------------------------------
# Relevance judgement
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace so phrases match across line wrapping."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """A phrase matches where it begins a word, and may end mid-word.

    The start is anchored so `no` cannot match inside "know" and `R:` cannot match
    inside "ER:". The end is left open so a label can name a stem: `mentor` still
    matches "mentoring" and `rate limit` still matches "rate limiting".
    """
    return re.compile(r"(?<![a-z0-9])" + re.escape(_normalize(phrase)))


def is_relevant(chunk_text: str, phrases: list[str]) -> bool:
    haystack = _normalize(chunk_text)
    return any(_phrase_pattern(p).search(haystack) for p in phrases)


def relevant_ids(chunks: list[dict], phrases: list[str]) -> set[int]:
    return {i for i, c in enumerate(chunks) if is_relevant(c["text"], phrases)}


# The largest share of the Corpus a single Relevant Phrase may mark relevant. Above it
# the phrase hands every arm a hit whatever it retrieved, which is a labelling defect
# rather than a label. A broad phrase that is nonetheless correct (the current
# employer's name) goes on the allow-list in golden_set.json rather than raising this.
MAX_PHRASE_SHARE = 0.15


def overbroad_phrases(chunks: list[dict], cases: list[dict], allowed: list[str]) -> list[dict]:
    """Every Relevant Phrase matching more than MAX_PHRASE_SHARE of `chunks`, unless allowed.

    Each finding names the phrase, its share of the Corpus, and the cases that use it.
    """
    allowed_normalized = {_normalize(p) for p in allowed}
    cases_by_phrase: dict[str, list[str]] = {}
    for case in cases:
        for phrase in case.get("relevant_phrases", []):
            cases_by_phrase.setdefault(phrase, []).append(case["id"])

    findings = []
    for phrase, case_ids in cases_by_phrase.items():
        if _normalize(phrase) in allowed_normalized:
            continue
        share = len(relevant_ids(chunks, [phrase])) / len(chunks)
        if share > MAX_PHRASE_SHARE:
            findings.append({"phrase": phrase, "share": share, "cases": case_ids})
    return findings


# ---------------------------------------------------------------------------
# Golden-set splits
# ---------------------------------------------------------------------------


def is_answerable(case: dict) -> bool:
    """False for an Out-of-Scope Case: one the Corpus cannot answer. Defaults to True."""
    return case.get("answerable", True)


def answerable_cases(cases: list[dict]) -> list[dict]:
    """The cases retrieval is scored on.

    An Out-of-Scope Case has no Relevant Phrases, so there is nothing for retrieval to
    find; it is scored only on whether the answer Declines (see the generation harness).
    It is excluded here by its own label rather than by the "matches no chunk" error, so
    that error still fails loudly when an answerable case's label is broken.
    """
    return [c for c in cases if is_answerable(c)]


def describe_cases(cases: list[dict]) -> str:
    """How many cases are scored for retrieval, and how many were skipped as out of scope."""
    answerable = len(answerable_cases(cases))
    return f"{answerable} answerable + {len(cases) - answerable} out-of-scope"


def select_cases(cases: list[dict], split: str) -> list[dict]:
    """The cases belonging to `split`.

    An unlabelled or misspelt case is an error rather than a silent exclusion: a case
    quietly dropped from both portions would shrink the set nobody is watching, and a
    case quietly dropped from `holdout` alone would shrink the published sample.
    """
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split!r}. Expected one of {', '.join(SPLITS)}.")

    unlabelled = [c["id"] for c in cases if c.get("split") not in ("dev", "holdout")]
    if unlabelled:
        raise ValueError(
            "Golden cases carry no valid split: "
            f"{', '.join(unlabelled)}. Every case belongs to exactly one of dev/holdout."
        )

    # An Out-of-Scope Case carries no category: a Query Category describes how a
    # question's phrasing relates to the Corpus, and it has no such relationship.
    unlabelled_category = [
        c["id"] for c in answerable_cases(cases) if c.get("category") not in VALID_CATEGORIES
    ]
    if unlabelled_category:
        raise ValueError(
            "Golden cases carry no valid category: "
            f"{', '.join(unlabelled_category)}. Every case belongs to one of {', '.join(VALID_CATEGORIES)}."
        )

    unknown_origin = [c["id"] for c in cases if c.get("origin", "authored") not in VALID_ORIGINS]
    if unknown_origin:
        raise ValueError(
            "Golden cases carry no valid origin: "
            f"{', '.join(unknown_origin)}. Expected one of {', '.join(VALID_ORIGINS)}."
        )

    unlabelled_phrases = [c["id"] for c in answerable_cases(cases) if not c.get("relevant_phrases")]
    if unlabelled_phrases:
        raise ValueError(
            "Answerable golden cases carry no Relevant Phrases: "
            f"{', '.join(unlabelled_phrases)}. Label them, or mark a question the Corpus "
            "cannot answer `answerable: false`."
        )

    # Fact Recall is the share of a case's Required Facts an answer conveys: a case
    # with none could never be scored, and would drop out of that metric unnoticed.
    unlabelled_facts = [c["id"] for c in answerable_cases(cases) if not c.get("required_facts")]
    if unlabelled_facts:
        raise ValueError(
            "Answerable golden cases carry no Required Facts: "
            f"{', '.join(unlabelled_facts)}. Write the facts a correct answer conveys, or "
            "mark a question the Corpus cannot answer `answerable: false`."
        )

    labelled_out_of_scope = [
        c["id"]
        for c in cases
        if not is_answerable(c) and (c.get("relevant_phrases") or c.get("required_facts"))
    ]
    if labelled_out_of_scope:
        raise ValueError(
            "Out-of-Scope cases carry labels: "
            f"{', '.join(labelled_out_of_scope)}. A question the Corpus cannot answer has "
            "no Relevant Phrases or Required Facts."
        )

    if split == "all":
        return list(cases)
    return [c for c in cases if c["split"] == split]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Fraction of relevant chunks that appear in the top k."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def hit_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """1.0 if any relevant chunk is in the top k. What the LLM actually needs."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def reciprocal_rank(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Reciprocal rank of the first relevant chunk within the top k.

    Truncated at k like every other metric here. An untruncated MRR measured on
    a --top-k 20 run is not comparable to the Floors, which were derived at k=5.
    """
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Binary-gain nDCG@k."""
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(retrieved[:k], start=1)
        if doc_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


#: The candidate pool of `bm25+onnx-rerank-20`: fixed, not a multiple of the cutoff. The
#: 2×k pool of the older re-ranking arms can only recover chunks BM25 already put in its
#: top 10, and widening it is a new Arm rather than an edit to theirs (ADR-0009).
RERANK_POOL = 20


def _retrievers(pipeline, top_k: int) -> dict:
    """How each arm retrieves, keyed by the same IDs as ARM_SPECS.

    ARM_SPECS owns how an arm is described; this owns what it does. A mapping rather
    than an if/elif chain because arms come and go — see retrievers_for_arms().

    The re-ranking arms retrieve twice the cutoff and let the cross-encoder narrow to
    top_k. That ratio lives here now: `RAGPipeline.retrieve` no longer has a candidate
    stage to mirror, because the arm it implements does not re-rank.
    """

    def reranked(retrieve):
        def run(question: str) -> list[int]:
            candidates = retrieve(question, top_k=top_k * 2)
            return pipeline.rerank(question, candidates, top_k=top_k)

        return run

    def onnx_reranked_from_pool(question: str) -> list[int]:
        candidates = pipeline.sparse_search(question, top_k=RERANK_POOL)
        return pipeline.onnx_rerank(question, candidates, top_k=top_k)

    return {
        "bm25": lambda q: pipeline.sparse_search(q, top_k=top_k),
        "dense": lambda q: pipeline.dense_search(q, top_k=top_k),
        "hybrid": lambda q: pipeline.hybrid_search(q, top_k=top_k),
        "rerank": reranked(pipeline.hybrid_search),
        "bm25+rerank": reranked(pipeline.sparse_search),
        "onnx-dense": lambda q: pipeline.onnx_dense_search(q, top_k=top_k),
        "onnx-hybrid": lambda q: pipeline.onnx_hybrid_search(q, top_k=top_k),
        "bm25+onnx-rerank-20": onnx_reranked_from_pool,
    }


def retrievers_for_arms(pipeline, top_k: int) -> dict:
    """The retrieval callables, checked against the published arm list.

    A published arm with no implementation would fail only once someone selected it,
    and an implemented arm with no spec would fail only at `--publish`. Both are the
    same mistake — adding or retiring an arm in one place and not the other — so both
    are caught here, before any case runs.
    """
    retrievers = _retrievers(pipeline, top_k)
    if set(retrievers) != set(ARMS):
        missing = sorted(set(ARMS) - set(retrievers))
        extra = sorted(set(retrievers) - set(ARMS))
        raise ValueError(
            "Arm specs and retrievers disagree — "
            f"specs with no retriever: {missing or 'none'}; "
            f"retrievers with no spec: {extra or 'none'}."
        )
    return retrievers


#: What each arm loads on top of the chunks and BM25 index every pipeline reads at
#: construction, named by the RAGPipeline attribute that loads it on first use.
_ARM_LOADS: dict[str, tuple[str, ...]] = {
    "bm25": (),
    "dense": ("faiss_index", "embedder"),
    "hybrid": ("faiss_index", "embedder"),
    "rerank": ("faiss_index", "embedder", "cross_encoder"),
    "bm25+rerank": ("cross_encoder",),
    "onnx-dense": ("onnx_embeddings", "onnx_embedder"),
    "onnx-hybrid": ("onnx_embeddings", "onnx_embedder"),
    "bm25+onnx-rerank-20": ("onnx_cross_encoder",),
}


def measure_load(arm: str, build=None, clock=time.perf_counter) -> float:
    """Seconds from nothing loaded to `arm` ready for its first query.

    Timed on a fresh pipeline, so a model an earlier arm already loaded is loaded again
    and counted here too. Call it after the arm has been evaluated, so a first-ever run
    has already downloaded the weights: the band reports loading, not the network.
    """
    build = build or build_pipeline
    start = clock()
    pipeline = build()
    for attribute in _ARM_LOADS[arm]:
        getattr(pipeline, attribute)
    return clock() - start


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value at least `p`% of `values` do not exceed."""
    ordered = sorted(values)
    return ordered[max(math.ceil(p / 100 * len(ordered)) - 1, 0)]


def evaluate_arm(
    pipeline, arm: str, cases: list[dict], top_k: int, clock=time.perf_counter
) -> dict:
    """Run every case through one retrieval arm, averaging the metrics and timing each query.

    One untimed query runs first: the models load lazily, so an arm's first query is a
    model load rather than a warm query (see `measure_load` for that cost).
    """
    retrievers = retrievers_for_arms(pipeline, top_k)
    if arm not in retrievers:
        raise ValueError(f"Unknown arm: {arm}")
    retrieve = retrievers[arm]

    per_case = []
    timings = []

    scored = answerable_cases(cases)
    if scored:
        retrieve(scored[0]["question"])

    for case in scored:
        relevant = relevant_ids(pipeline.chunks, case["relevant_phrases"])
        if not relevant:
            raise ValueError(
                f"Golden case {case['id']!r} matches no chunk in the corpus. "
                "Fix the phrases or rebuild the index."
            )

        start = clock()
        retrieved = retrieve(case["question"])
        timings.append(clock() - start)

        per_case.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "n_relevant": len(relevant),
                f"recall@{top_k}": recall_at_k(retrieved, relevant, top_k),
                f"hit@{top_k}": hit_at_k(retrieved, relevant, top_k),
                "mrr": reciprocal_rank(retrieved, relevant, top_k),
                f"ndcg@{top_k}": ndcg_at_k(retrieved, relevant, top_k),
            }
        )

    metric_names = metric_names_for(top_k)
    summary = {m: sum(c[m] for c in per_case) / len(per_case) for m in metric_names}
    by_category = {}
    categories = sorted({c["category"] for c in per_case})
    for cat in categories:
        cat_cases = [c for c in per_case if c["category"] == cat]
        by_category[cat] = {m: sum(c[m] for c in cat_cases) / len(cat_cases) for m in metric_names}

    return {
        "arm": arm,
        "top_k": top_k,
        "summary": summary,
        "by_category": by_category,
        "cases": per_case,
        # Raw seconds, for the CLI and --json output. Only bands are published.
        "latency": {"p50": percentile(timings, 50), "p95": percentile(timings, 95)},
    }


def build_pipeline():
    """Construct the pipeline.

    Models load lazily, so the bm25 arm runs without downloading any weights.
    """
    from app.rag.pipeline import RAGPipeline

    return RAGPipeline()


def format_table(results: list[dict], top_k: int) -> str:
    headers = ["arm"] + metric_names_for(top_k)
    # The arm column sizes to the longest arm name. Arms are added and retired, and
    # "bm25+rerank" already overflows a fixed width — a table whose columns stop
    # lining up is how a reader misreads a row.
    widths = [max(len(h), 8) for h in headers]
    if results:
        widths[0] = max(widths[0], max(len(r["arm"]) for r in results))
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    for r in results:
        row = [r["arm"]] + [f"{r['summary'][m]:.3f}" for m in headers[1:]]
        lines.append("  ".join(v.ljust(w) for v, w in zip(row, widths)))
    return "\n".join(lines)


def format_latency_table(results: list[dict]) -> str:
    """Raw timings beside the Latency Bands they publish as.

    The raw numbers appear here and in --json output only: they move between runs and
    runners, so the published document carries the bands alone.
    """
    headers = ["arm", "p50 ms", "p95 ms", "load s", "warm band", "load band"]
    rows = [
        [
            r["arm"],
            f"{r['latency']['p50'] * 1000:.2f}",
            f"{r['latency']['p95'] * 1000:.2f}",
            f"{r['latency']['load']:.3f}",
            latency_band(r["latency"]["p95"]),
            latency_band(r["latency"]["load"]),
        ]
        for r in results
    ]
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    lines += ["  ".join(v.ljust(w) for v, w in zip(row, widths)) for row in rows]
    return "\n".join(lines)


def check_floors(
    results: list[dict],
    top_k: int,
    golden_cases: list[dict],
    split: str = GATED_SPLIT,
    record: dict | None = None,
) -> int:
    """Gate the run against the retrieval Floors record. Returns a process exit code.

    `golden_cases` is the whole committed Golden Set, whatever split ran, and `record`
    defaults to the committed one (eval/floors/retrieval.json).

    A record whose fingerprint no longer matches the Golden Set fails first, on its own,
    with "Floors stale: Recalibrate": its Floors were derived on a set that no longer
    exists, so comparing against them would be neither a pass nor a regression.

    Three ways a run can look gated without being gated. The first two were real
    behaviour once; the third is what a `--split` flag would have introduced:

    1. An ungated arm (``dense``) contributed no checks, so a dense-only ``--check``
       run compared nothing and still printed "OK". A run in which *nothing* was gated
       is now a failure, and any ungated arm is named explicitly rather than passing in
       silence.
    2. Floors are derived at k=5. Comparing them against metrics measured at another
       cutoff is meaningless, so a non-default ``--top-k`` cannot be gated.
    3. Floors are derived on the whole golden set. A single split is a smaller,
       noisier sample against the same absolute numbers, so gating one would fail
       the build on sampling noise or pass a real regression by luck.
    """
    record = record if record is not None else read_record(RETRIEVAL_FLOORS_PATH)
    expected = retrieval_fingerprint(golden_cases)
    if record["fingerprint"] != expected:
        print(
            f"\nFAIL — {STALE}. The Golden Set no longer matches the retrieval Floors "
            f"record (record {record['fingerprint'][:19]}…, Golden Set {expected[:19]}…). "
            "Run `uv run --frozen python eval/recalibrate.py retrieval` in this same "
            "change (ADR-0012)."
        )
        return 1

    if top_k != DEFAULT_TOP_K:
        print(
            f"\nFAIL — --check is derived for --top-k {DEFAULT_TOP_K}, got {top_k}. "
            "Re-run at the default cutoff."
        )
        return 1

    if split != GATED_SPLIT:
        print(
            f"\nFAIL — --check Floors are derived on the {GATED_SPLIT} golden set, got "
            f"--split {split}. A split is a smaller sample against the same Floors."
        )
        return 1

    floors_by_arm = {shipped_arm_id(): record["floors"]}
    failures: list[str] = []
    gated: list[str] = []
    ungated: list[str] = []

    for r in results:
        floors = floors_by_arm.get(r["arm"])
        if not floors:
            ungated.append(r["arm"])
            continue
        gated.append(r["arm"])
        for metric, floor in floors.items():
            actual = r["summary"][metric]
            if actual < floor:
                failures.append(f"{r['arm']}.{metric} = {actual:.3f} < {floor:.3f}")

    if ungated:
        print(f"\nNOT GATED — no Floors for: {', '.join(ungated)}")

    if failures:
        print("\nFAIL — retrieval quality below its Floors:")
        for f in failures:
            print(f"  {f}")
        return 1

    if not gated:
        print("\nFAIL — --check ran but gated nothing. No evaluated arm has Floors.")
        return 1

    print(f"\nOK — all gated arms ({', '.join(gated)}) meet their Floors.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arms",
        nargs="+",
        default=list(ARMS),
        choices=ARMS,
        help="Retrieval arms to evaluate (default: all).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Cutoff for retrieval and every metric (default: {DEFAULT_TOP_K}). "
        "--check requires the default.",
    )
    parser.add_argument(
        "--split",
        default="all",
        choices=SPLITS,
        help="Golden-set portion to measure (default: all). Decide things on dev; "
        f"--publish reports {PUBLISHED_SPLIT} and --check gates {GATED_SPLIT}.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the Floors record is stale, or the Shipped Arm falls below a Floor.",
    )
    parser.add_argument("--json", type=Path, help="Write full per-case results to this path.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write the measured run to frontend/data/evalResults.json and refresh the "
        f"generated table in docs/evaluation.md. Requires every arm, the default cutoff, "
        f"and --split {PUBLISHED_SPLIT}.",
    )
    parser.add_argument(
        "--failures",
        action="store_true",
        help="List the individual cases where no relevant chunk was retrieved.",
    )
    args = parser.parse_args()

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = select_cases(golden["cases"], args.split)

    pipeline = build_pipeline()
    print(
        f"Corpus: {len(pipeline.chunks)} chunks | "
        f"Golden set: {describe_cases(cases)} questions ({args.split})\n"
    )

    results = [evaluate_arm(pipeline, arm, cases, args.top_k) for arm in args.arms]
    # After every arm has run, so any model weights are already downloaded.
    for r in results:
        r["latency"]["load"] = measure_load(r["arm"])
    print(format_table(results, args.top_k))
    print(f"\nLatency ({len(answerable_cases(cases))} warm queries per arm)")
    print(format_latency_table(results))

    all_categories = sorted({cat for r in results for cat in r.get("by_category", {})})
    for cat in all_categories:
        cat_results = [
            {"arm": r["arm"], "summary": r["by_category"][cat]}
            for r in results
            if cat in r.get("by_category", {})
        ]
        cat_cases_count = len([c for c in cases if c.get("category") == cat])
        print(f"\nCategory: {cat} ({cat_cases_count} questions)")
        print(format_table(cat_results, args.top_k))

    if args.failures:
        for r in results:
            hit_key = f"hit@{args.top_k}"
            misses = [c for c in r["cases"] if c[hit_key] == 0.0]
            if misses:
                print(
                    f"\n{r['arm']} — {len(misses)} question(s) "
                    f"with no relevant chunk in top {args.top_k}:"
                )
                for m in misses:
                    print(f"  - [{m['id']}] {m['question']}")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    if args.publish:
        # A partial run would publish a table missing arms, and a non-default cutoff
        # would publish metrics the prose around them does not describe. Both are worse
        # than not publishing, so refuse rather than write something misleading.
        if set(args.arms) != set(ARMS):
            print(
                f"\nFAIL — --publish needs every arm ({', '.join(ARMS)}), got "
                f"{', '.join(args.arms)}. Publishing a partial run would drop rows from "
                "the public table."
            )
            return 1
        if args.top_k != DEFAULT_TOP_K:
            print(f"\nFAIL — --publish requires --top-k {DEFAULT_TOP_K}; got {args.top_k}.")
            return 1
        # Publishing the dev portion would put the questions the configuration was
        # chosen on onto the public page as if they were evidence about it.
        if args.split != PUBLISHED_SPLIT:
            print(
                f"\nFAIL — --publish reports the {PUBLISHED_SPLIT} split; got "
                f"--split {args.split}. Published numbers must be numbers nothing was "
                "tuned against."
            )
            return 1

        document = build_results_document(
            results,
            corpus_chunks=len(pipeline.chunks),
            golden_questions=len(answerable_cases(cases)),
            top_k=args.top_k,
            gating_metric=GATING_METRIC,
            split=args.split,
            inputs_fingerprint=retrieval_inputs_fingerprint(),
        )
        # An unchanged measurement leaves both files alone, so the publishing job has
        # something real to test for. `document` is rebound to whatever is now on disk:
        # rendering the markdown from the run we just discarded would put a fresh
        # timestamp under a table the JSON still dates to the earlier run.
        document, written = write_results_document(document, RESULTS_PATH)
        changed = update_markdown_block(EVALUATION_DOC_PATH, document)
        print(
            f"\n{'Published' if written else 'Measurement unchanged; kept'} "
            f"{RESULTS_PATH.relative_to(REPO_ROOT)}"
        )
        print(
            f"{'Updated' if changed else 'No change to'} "
            f"{EVALUATION_DOC_PATH.relative_to(REPO_ROOT)}"
        )
        print(f"Verdict: {verdict_line(document)}")

    if args.check:
        return check_floors(results, args.top_k, golden["cases"], args.split)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
