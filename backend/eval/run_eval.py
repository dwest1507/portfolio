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
sys.path.insert(0, str(BACKEND_ROOT))

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.json"

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
# The floors below are the measured BM25-only baseline rounded down. BM25 alone
# is the weakest arm, so any arm scoring under it is a genuine regression.
# Tighten these once the full four-arm run has been recorded — see
# docs/evaluation.md.
_FLOORS = {"hit@5": 0.85, "mrr": 0.75}

THRESHOLDS: dict[str, dict[str, float]] = {
    "bm25": dict(_FLOORS),
    "hybrid": dict(_FLOORS),
    "rerank": dict(_FLOORS),
}

ARMS = ("bm25", "dense", "hybrid", "rerank")


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


def reciprocal_rank(retrieved: list[int], relevant: set[int]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
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
                "recall@5": recall_at_k(retrieved, relevant, 5),
                "hit@5": hit_at_k(retrieved, relevant, 5),
                "mrr": reciprocal_rank(retrieved, relevant),
                "ndcg@5": ndcg_at_k(retrieved, relevant, 5),
            }
        )

    metric_names = ["recall@5", "hit@5", "mrr", "ndcg@5"]
    summary = {m: sum(c[m] for c in per_case) / len(per_case) for m in metric_names}
    return {"arm": arm, "summary": summary, "cases": per_case}


def build_pipeline():
    """Construct the pipeline.

    Models load lazily, so the bm25 arm runs without downloading any weights.
    """
    from app.rag.pipeline import RAGPipeline

    return RAGPipeline()


def format_table(results: list[dict]) -> str:
    headers = ["arm", "recall@5", "hit@5", "mrr", "ndcg@5"]
    widths = [max(len(h), 8) for h in headers]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    for r in results:
        row = [r["arm"]] + [f"{r['summary'][m]:.3f}" for m in headers[1:]]
        lines.append("  ".join(v.ljust(w) for v, w in zip(row, widths)))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arms",
        nargs="+",
        default=list(ARMS),
        choices=ARMS,
        help="Retrieval arms to evaluate (default: all).",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Cutoff for retrieval (default: 5).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any evaluated arm falls below its threshold.",
    )
    parser.add_argument("--json", type=Path, help="Write full results to this path.")
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
    print(format_table(results))

    if args.failures:
        for r in results:
            misses = [c for c in r["cases"] if c["hit@5"] == 0.0]
            if misses:
                print(f"\n{r['arm']} — {len(misses)} question(s) with no relevant chunk in top 5:")
                for m in misses:
                    print(f"  - [{m['id']}] {m['question']}")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    if args.check:
        failures = []
        for r in results:
            for metric, floor in THRESHOLDS.get(r["arm"], {}).items():
                actual = r["summary"][metric]
                if actual < floor:
                    failures.append(f"{r['arm']}.{metric} = {actual:.3f} < {floor:.3f}")
        if failures:
            print("\nFAIL — retrieval quality below threshold:")
            for f in failures:
                print(f"  {f}")
            return 1
        print("\nOK — all evaluated arms meet their thresholds.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
