"""Tests for the RAG pipeline components."""

import json
import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Chunking (scripts/build_index.py)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_index import _chunk_text, _strip_mdx


def test_chunk_text_respects_max_size():
    # Build multi-paragraph text with sentence endings (realistic input)
    para = "David is an experienced AI engineer. " * 10  # ~370 chars
    long_text = "\n\n".join([para] * 8)  # 8 paragraphs, ~3000 chars total
    chunks = _chunk_text(long_text, source="test")
    # Allow up to 1.3× CHUNK_SIZE due to overlap
    assert all(len(c["text"]) <= 1300 for c in chunks), "Chunks must stay near size limit"


def test_chunk_text_preserves_source():
    chunks = _chunk_text("Hello world.\n\nSecond paragraph.", source="resume")
    assert all(c["source"] == "resume" for c in chunks)


def test_chunk_text_produces_overlap():
    """Last chars of chunk N should appear at start of chunk N+1."""
    # Create text that forces at least 2 chunks
    para_a = "A " * 600  # 1200 chars — exceeds CHUNK_SIZE alone
    para_b = "B " * 600
    text = para_a.strip() + "\n\n" + para_b.strip()
    chunks = _chunk_text(text, source="test")
    assert len(chunks) >= 2
    # Overlap: chunk[1] should start with tail of chunk[0] content
    first_end = chunks[0]["text"][-80:]
    assert first_end[:5] in chunks[1]["text"]


def test_strip_mdx_removes_code_blocks():
    text = "Intro\n\n```python\ncode here\n```\n\nOutro"
    result = _strip_mdx(text)
    assert "code here" not in result
    assert "Intro" in result
    assert "Outro" in result


def test_strip_mdx_removes_links_keeps_text():
    text = "Visit [my portfolio](https://example.com) today."
    result = _strip_mdx(text)
    assert "my portfolio" in result
    assert "https://example.com" not in result


# ---------------------------------------------------------------------------
# RAGPipeline unit tests (with mocked models/indexes)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_indexes(tmp_path):
    """Create minimal fake indexes in a temp directory."""
    import faiss as faiss_lib

    chunks = [
        {"text": "David is an AI Engineer.", "source": "resume"},
        {"text": "David built a RAG pipeline using FAISS and BM25.", "source": "resume"},
        {"text": "David has 5 years of data science experience.", "source": "resume"},
    ]
    with open(tmp_path / "chunks.json", "w") as f:
        json.dump(chunks, f)

    # FAISS index with random 768-dim vectors
    dim = 768
    vectors = np.random.rand(len(chunks), dim).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    index = faiss_lib.IndexFlatIP(dim)
    index.add(vectors)
    faiss_lib.write_index(index, str(tmp_path / "faiss.index"))

    # BM25 index
    from rank_bm25 import BM25Okapi

    from app.rag.tokenize import tokenize

    corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)
    with open(tmp_path / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)

    return tmp_path, chunks


def test_hybrid_search_returns_chunks(fake_indexes):
    indexes_dir, _chunks = fake_indexes

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.random.rand(1, 768).astype(np.float32)

    mock_cross_encoder = MagicMock()
    mock_cross_encoder.predict.return_value = np.array([0.9, 0.7, 0.5])

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(
        indexes_dir=indexes_dir, embedder=mock_embedder, cross_encoder=mock_cross_encoder
    )
    results = pipeline.hybrid_search("AI Engineer experience", top_k=3)

    assert len(results) > 0
    assert all(isinstance(doc_id, int) for doc_id in results)
    assert all(0 <= doc_id < 3 for doc_id in results)


def test_reranking_orders_by_cross_encoder_score(fake_indexes):
    """The chunk with the highest cross-encoder score should appear first."""
    indexes_dir, _chunks = fake_indexes

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.random.rand(1, 768).astype(np.float32)

    # Cross-encoder: make the last candidate score highest
    mock_cross_encoder = MagicMock()
    mock_cross_encoder.predict.return_value = np.array([0.1, 0.5, 0.9])

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(
        indexes_dir=indexes_dir, embedder=mock_embedder, cross_encoder=mock_cross_encoder
    )
    reranked = pipeline.rerank("query", [0, 1, 2], top_k=3)

    # The candidate that got score 0.9 (chunk ID 2) should be first
    assert reranked[0] == 2


def test_retrieve_returns_top_k(fake_indexes):
    indexes_dir, _chunks = fake_indexes

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.random.rand(1, 768).astype(np.float32)

    mock_cross_encoder = MagicMock()
    mock_cross_encoder.predict.side_effect = lambda pairs: np.random.rand(len(pairs))

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(
        indexes_dir=indexes_dir, embedder=mock_embedder, cross_encoder=mock_cross_encoder
    )
    results = pipeline.retrieve("What is David's background?", top_k=2)

    assert len(results) <= 2
    assert all(isinstance(r, str) for r in results)


def test_prompt_includes_context_and_history(fake_indexes):
    """build_messages includes context in the system message and preserves history order."""
    from app.llm import SYSTEM_PROMPT, Message, build_messages

    context = "David is an AI Engineer.\n\n---\n\nDavid has worked on RAG pipelines."
    history = [
        Message(role="user", content="What skills does David have?"),
        Message(role="assistant", content="Python, FastAPI, FAISS."),
    ]
    new_message = "Tell me about his projects."

    messages = build_messages(context, history, new_message)

    assert messages[0]["role"] == "system"
    assert SYSTEM_PROMPT in messages[0]["content"]
    assert "David is an AI Engineer" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "What skills does David have?"}
    assert messages[2] == {"role": "assistant", "content": "Python, FastAPI, FAISS."}
    assert messages[-1] == {"role": "user", "content": new_message}
