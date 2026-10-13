"""Tests for the RAG pipeline components."""

import json
import os
import pickle
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Chunking (scripts/build_index.py)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_index import (
    CHUNK_SIZE,
    MDX_DIR,
    QA_PATH,
    RESUME_PATH,
    _strip_mdx,
    chunk_document,
    load_documents,
    project_titles,
)

QA_FIXTURE = """# Chatbot Q&A — David West

> This document is the primary knowledge source for the chatbot.

---

## About David

**Where is David based?**
I work in the Metro-Detroit area in Michigan.

**What kinds of AI problems is David most excited to work on?**

**What industries has David worked in?**
I've worked in the defense industry since college.

It started at **TACOM**, then [Booz Allen](https://www.boozallen.com).

---

## Technical Skills

### Languages

**What programming languages does David know?**
Python, R, Typescript, and SQL.
"""


def test_the_question_document_yields_one_chunk_per_question_and_answer():
    chunks = chunk_document(QA_FIXTURE, source="qa")

    assert chunks == [
        {
            "text": "Where is David based?\nI work in the Metro-Detroit area in Michigan.",
            "source": "qa",
        },
        {
            "text": "What industries has David worked in?\n"
            "I've worked in the defense industry since college.\n"
            "It started at TACOM, then Booz Allen.",
            "source": "qa",
        },
        {
            "text": "What programming languages does David know?\nPython, R, Typescript, and SQL.",
            "source": "qa",
        },
    ]


def test_an_over_long_question_and_answer_splits_by_sentence_with_the_question_repeated():
    question = "Why is David looking for a new opportunity?"
    sentences = [
        f"Reason number {i} is a complete sentence about his career goals." for i in range(40)
    ]
    text = f"**{question}**\n{' '.join(sentences)}\n"

    chunks = chunk_document(text, source="qa")

    assert len(chunks) > 1
    assert all(len(c["text"]) <= CHUNK_SIZE for c in chunks)
    assert all(c["text"].startswith(question + "\n") for c in chunks)
    # Every sentence lands in exactly one piece, whole and in order.
    answers = [c["text"].removeprefix(question + "\n") for c in chunks]
    assert " ".join(answers) == " ".join(sentences)


PROJECT_FIXTURE = """## Overview

Chat with Nietzsche is a conversational AI over his complete works.

## The RAG Pipeline

1. **Hybrid search**: FAISS and BM25 over roughly 7,300 chunks.
2. **Re-ranking**: it uses a cross-encoder.

```python
print("code is not prose")
```

### Why re-rank

Shared vocabulary is not relevance.
"""


def test_a_project_write_up_yields_one_chunk_per_section_headed_by_project_and_section():
    chunks = chunk_document(
        PROJECT_FIXTURE, source="project:nietzsche-chat", title="Chat with Nietzsche"
    )

    assert chunks == [
        {
            "text": "Chat with Nietzsche — Overview\n"
            "Chat with Nietzsche is a conversational AI over his complete works.",
            "source": "project:nietzsche-chat",
        },
        {
            "text": "Chat with Nietzsche — The RAG Pipeline\n"
            "1. Hybrid search: FAISS and BM25 over roughly 7,300 chunks.\n"
            "2. Re-ranking: it uses a cross-encoder.\n"
            "Why re-rank\n"
            "Shared vocabulary is not relevance.",
            "source": "project:nietzsche-chat",
        },
    ]


RESUME_FIXTURE = """DAVID P WEST
Waterford, MI  ●  someone@example.com
SUMMARY
I'm a Lead AI Engineer.

EXPERIENCE

AI Engineer, Lead
January 2026 – Present (40 Hrs/Week)
Booz Allen Hamilton
Royal Oak MI Office

Notable projects:
Extract information from 260k old paper records.


Operations Research Analyst (GS-1515-11)
May 2020 – January 2021 (40 Hrs/Week)
Army Tank-Automotive & Armaments Command
Program Executive Office: Ground Combat Systems

Maintain a self-made Excel cost model.

Develop a database for a Continuous Process Improvement (CPI) project.

EDUCATION\t\t\t

Western Michigan University (WMU)
GPA: 3.57
"""


def test_the_resume_yields_one_chunk_per_section_and_per_role():
    chunks = chunk_document(RESUME_FIXTURE, source="resume")

    assert [c["text"] for c in chunks] == [
        "Resume — David P West\nWaterford, MI  ●  someone@example.com",
        "Resume — Summary\nI'm a Lead AI Engineer.",
        (
            "Booz Allen Hamilton — AI Engineer, Lead\n"
            "January 2026 – Present (40 Hrs/Week)\n"
            "Royal Oak MI Office\n"
            "Notable projects:\n"
            "Extract information from 260k old paper records."
        ),
        (
            "Army Tank-Automotive & Armaments Command — Operations Research Analyst (GS-1515-11)\n"
            "May 2020 – January 2021 (40 Hrs/Week)\n"
            "Program Executive Office: Ground Combat Systems\n"
            "Maintain a self-made Excel cost model.\n"
            "Develop a database for a Continuous Process Improvement (CPI) project."
        ),
        "Resume — Education\nWestern Michigan University (WMU)\nGPA: 3.57",
    ]
    assert {c["source"] for c in chunks} == {"resume"}


# The committed sources. A formatting change that a rule no longer recognises must fail
# here rather than quietly index a document as one giant Chunk, or drop part of it. The
# expected structure is counted from the raw files with deliberately looser patterns than
# the chunker's, so the two can disagree.


def _committed_chunks(source: str) -> list[dict]:
    doc = next(d for d in load_documents() if d["source"] == source)
    return chunk_document(doc["text"], doc["source"], doc.get("title"))


def _headings(chunks: list[dict]) -> list[str]:
    """Each distinct heading, in order: an over-long unit's pieces share one."""
    return list(dict.fromkeys(c["text"].split("\n", 1)[0] for c in chunks))


def test_the_committed_question_document_parses_into_its_questions():
    # A question whose next non-blank line is not prose has no answer yet, and is skipped.
    lines = [line for line in QA_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = [
        line.strip().strip("*")
        for line, after in zip(lines, lines[1:] + [""])
        if line.startswith("**") and after and not after.startswith(("**", "#", "---"))
    ]

    chunks = _committed_chunks("qa")

    assert len(questions) > 50
    assert _headings(chunks) == questions
    assert all("**" not in c["text"] and "\n" in c["text"].strip() for c in chunks)


@pytest.mark.parametrize("path", sorted(MDX_DIR.glob("*.mdx")), ids=lambda p: p.stem)
def test_each_committed_project_write_up_parses_into_its_sections(path: Path):
    title = project_titles()[path.stem]
    sections = [
        line.removeprefix("## ").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]

    chunks = _committed_chunks(f"project:{path.stem}")

    assert len(sections) > 1
    assert _headings(chunks) == [f"{title} — {s}" for s in sections]


def test_the_committed_resume_parses_into_its_sections_and_roles():
    raw = RESUME_PATH.read_text(encoding="utf-8")
    date_ranges = [
        line for line in raw.splitlines() if re.search(r"\d{4}\s*[–-]\s*(?:Present|[A-Z])", line)
    ]

    headings = _headings(_committed_chunks("resume"))
    roles = [h for h in headings if not h.startswith("Resume — ")]

    for section in ("Summary", "Technical Skills", "Education", "Leadership"):
        assert f"Resume — {section}" in headings
    assert len(roles) == len(date_ranges) > 1
    assert all(
        employer in {"Booz Allen Hamilton", "Army Tank-Automotive & Armaments Command"}
        for employer in (h.split(" — ")[0] for h in roles)
    )


@pytest.mark.parametrize(
    ("source", "title"),
    [("qa", None), ("project:nietzsche-chat", "Chat with Nietzsche"), ("resume", None)],
)
def test_a_document_that_has_lost_its_structure_fails_the_build(source, title):
    """Questions no longer bold, headings demoted, a resume reflowed: index nothing quietly."""
    with pytest.raises(ValueError, match="no structure"):
        chunk_document("Some prose that has lost every heading.\n", source, title)


def test_no_committed_chunk_exceeds_the_size_limit_except_one_whole_sentence():
    for doc in load_documents():
        for chunk in chunk_document(doc["text"], doc["source"], doc.get("title")):
            if len(chunk["text"]) > CHUNK_SIZE:
                body = chunk["text"].split("\n", 1)[1]
                assert len(re.split(r"(?<=[.!?])\s+", body)) == 1, chunk["text"][:80]


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
    """Create minimal fake indexes in a temp directory: chunks and BM25, what production
    reads. Tests that need Corpus embeddings write their own (see `_onnx_pipeline`)."""
    chunks = [
        {"text": "David is an AI Engineer.", "source": "resume"},
        {"text": "David built a RAG pipeline using FAISS and BM25.", "source": "resume"},
        {"text": "David has 5 years of data science experience.", "source": "resume"},
    ]
    with open(tmp_path / "chunks.json", "w") as f:
        json.dump(chunks, f)

    # BM25 index
    from rank_bm25 import BM25Okapi

    from app.rag.tokenize import tokenize

    corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)
    with open(tmp_path / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)

    return tmp_path, chunks


# ---------------------------------------------------------------------------
# ONNX Runtime retrieval (the Candidate Arms)
# ---------------------------------------------------------------------------


def _onnx_pipeline(indexes_dir, embeddings, query_vector=None, scores=None):
    """A pipeline whose ONNX models are fakes and whose ONNX corpus embeddings are given."""
    from app.rag.pipeline import RAGPipeline

    np.save(indexes_dir / "onnx_embeddings.npy", np.asarray(embeddings, dtype=np.float32))
    embedder = MagicMock()
    embedder.encode.return_value = np.asarray([query_vector or [1.0, 0.0]], dtype=np.float32)
    cross_encoder = MagicMock()
    cross_encoder.predict.return_value = np.asarray(scores or [], dtype=np.float32)
    return RAGPipeline(
        indexes_dir=indexes_dir, onnx_embedder=embedder, onnx_cross_encoder=cross_encoder
    )


def test_onnx_dense_search_ranks_chunks_by_similarity_to_the_query(fake_indexes):
    indexes_dir, _chunks = fake_indexes
    pipeline = _onnx_pipeline(indexes_dir, [[0.0, 1.0], [0.6, 0.8], [1.0, 0.0]])

    assert pipeline.onnx_dense_search("q", top_k=2) == [2, 1]


def test_onnx_hybrid_search_fuses_the_keyword_ranking_into_the_dense_one(fake_indexes):
    """BM25 lifts a chunk the dense ranking put last."""
    indexes_dir, _chunks = fake_indexes
    # Dense ranks chunk 1 ("...FAISS and BM25.") last; only BM25 matches "FAISS".
    pipeline = _onnx_pipeline(indexes_dir, [[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]])
    assert pipeline.onnx_dense_search("FAISS", top_k=3) == [0, 2, 1]

    assert pipeline.onnx_hybrid_search("FAISS", top_k=3) == [0, 1, 2]


def test_onnx_rerank_orders_candidates_by_the_onnx_cross_encoder(fake_indexes):
    indexes_dir, _chunks = fake_indexes
    pipeline = _onnx_pipeline(indexes_dir, [[1.0, 0.0]] * 3, scores=[0.1, 2.5, -1.0])

    assert pipeline.onnx_rerank("q", [0, 1, 2], top_k=2) == [1, 0]


def test_stale_onnx_embeddings_raise_for_the_harness(fake_indexes):
    """The mismatch guard runs on first use, off the startup path, since dense retrieval
    is not served. It still has to run: embeddings out of step with chunks.json return
    the wrong chunk IDs, which would corrupt a measured run rather than an answer."""
    indexes_dir, chunks = fake_indexes
    pipeline = _onnx_pipeline(indexes_dir, [[1.0, 0.0]] * (len(chunks) + 1))

    with pytest.raises(ValueError, match="Index mismatch"):
        _ = pipeline.onnx_embeddings


def test_the_onnx_embedder_mean_pools_real_tokens_and_normalizes():
    """Padding positions carry hidden states too; averaging them in would make a short
    text's embedding depend on the longest text in its batch."""
    from types import SimpleNamespace

    from app.rag.onnx_models import OnnxEmbedder

    tokenizer = MagicMock()
    tokenizer.encode_batch.return_value = [
        SimpleNamespace(ids=[5, 6, 0], attention_mask=[1, 1, 0], type_ids=[0, 0, 0]),
    ]
    session = MagicMock()
    session.get_inputs.return_value = [
        SimpleNamespace(name="input_ids"),
        SimpleNamespace(name="attention_mask"),
    ]
    # Two real tokens averaging to (3, 4); the padding state would drag it elsewhere.
    session.run.return_value = [np.array([[[2.0, 4.0], [4.0, 4.0], [100.0, -100.0]]])]

    embedding = OnnxEmbedder(tokenizer, session).encode(["short text"])

    np.testing.assert_allclose(embedding, [[0.6, 0.8]], rtol=1e-6)
    sent = session.run.call_args.args[1]
    assert set(sent) == {"input_ids", "attention_mask"}, "only the inputs the model declares"


def test_retrieve_returns_top_k(fake_indexes):
    indexes_dir, _chunks = fake_indexes

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(indexes_dir=indexes_dir)
    results = pipeline.retrieve("RAG pipeline FAISS", top_k=2)

    assert 0 < len(results) <= 2
    assert all(isinstance(r, str) for r in results)


def test_retrieve_needs_neither_a_model_nor_the_dense_index(fake_indexes):
    """What the production container actually has: chunks, a BM25 index, no weights.

    The eval measured semantic search, fusion and re-ranking against plain keyword
    search and none of them won, so serving must not touch any of them. This asserts
    it the only way that cannot rot — with no onnx_embeddings.npy on disk and both model
    slots empty. If a dense stage ever creeps back onto the serving path, this raises
    instead of quietly downloading model weights on a Railway cold start.
    """
    indexes_dir, _chunks = fake_indexes
    assert not (indexes_dir / "onnx_embeddings.npy").exists()

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(indexes_dir=indexes_dir)
    assert pipeline.retrieve("RAG pipeline FAISS", top_k=2)


def test_retrieve_returns_nothing_when_the_query_shares_no_term(fake_indexes):
    """An off-topic question yields no context rather than the least-bad chunks.

    Padding the prompt is how a model answers a question the corpus cannot support;
    an empty context leaves the system prompt's "say so honestly" unopposed.
    """
    indexes_dir, _chunks = fake_indexes

    from app.rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(indexes_dir=indexes_dir)
    assert pipeline.retrieve("zebra photosynthesis quarterly") == []


def test_a_stale_bm25_index_refuses_to_construct(fake_indexes):
    """The served index gets its mismatch guard at construction, not first use.

    `sparse_search` hands BM25's ranked positions straight to `self.chunks[i]`, so a
    pickle built from a different revision of chunks.json either raises IndexError on a
    live request or serves the text of the wrong chunk with no error at all. Neither
    should be reachable: refuse at construction.
    """
    from rank_bm25 import BM25Okapi

    from app.rag.tokenize import tokenize

    indexes_dir, chunks = fake_indexes
    stale = BM25Okapi([tokenize(c["text"]) for c in chunks] + [["extra", "document"]])
    with open(indexes_dir / "bm25.pkl", "wb") as f:
        pickle.dump(stale, f)

    from app.rag.pipeline import RAGPipeline

    with pytest.raises(ValueError, match="bm25.pkl has"):
        RAGPipeline(indexes_dir=indexes_dir)


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


# ---------------------------------------------------------------------------
# Reciprocal-rank fusion
# ---------------------------------------------------------------------------


def test_rrf_sparse_only_hit_reaches_candidates():
    """A chunk only BM25 found must survive into the candidate set.

    This is the whole justification for keeping a sparse arm: it is the backstop
    for proper nouns and rare terms the embedding model smooths away. With
    RRF_K=60 the weight ratio (0.7/0.3) dwarfed the rank term across a 10-item
    list, so every dense hit outscored every sparse hit and the sparse-only
    chunk was truncated away before the re-ranker ever saw it.
    """
    from app.rag.pipeline import reciprocal_rank_fusion

    dense = list(range(100, 110))  # 10 dense hits, none of them chunk 7
    sparse = [7, 101]  # BM25's top hit is a chunk dense missed entirely

    fused = [doc_id for doc_id, _ in reciprocal_rank_fusion([dense, sparse], [0.7, 0.3])]

    assert 7 in fused[:10], "BM25's top hit must make the 10-candidate set"


def test_rrf_dense_still_leads_the_ordering():
    """Fixing the above must not flip the arms: dense is still the primary."""
    from app.rag.pipeline import reciprocal_rank_fusion

    dense = list(range(100, 110))
    sparse = [7, 101]

    fused = [doc_id for doc_id, _ in reciprocal_rank_fusion([dense, sparse], [0.7, 0.3])]

    assert fused[0] == 100, "the top dense hit should still rank first"
    assert fused.index(7) > 0, "a sparse-only hit should not displace the top dense hit"


def test_rrf_agreement_between_arms_boosts_a_chunk():
    """A chunk both retrievers found should outrank one only dense found."""
    from app.rag.pipeline import reciprocal_rank_fusion

    dense = [10, 11, 12]
    sparse = [12, 99]

    fused = [doc_id for doc_id, _ in reciprocal_rank_fusion([dense, sparse], [0.7, 0.3])]

    assert fused.index(12) < fused.index(11), "agreement should pull chunk 12 up past 11"


def test_the_pipeline_module_imports_without_the_eval_only_libraries():
    """The production image installs neither onnxruntime nor tokenizers.

    Both are in the `dev` dependency group, and the Dockerfile syncs with --no-dev, so a
    module-level `import onnxruntime` reachable from pipeline.py would crash the container
    on boot while every test here still passed — the dev group has both installed. Run in
    a subprocess with the ML libraries made unimportable, which is the only way to
    reproduce the production environment from inside a dev one. The torch-era names stay
    in the guard so none of them can return to the serving path either.

    The subprocess walks the whole boot path, not just the imports: `app.main`'s lifespan
    calls `get_pipeline()`, and a request calls `retrieve()`. Importing the module alone
    would miss a lazy `import onnxruntime` inside `RAGPipeline.__init__` — which is exactly the
    shape of mistake this guards, and would fail only once Railway ran it.
    """
    import subprocess
    import sys

    program = """
import sys

class Guard:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {
            "faiss", "sentence_transformers", "torch", "transformers", "onnxruntime", "tokenizers"
        }:
            raise AssertionError(f"{name} must not be imported to serve a request")
        return None

sys.meta_path.insert(0, Guard())
import app.main  # noqa: F401

# The startup path (app.main's lifespan) and the request path, against the real
# committed indexes — both must complete with the ML stack unimportable.
from app.rag.pipeline import get_pipeline

get_pipeline().retrieve("What does David do?")
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=False,  # the assertion below reports the traceback, which `check` would hide
        cwd=str(Path(__file__).resolve().parent.parent),
        env={
            **os.environ,
            "OPENAI_API_KEY": "test_key",
            "ALLOWED_ORIGINS": "http://localhost:3000",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
