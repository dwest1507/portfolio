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

They are inert until an arm asks for them: faiss and sentence-transformers are imported
inside the lazy loaders below, not at module scope, so the production image installs
neither and startup loads neither. Both are declared in the `dev` dependency group,
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
    import faiss
    from sentence_transformers import CrossEncoder, SentenceTransformer

EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Weights applied to each retriever's reciprocal-rank contribution in the `hybrid` and
# `rerank` arms. Semantic search leads on the assumption that most recruiter questions
# are paraphrases rather than exact-term lookups, with BM25 as the backstop for proper
# nouns ("TACOM", "FAISS") that embeddings blur together.
#
# These were never tuned, and deliberately were not. Under RRF, driving DENSE_WEIGHT
# toward zero makes `hybrid` converge on BM25's ordering — so on a corpus where BM25
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
    """Retrieval over the pre-built portfolio indexes.

    Only the chunks and the BM25 index are loaded on construction, because only those
    are on the serving path. The FAISS index, the embedding model and the cross-encoder
    load on first use, which in production is never — the evaluation harness is the only
    caller that reaches them.
    """

    def __init__(
        self,
        indexes_dir: Path = INDEXES_DIR,
        embedder: SentenceTransformer | None = None,
        cross_encoder: CrossEncoder | None = None,
    ) -> None:
        self._indexes_dir = indexes_dir

        # Load chunks
        with open(indexes_dir / "chunks.json") as f:
            self.chunks: list[dict] = json.load(f)

        # Load BM25 index
        with open(indexes_dir / "bm25.pkl", "rb") as f:
            self.bm25: BM25Okapi = pickle.load(f)

        self._faiss_index: faiss.Index | None = None
        self._embedder = embedder
        self._cross_encoder = cross_encoder

    # -- Lazily loaded indexes and models ------------------------------------

    @property
    def faiss_index(self) -> faiss.Index:
        """The dense index, read on first use.

        The consistency check below used to run at construction, catching a stale
        index before the server took traffic. It belongs here now: dense retrieval is
        no longer on the serving path, so a mismatch can no longer return the text of
        the wrong chunk to a visitor — it can only mislead the harness, which is
        exactly who this raises for.
        """
        if self._faiss_index is None:
            import faiss

            index = faiss.read_index(str(self._indexes_dir / "faiss.index"))
            if index.ntotal != len(self.chunks):
                raise ValueError(
                    f"Index mismatch: faiss.index has {index.ntotal} vectors but "
                    f"chunks.json has {len(self.chunks)} chunks. Run `make build-index`."
                )
            self._faiss_index = index
        return self._faiss_index

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedder

    @property
    def cross_encoder(self) -> CrossEncoder:
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder

            self._cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
        return self._cross_encoder

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

    def dense_search(self, query: str, top_k: int = 10) -> list[int]:
        """Semantic search over the FAISS index. Returns chunk IDs, best first.

        Measured, not shipped — see the module docstring.
        """
        query_vec = self.embedder.encode([query], normalize_embeddings=True).astype(np.float32)
        _, indices = self.faiss_index.search(query_vec, top_k)
        return [int(i) for i in indices[0] if i >= 0]

    def hybrid_search(self, query: str, top_k: int = 10) -> list[int]:
        """Weighted reciprocal-rank fusion of dense and sparse retrieval.

        Returns chunk IDs, best first. Measured, not shipped.
        """
        dense = self.dense_search(query, top_k=top_k)
        sparse = self.sparse_search(query, top_k=top_k)
        fused = reciprocal_rank_fusion([dense, sparse], [DENSE_WEIGHT, SPARSE_WEIGHT])
        return [doc_id for doc_id, _ in fused[:top_k]]

    def rerank(self, query: str, candidate_ids: list[int], top_k: int = 5) -> list[int]:
        """Cross-encoder re-ranking. Returns chunk IDs, best first.

        Measured, not shipped.
        """
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
