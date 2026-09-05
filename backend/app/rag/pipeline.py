"""RAG pipeline: hybrid search (FAISS + BM25) + cross-encoder re-ranking."""

import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from ..config import INDEXES_DIR
from .tokenize import tokenize

EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Weights applied to each retriever's reciprocal-rank contribution. Semantic
# search leads because most recruiter questions are paraphrases rather than
# exact-term lookups; BM25 is the backstop for proper nouns ("TACOM", "FAISS")
# that embeddings blur together. Tuned against eval/golden_set.json — see
# `make eval`.
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

    RRF is used instead of normalizing and summing raw scores because FAISS
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
    """Hybrid retrieval over the pre-built portfolio indexes.

    The embedding and cross-encoder models are loaded lazily on first use. That
    keeps keyword-only paths (the BM25 arm of the eval harness, most unit tests)
    runnable without downloading ~500MB of weights, and lets the API server
    control when it pays that cost via :meth:`warm`.
    """

    def __init__(
        self,
        indexes_dir: Path = INDEXES_DIR,
        embedder: SentenceTransformer | None = None,
        cross_encoder: CrossEncoder | None = None,
    ) -> None:
        # Load chunks
        with open(indexes_dir / "chunks.json") as f:
            self.chunks: list[dict] = json.load(f)

        # Load FAISS index (inner product = cosine sim on normalized vectors)
        self.faiss_index = faiss.read_index(str(indexes_dir / "faiss.index"))

        # A FAISS index built from a different revision of chunks.json would
        # silently return the text of the wrong chunk IDs, so refuse to start.
        if self.faiss_index.ntotal != len(self.chunks):
            raise ValueError(
                f"Index mismatch: faiss.index has {self.faiss_index.ntotal} vectors but "
                f"chunks.json has {len(self.chunks)} chunks. Run `make build-index`."
            )

        # Load BM25 index
        with open(indexes_dir / "bm25.pkl", "rb") as f:
            self.bm25: BM25Okapi = pickle.load(f)

        self._embedder = embedder
        self._cross_encoder = cross_encoder

    # -- Lazily loaded models ------------------------------------------------

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedder

    @property
    def cross_encoder(self) -> CrossEncoder:
        if self._cross_encoder is None:
            self._cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
        return self._cross_encoder

    def warm(self) -> None:
        """Force both models to load. Called at API startup so the first
        request doesn't pay the download/initialization cost."""
        _ = self.embedder
        _ = self.cross_encoder

    # -- Retrieval -----------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 5, candidates_k: int = 10) -> list[str]:
        """Full pipeline: hybrid search → cross-encoder re-ranking → top_k chunk texts."""
        candidate_ids = self.hybrid_search(query, top_k=candidates_k)
        reranked_ids = self.rerank(query, candidate_ids, top_k=top_k)
        return [self.chunks[i]["text"] for i in reranked_ids]

    def dense_search(self, query: str, top_k: int = 10) -> list[int]:
        """Semantic search over the FAISS index. Returns chunk IDs, best first."""
        query_vec = self.embedder.encode([query], normalize_embeddings=True).astype(np.float32)
        _, indices = self.faiss_index.search(query_vec, top_k)
        return [int(i) for i in indices[0] if i >= 0]

    def sparse_search(self, query: str, top_k: int = 10) -> list[int]:
        """BM25 keyword search. Returns chunk IDs, best first."""
        scores = self.bm25.get_scores(tokenize(query))
        ranked = np.argsort(scores)[::-1][:top_k]
        # Drop chunks BM25 scored at zero: they share no query term at all, and
        # including them would hand reciprocal-rank credit to documents that
        # merely padded out the list.
        return [int(i) for i in ranked if scores[i] > 0]

    def hybrid_search(self, query: str, top_k: int = 10) -> list[int]:
        """Weighted reciprocal-rank fusion of dense and sparse retrieval.

        Returns chunk IDs, best first.
        """
        dense = self.dense_search(query, top_k=top_k)
        sparse = self.sparse_search(query, top_k=top_k)
        fused = reciprocal_rank_fusion([dense, sparse], [DENSE_WEIGHT, SPARSE_WEIGHT])
        return [doc_id for doc_id, _ in fused[:top_k]]

    def rerank(self, query: str, candidate_ids: list[int], top_k: int = 5) -> list[int]:
        """Cross-encoder re-ranking. Returns chunk IDs, best first."""
        if len(candidate_ids) <= 1:
            return candidate_ids[:top_k]
        pairs = [[query, self.chunks[i]["text"]] for i in candidate_ids]
        scores = self.cross_encoder.predict(pairs)
        ranked = sorted(zip(candidate_ids, scores), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in ranked[:top_k]]


_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
