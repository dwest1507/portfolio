"""Shared fixtures for the test suite."""
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set required env vars before importing the app
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


SAMPLE_CHUNKS = [
    {
        "text": "David West is an AI Engineer with 5+ years of data science experience. "
                "He leads the Data ReconnAIssance capability at Booz Allen Hamilton.",
        "source": "resume",
    },
    {
        "text": "David has expertise in Python, FastAPI, FAISS, LangChain, and Groq. "
                "He has built RAG pipelines and LLM-powered applications.",
        "source": "resume",
    },
    {
        "text": "Generate Music with AI is a full-stack app using Next.js, FastAPI, "
                "Modal for GPU inference, and Groq for LLM-based prompt generation.",
        "source": "project:ai-music-gen",
    },
    {
        "text": "Chat with Nietzsche uses FAISS + BM25 hybrid search with cross-encoder "
                "re-ranking for a RAG pipeline over Nietzsche's complete works.",
        "source": "project:nietzsche-chat",
    },
    {
        "text": "David holds a Secret clearance and has 8+ years in the defense industry "
                "working on Army and Air Force programs.",
        "source": "resume",
    },
]


@pytest.fixture
def mock_pipeline():
    """RAGPipeline that returns sample chunks without loading real models."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = [c["text"] for c in SAMPLE_CHUNKS[:3]]
    return pipeline


@pytest.fixture
def client(mock_pipeline):
    """TestClient with mocked RAG pipeline and Groq."""
    with patch("app.rag.pipeline.get_pipeline", return_value=mock_pipeline):
        # Also patch the pipeline import in the chat route
        with patch("app.routes.chat.get_pipeline", return_value=mock_pipeline):
            from app.main import app
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c
