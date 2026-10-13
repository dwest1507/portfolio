"""Retrieval over the pre-built portfolio indexes.

Production retrieves with BM25 keyword search and nothing else. That is not the
configuration this pipeline was designed with — it is the one the evaluation harness
picked out of five. Semantic search, fusion and cross-encoder re-ranking were all
measured against plain keyword search on this corpus and none of them beat it; see
docs/evaluation.md and the findings log for the numbers and the reasoning.

Those stages still live here, because retiring an arm from production is not the same
as deciding it will never be worth running again. `eval/run_eval.py` measures every one
of them on every run, so the day the corpus grows past the point where keyword matching
suffices, the harness is what says so.

They run on ONNX Runtime (`onnx_dense_search`, `onnx_hybrid_search`, `onnx_rerank`), not
torch, so each is a Candidate Arm production could actually ship (ADR-0009). The torch
and FAISS versions they were checked against are gone (ADR-0013).

They are inert until an arm asks for them: the ONNX models are imported inside the lazy
loaders below, not at module scope, so the production image installs none of them and
startup loads none of them. Their runtime is declared in the `dev` dependency group,
which the Dockerfile's `uv sync --no-dev` skips.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from rank_bm25 import BM25Okapi

from ..config import INDEXES_DIR
from .tokenize import tokenize

if TYPE_CHECKING:  # imported for typing only; see the module docstring
    from .onnx_models import OnnxCrossEncoder, OnnxEmbedder

# Weights applied to each retriever's reciprocal-rank contribution in the `onnx-hybrid`
# arm. Semantic search leads on the assumption that most recruiter questions are
# paraphrases rather than exact-term lookups, with BM25 as the backstop for proper nouns
# ("TACOM", "FAISS") that embeddings blur together.
#
# These were never tuned, and deliberately were not. Under RRF, driving DENSE_WEIGHT
# toward zero makes the fused ranking converge on BM25's ordering — so on a corpus where BM25
# already leads every metric, "find the best ratio" and "turn dense off" are the same
# experiment, and the second one is the honest way to run it. It was run, dense lost,
# and tuning the split would have been optimising a stage on its way off the serving
# path. They stay at their original values so the measured arms keep meaning what they
# have always meant.
DENSE_WEIGHT = 0.7
SPARSE_WEIGHT = 0.3

# RRF damping constant.
#
# NOT the Cormack et al. (2009) default of 60. That value assumes ranked lists
# thousands of documents long, where k=60 usefully flattens the gap between the
# top few ranks. Here the lists are 10 items, and at k=60 the rank term varies
# by only (60+10)/(60+1) = 1.15x across the whole list while the weight term
# varies by 0.7/0.3 = 2.33x. The weights therefore dominate completely: every
# dense hit outscores every sparse hit, BM25 can never introduce a candidate the
# dense arm missed, and its documented role as a proper-noun backstop is dead.
#
# k must satisfy (k+10)/(k+1) > 0.7/0.3 for a sparse-only hit at rank 1 to beat
# a dense hit at rank 10, i.e. k < 5.75. k=1 places a sparse-only top hit around
# 4th in the fused list, which is inside the candidate set with room to spare.
# test_rrf_sparse_only_hit_reaches_candidates locks this property down.
RRF_K = 1


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    weights: list[float],
    k: int = RRF_K,
) -> list[tuple[int, float]]:
    """Fuse ranked ID lists by weighted reciprocal rank.

    Each list contributes ``weight / (k + rank)`` for its entries (rank is
    1-based). Returns ``(id, score)`` pairs sorted best-first.

    RRF is used instead of normalizing and summing raw scores because embedding
    cosine similarities and BM25 term-frequency scores live on different,
    unbounded scales. Min-max normalizing each list independently — the previous
    approach here — forces the top hit of *every* list to 1.0 and the bottom to
    0.0 regardless of absolute quality, so a list of uniformly irrelevant
    results contributed exactly as much as a list of excellent ones, and the
    last item of each list was always discarded at score 0. Rank position is
    scale-free and has neither failure mode.
    """
    if len(rankings) != len(weights):
        raise ValueError("rankings and weights must be the same length")

    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class RAGPipeline:
    """Retrieval over the pre-built portfolio indexes.

    Only the chunks and the BM25 index are loaded on construction, because only those
    are on the serving path. The Corpus embeddings, the embedding model and the
    cross-encoder load on first use, which in production is never — the evaluation
    harness is the only caller that reaches them.
    """

    def __init__(
        self,
        indexes_dir: Path = INDEXES_DIR,
        onnx_embedder: OnnxEmbedder | None = None,
        onnx_cross_encoder: OnnxCrossEncoder | None = None,
    ) -> None:
        self._indexes_dir = indexes_dir

        # Load chunks
        with open(indexes_dir / "chunks.json") as f:
            self.chunks: list[dict] = json.load(f)

        # Load BM25 index
        with open(indexes_dir / "bm25.pkl", "rb") as f:
            self.bm25: BM25Okapi = pickle.load(f)

        # A BM25 index built from a different revision of chunks.json would rank
        # positions that no longer mean what they meant when it was built. Since
        # `sparse_search` hands those positions straight to `self.chunks[i]`, a stale
        # pickle either raises IndexError on a live request or, worse, silently serves
        # the text of the wrong chunk. The guards on the unserved indexes run on first use
        # instead; this one belongs on whichever index is actually served.
        if self.bm25.corpus_size != len(self.chunks):
            raise ValueError(
                f"Index mismatch: bm25.pkl has {self.bm25.corpus_size} documents but "
                f"chunks.json has {len(self.chunks)} chunks. Run `make build-index`."
            )

        self._onnx_embeddings: np.ndarray | None = None
        self._onnx_embedder = onnx_embedder
        self._onnx_cross_encoder = onnx_cross_encoder

    # -- Lazily loaded indexes and models ------------------------------------

    @property
    def onnx_embeddings(self) -> np.ndarray:
        """The Corpus embedded by the ONNX embedder at index build time, read on first use.

        A plain matrix rather than a vector index: an exact inner-product search over a few
        hundred rows is one matrix product, and numpy is already on the serving path.

        The consistency check runs here rather than at construction: dense retrieval is
        not on the serving path, so a mismatch cannot return the text of the wrong chunk to
        a visitor — it can only mislead the harness, which is exactly who this raises for.
        """
        if self._onnx_embeddings is None:
            embeddings = np.load(self._indexes_dir / "onnx_embeddings.npy")
            if len(embeddings) != len(self.chunks):
                raise ValueError(
                    f"Index mismatch: onnx_embeddings.npy has {len(embeddings)} rows but "
                    f"chunks.json has {len(self.chunks)} chunks. Run `make build-index`."
                )
            self._onnx_embeddings = embeddings
        return self._onnx_embeddings

    @property
    def onnx_embedder(self) -> OnnxEmbedder:
        if self._onnx_embedder is None:
            from .onnx_models import OnnxEmbedder

            self._onnx_embedder = OnnxEmbedder()
        return self._onnx_embedder

    @property
    def onnx_cross_encoder(self) -> OnnxCrossEncoder:
        if self._onnx_cross_encoder is None:
            from .onnx_models import OnnxCrossEncoder

            self._onnx_cross_encoder = OnnxCrossEncoder()
        return self._onnx_cross_encoder

    # -- Retrieval -----------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """What production runs: BM25 keyword search → top_k chunk texts.

        Returns fewer than `top_k` texts — possibly none — when the query shares no
        term with any chunk. That is deliberate. The alternative is padding the prompt
        with the least-bad chunks in the corpus, which is how a model ends up
        confidently answering an off-topic question from unrelated context. An empty
        context leaves the system prompt's "say so honestly" instruction with nothing
        to contradict it.
        """
        return [self.chunks[i]["text"] for i in self.sparse_search(query, top_k=top_k)]

    def sparse_search(self, query: str, top_k: int = 10) -> list[int]:
        """BM25 keyword search. Returns chunk IDs, best first."""
        scores = self.bm25.get_scores(tokenize(query))
        ranked = np.argsort(scores)[::-1][:top_k]
        # Drop chunks BM25 scored at zero: they share no query term at all, and
        # including them would hand reciprocal-rank credit to documents that
        # merely padded out the list.
        return [int(i) for i in ranked if scores[i] > 0]

    # The stages below are measured, not shipped — see the module docstring.

    def onnx_dense_search(self, query: str, top_k: int = 10) -> list[int]:
        """Semantic search with the ONNX embedder. Returns chunk IDs, best first."""
        query_vec = self.onnx_embedder.encode([query])[0]
        scores = self.onnx_embeddings @ query_vec
        return [int(i) for i in np.argsort(-scores, kind="stable")[:top_k]]

    def onnx_hybrid_search(self, query: str, top_k: int = 10) -> list[int]:
        """Weighted reciprocal-rank fusion of `onnx_dense_search` and `sparse_search`.

        Returns chunk IDs, best first.
        """
        dense = self.onnx_dense_search(query, top_k=top_k)
        sparse = self.sparse_search(query, top_k=top_k)
        fused = reciprocal_rank_fusion([dense, sparse], [DENSE_WEIGHT, SPARSE_WEIGHT])
        return [doc_id for doc_id, _ in fused[:top_k]]

    def onnx_rerank(self, query: str, candidate_ids: list[int], top_k: int = 5) -> list[int]:
        """Cross-encoder re-ranking of `candidate_ids`. Returns chunk IDs, best first."""
        if len(candidate_ids) <= 1:
            return candidate_ids[:top_k]
        pairs = [[query, self.chunks[i]["text"]] for i in candidate_ids]
        scores = self.onnx_cross_encoder.predict(pairs)
        ranked = sorted(zip(candidate_ids, scores), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in ranked[:top_k]]


_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
