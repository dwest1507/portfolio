"""RAG pipeline: hybrid search (FAISS + BM25) + cross-encoder re-ranking."""
import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from ..config import INDEXES_DIR


class RAGPipeline:
    def __init__(self) -> None:
        # Load chunks
        with open(INDEXES_DIR / "chunks.json") as f:
            self.chunks: list[dict] = json.load(f)

        # Load FAISS index (inner product = cosine sim on normalized vectors)
        self.faiss_index = faiss.read_index(str(INDEXES_DIR / "faiss.index"))

        # Load BM25 index
        with open(INDEXES_DIR / "bm25.pkl", "rb") as f:
            self.bm25: BM25Okapi = pickle.load(f)

        self.embedder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Full pipeline: hybrid search → cross-encoder re-ranking → top_k chunks."""
        candidates = self._hybrid_search(query, top_k=10)
        reranked = self._rerank(query, candidates, top_k=top_k)
        return [c["text"] for c in reranked]

    def _hybrid_search(self, query: str, top_k: int = 10) -> list[dict]:
        """70% semantic (FAISS) + 30% keyword (BM25)."""
        # --- Semantic search ---
        query_vec = self.embedder.encode([query], normalize_embeddings=True).astype(
            np.float32
        )
        faiss_scores, faiss_indices = self.faiss_index.search(query_vec, top_k)
        faiss_scores = faiss_scores[0]
        faiss_indices = faiss_indices[0]

        # --- BM25 search ---
        tokenized = query.lower().split()
        bm25_scores_all = self.bm25.get_scores(tokenized)
        bm25_top_indices = np.argsort(bm25_scores_all)[::-1][:top_k]
        bm25_top_scores = bm25_scores_all[bm25_top_indices]

        # --- Normalize to [0, 1] ---
        def _norm(scores: np.ndarray) -> np.ndarray:
            lo, hi = scores.min(), scores.max()
            return np.zeros_like(scores) if hi == lo else (scores - lo) / (hi - lo)

        faiss_norm = _norm(faiss_scores)
        bm25_norm = _norm(bm25_top_scores)

        # --- Combine with 70/30 weighting ---
        combined: dict[int, float] = {}
        for idx, score in zip(faiss_indices, faiss_norm):
            if idx >= 0:
                combined[int(idx)] = combined.get(int(idx), 0.0) + 0.7 * float(score)
        for idx, score in zip(bm25_top_indices, bm25_norm):
            combined[int(idx)] = combined.get(int(idx), 0.0) + 0.3 * float(score)

        sorted_items = sorted(combined.items(), key=lambda x: x[1], reverse=True)[
            :top_k
        ]
        return [self.chunks[idx] for idx, _ in sorted_items]

    def _rerank(
        self, query: str, candidates: list[dict], top_k: int = 5
    ) -> list[dict]:
        """Cross-encoder re-ranking."""
        if len(candidates) <= 1:
            return candidates[:top_k]
        pairs = [[query, c["text"]] for c in candidates]
        scores = self.cross_encoder.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked[:top_k]]


_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
