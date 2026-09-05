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

Usage:
    uv run python eval/run_eval.py                      # all arms
    uv run python eval/run_eval.py --arms bm25          # no model download
    uv run python eval/run_eval.py --check              # exit 1 below thresholds
    uv run python eval/run_eval.py --json results.json  # machine-readable output
    uv run python eval/run_eval.py --publish            # refresh the published results

A chunk counts as relevant when its text contains any of the case's
`relevant_phrases`. Labelling by phrase rather than chunk ID keeps the golden
set valid when the corpus is re-chunked.

The golden set is split into `dev` and `holdout` portions (see golden_set.json).
Decide things on `dev`; `holdout` is what gets published, so a published number is
never a number something was tuned against. `--split` selects which portion runs.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.publish import (  # (needs the sys.path line above)
    ARMS,
    build_results_document,
    shipped_arm_id,
    update_markdown_block,
    verdict_line,
    write_results_document,
)

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.json"

# Where a published run lands. Both are committed by CI; see
# docs/adr/0001-generated-eval-results.md.
RESULTS_PATH = REPO_ROOT / "frontend" / "data" / "evalResults.json"
EVALUATION_DOC_PATH = REPO_ROOT / "docs" / "evaluation.md"

# Regression floors for `--check`. Not targets — they sit below measured
# performance so real regressions fail CI while ordinary noise does not.
#
# The gate is hit@5 and MRR, deliberately NOT recall@5. recall@5 is reported
# because it is informative, but it is a poor gate here: several golden
# questions have more than five relevant chunks, so their recall@5 is capped
# below 1.0 by construction and the aggregate can never reach a high floor.
# hit@5 ("did any grounding text reach the model?") is what actually determines
# whether the LLM can answer, and MRR captures how far up the list it landed.
#
# The floors sit below measured performance with headroom for noise, so a real
# regression fails the build while ordinary variation does not. They are floors,
# never targets: tuning a parameter until a floor is cleared is fitting to the
# golden set. See docs/evaluation.md.
_FLOORS = {"hit@5": 0.85, "mrr": 0.75}

# Keyed by metric name at the default cutoff. `--check` is only meaningful at
# that cutoff, which check_thresholds() enforces rather than silently comparing
# a hit@20 against a floor calibrated for hit@5.
DEFAULT_TOP_K = 5

# The metric the published verdict is decided on: "did any grounding text reach the
# model?" is what determines whether the LLM can answer at all.
GATING_METRIC = f"hit@{DEFAULT_TOP_K}"

# Golden-set portions. "all" is not a third portion, it is both of them together.
SPLITS = ("all", "dev", "holdout")

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

# Gated arms, keyed by ID. Only the SHIPPED arm is gated, and it is looked up rather
# than named so the gate follows production when the shipped arm changes.
#
# Every other arm is measured and published as a baseline for comparison, not defended
# as a quality bar. Two reasons that is the right line to draw. A floor is there to stop
# a change degrading what a visitor is actually served, and nothing is served by an arm
# production does not run. And floors are calibrated against a corpus: when the corpus
# grows, floors on four arms means four constants to re-justify, and a constant nudged
# to make a build pass is the magic number this file exists to argue against.
#
# `--check` names every ungated arm explicitly, and a run that gates nothing is a
# failure, so this cannot quietly become a gate over nothing.
THRESHOLDS: dict[str, dict[str, float]] = {shipped_arm_id(): dict(_FLOORS)}


def metric_names_for(top_k: int) -> list[str]:
    return [f"recall@{top_k}", f"hit@{top_k}", "mrr", f"ndcg@{top_k}"]


# ---------------------------------------------------------------------------
# Relevance judgement
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace so phrases match across line wrapping."""
    return re.sub(r"\s+", " ", text).strip().lower()


def is_relevant(chunk_text: str, phrases: list[str]) -> bool:
    haystack = _normalize(chunk_text)
    return any(_normalize(p) in haystack for p in phrases)


def relevant_ids(chunks: list[dict], phrases: list[str]) -> set[int]:
    return {i for i, c in enumerate(chunks) if is_relevant(c["text"], phrases)}


# ---------------------------------------------------------------------------
# Golden-set splits
# ---------------------------------------------------------------------------


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
    a --top-k 20 run is not comparable to the thresholds, which were calibrated
    at k=5.
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


def _retrievers(pipeline, top_k: int) -> dict:
    """How each arm retrieves, keyed by the same IDs as ARM_SPECS.

    ARM_SPECS owns how an arm is described; this owns what it does. A mapping rather
    than an if/elif chain because arms come and go — see retrievers_for_arms().

    The re-ranking arms retrieve twice the cutoff and let the cross-encoder narrow to
    top_k, mirroring RAGPipeline.retrieve's candidates_k/top_k split.
    """

    def reranked(retrieve):
        def run(question: str) -> list[int]:
            candidates = retrieve(question, top_k=top_k * 2)
            return pipeline.rerank(question, candidates, top_k=top_k)

        return run

    return {
        "bm25": lambda q: pipeline.sparse_search(q, top_k=top_k),
        "dense": lambda q: pipeline.dense_search(q, top_k=top_k),
        "hybrid": lambda q: pipeline.hybrid_search(q, top_k=top_k),
        "rerank": reranked(pipeline.hybrid_search),
        "bm25+rerank": reranked(pipeline.sparse_search),
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


def evaluate_arm(pipeline, arm: str, cases: list[dict], top_k: int) -> dict:
    """Run every case through one retrieval arm and average the metrics."""
    retrievers = retrievers_for_arms(pipeline, top_k)
    if arm not in retrievers:
        raise ValueError(f"Unknown arm: {arm}")
    retrieve = retrievers[arm]

    per_case = []

    for case in cases:
        relevant = relevant_ids(pipeline.chunks, case["relevant_phrases"])
        if not relevant:
            raise ValueError(
                f"Golden case {case['id']!r} matches no chunk in the corpus. "
                "Fix the phrases or rebuild the index."
            )

        retrieved = retrieve(case["question"])

        per_case.append(
            {
                "id": case["id"],
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
    return {"arm": arm, "top_k": top_k, "summary": summary, "cases": per_case}


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


def check_thresholds(results: list[dict], top_k: int, split: str = GATED_SPLIT) -> int:
    """Gate the run against THRESHOLDS. Returns a process exit code.

    Three ways a run can look gated without being gated. The first two were real
    behaviour once; the third is what a `--split` flag would have introduced:

    1. An arm with no THRESHOLDS entry (``dense``) contributed no checks, so a
       dense-only ``--check`` run compared nothing and still printed "OK". A run
       in which *nothing* was gated is now a failure, and any ungated arm is
       named explicitly rather than passing in silence.
    2. Floors are calibrated at k=5. Comparing them against metrics measured at
       another cutoff is meaningless, so a non-default ``--top-k`` cannot be
       gated.
    3. Floors are calibrated on the whole golden set. A single split is a smaller,
       noisier sample against the same absolute numbers, so gating one would fail
       the build on sampling noise or pass a real regression by luck.
    """
    if top_k != DEFAULT_TOP_K:
        print(
            f"\nFAIL — --check is calibrated for --top-k {DEFAULT_TOP_K}, got {top_k}. "
            "Re-run at the default cutoff, or update THRESHOLDS deliberately."
        )
        return 1

    if split != GATED_SPLIT:
        print(
            f"\nFAIL — --check is calibrated on the {GATED_SPLIT} golden set, got "
            f"--split {split}. A split is a smaller sample against the same floors."
        )
        return 1

    failures: list[str] = []
    gated: list[str] = []
    ungated: list[str] = []

    for r in results:
        thresholds = THRESHOLDS.get(r["arm"])
        if not thresholds:
            ungated.append(r["arm"])
            continue
        gated.append(r["arm"])
        for metric, floor in thresholds.items():
            actual = r["summary"][metric]
            if actual < floor:
                failures.append(f"{r['arm']}.{metric} = {actual:.3f} < {floor:.3f}")

    if ungated:
        print(f"\nNOT GATED — no thresholds configured for: {', '.join(ungated)}")

    if failures:
        print("\nFAIL — retrieval quality below threshold:")
        for f in failures:
            print(f"  {f}")
        return 1

    if not gated:
        print("\nFAIL — --check ran but gated nothing. No evaluated arm has thresholds.")
        return 1

    print(f"\nOK — all gated arms ({', '.join(gated)}) meet their thresholds.")
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
        help="Exit non-zero if any evaluated arm falls below its threshold.",
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
        f"Golden set: {len(cases)} questions ({args.split})\n"
    )

    results = [evaluate_arm(pipeline, arm, cases, args.top_k) for arm in args.arms]
    print(format_table(results, args.top_k))

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
            golden_questions=len(cases),
            top_k=args.top_k,
            gating_metric=GATING_METRIC,
            split=args.split,
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
        return check_thresholds(results, args.top_k, args.split)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
