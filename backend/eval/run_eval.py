"""Retrieval evaluation harness for the portfolio chatbot.

Answers the question the pipeline could not previously answer: does retrieval
actually work, and do the weights and stage choices earn their keep?

Runs the golden question set through each retrieval arm and reports recall@k,
MRR, and nDCG@k so the arms can be compared directly:

    bm25    keyword only (no embedding model required)
    dense   FAISS semantic only
    hybrid  weighted reciprocal-rank fusion of both
    rerank  hybrid candidates re-ordered by the cross-encoder

Usage:
    uv run python eval/run_eval.py                      # all arms
    uv run python eval/run_eval.py --arms bm25          # no model download
    uv run python eval/run_eval.py --check              # exit 1 below thresholds
    uv run python eval/run_eval.py --json results.json  # machine-readable output
    uv run python eval/run_eval.py --publish            # refresh the published results

A chunk counts as relevant when its text contains any of the case's
`relevant_phrases`. Labelling by phrase rather than chunk ID keeps the golden
set valid when the corpus is re-chunked.
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

from eval.publish import (  # noqa: E402  (needs the sys.path line above)
    ARMS,
    build_results_document,
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

THRESHOLDS: dict[str, dict[str, float]] = {
    "bm25": dict(_FLOORS),
    "hybrid": dict(_FLOORS),
    "rerank": dict(_FLOORS),
    # NOTE: "dense" is deliberately absent. It is measured and published as a
    # baseline for comparison, not defended as a quality bar, so it has no honest
    # floor. An ungated arm is reported as such by `--check` rather than quietly
    # passing.
}


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


def evaluate_arm(pipeline, arm: str, cases: list[dict], top_k: int) -> dict:
    """Run every case through one retrieval arm and average the metrics."""
    per_case = []

    for case in cases:
        relevant = relevant_ids(pipeline.chunks, case["relevant_phrases"])
        if not relevant:
            raise ValueError(
                f"Golden case {case['id']!r} matches no chunk in the corpus. "
                "Fix the phrases or rebuild the index."
            )

        if arm == "bm25":
            retrieved = pipeline.sparse_search(case["question"], top_k=top_k)
        elif arm == "dense":
            retrieved = pipeline.dense_search(case["question"], top_k=top_k)
        elif arm == "hybrid":
            retrieved = pipeline.hybrid_search(case["question"], top_k=top_k)
        elif arm == "rerank":
            candidates = pipeline.hybrid_search(case["question"], top_k=top_k * 2)
            retrieved = pipeline.rerank(case["question"], candidates, top_k=top_k)
        else:
            raise ValueError(f"Unknown arm: {arm}")

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
    widths = [max(len(h), 8) for h in headers]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    for r in results:
        row = [r["arm"]] + [f"{r['summary'][m]:.3f}" for m in headers[1:]]
        lines.append("  ".join(v.ljust(w) for v, w in zip(row, widths)))
    return "\n".join(lines)


def check_thresholds(results: list[dict], top_k: int) -> int:
    """Gate the run against THRESHOLDS. Returns a process exit code.

    Two ways this used to pass when it should not have:

    1. An arm with no THRESHOLDS entry (``dense``) contributed no checks, so a
       dense-only ``--check`` run compared nothing and still printed "OK". A run
       in which *nothing* was gated is now a failure, and any ungated arm is
       named explicitly rather than passing in silence.
    2. Floors are calibrated at k=5. Comparing them against metrics measured at
       another cutoff is meaningless, so a non-default ``--top-k`` cannot be
       gated.
    """
    if top_k != DEFAULT_TOP_K:
        print(
            f"\nFAIL — --check is calibrated for --top-k {DEFAULT_TOP_K}, got {top_k}. "
            "Re-run at the default cutoff, or update THRESHOLDS deliberately."
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
        "--check",
        action="store_true",
        help="Exit non-zero if any evaluated arm falls below its threshold.",
    )
    parser.add_argument("--json", type=Path, help="Write full per-case results to this path.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write the measured run to frontend/data/evalResults.json and refresh the "
        "generated table in docs/evaluation.md. Requires every arm and the default cutoff.",
    )
    parser.add_argument(
        "--failures",
        action="store_true",
        help="List the individual cases where no relevant chunk was retrieved.",
    )
    args = parser.parse_args()

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = golden["cases"]

    pipeline = build_pipeline()
    print(f"Corpus: {len(pipeline.chunks)} chunks | Golden set: {len(cases)} questions\n")

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

        document = build_results_document(
            results,
            corpus_chunks=len(pipeline.chunks),
            golden_questions=len(cases),
            top_k=args.top_k,
            gating_metric=GATING_METRIC,
        )
        write_results_document(document, RESULTS_PATH)
        changed = update_markdown_block(EVALUATION_DOC_PATH, document)
        print(f"\nPublished {RESULTS_PATH.relative_to(REPO_ROOT)}")
        print(
            f"{'Updated' if changed else 'No change to'} "
            f"{EVALUATION_DOC_PATH.relative_to(REPO_ROOT)}"
        )
        print(f"Verdict: {verdict_line(document)}")

    if args.check:
        return check_thresholds(results, args.top_k)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
