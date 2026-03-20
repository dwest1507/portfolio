"""Tests for POST /api/chat."""
import json
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_groq_stream(tokens: list[str]):
    """Build an async mock that yields token chunks like the real Groq stream."""
    async def _stream():
        for token in tokens:
            chunk = MagicMock()
            chunk.choices[0].delta.content = token
            yield chunk

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_stream())
    return mock_client


def _parse_data_stream(text: str) -> list[str]:
    """Parse Vercel AI SDK data stream v1 text tokens."""
    tokens = []
    for line in text.strip().splitlines():
        line = line.strip()
        if line.startswith("0:"):
            tokens.append(json.loads(line[2:]))
    return tokens


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_empty_message_returns_422(client):
    """Pydantic min_length=1 rejects empty strings."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_message_too_long_returns_422(client):
    """Pydantic max_length=500 rejects messages over 500 chars."""
    response = client.post("/api/chat", json={"message": "x" * 501})
    assert response.status_code == 422


def test_missing_message_field_returns_422(client):
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Valid request
# ---------------------------------------------------------------------------

def test_valid_request_streams_response(client, mock_pipeline):
    tokens = ["David", " is", " an", " AI", " Engineer."]
    mock_groq = _mock_groq_stream(tokens)

    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post(
            "/api/chat",
            json={"message": "What is David's background?"},
        )

    assert response.status_code == 200
    body = response.text
    parsed = _parse_data_stream(body)
    assert parsed == tokens


def test_response_content_type(client, mock_pipeline):
    mock_groq = _mock_groq_stream(["ok"])
    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post("/api/chat", json={"message": "Hello"})
    assert "text/plain" in response.headers["content-type"]


def test_stream_ends_with_finish_marker(client, mock_pipeline):
    mock_groq = _mock_groq_stream(["done"])
    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post("/api/chat", json={"message": "Hello"})
    assert 'd:{"finishReason": "stop"}' in response.text


def test_conversation_history_is_forwarded(client, mock_pipeline):
    """History should be included in the messages sent to Groq."""
    captured_messages = []

    async def _fake_create(**kwargs):
        captured_messages.extend(kwargs["messages"])

        async def _empty():
            return
            yield  # make it an async generator

        return _empty()

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=_fake_create)

    history = [
        {"role": "user", "content": "What are your skills?"},
        {"role": "assistant", "content": "Python, FastAPI, FAISS..."},
    ]

    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        client.post(
            "/api/chat",
            json={"message": "Tell me more", "history": history},
        )

    roles = [m["role"] for m in captured_messages]
    assert "system" in roles
    assert roles.count("user") >= 2  # history user + new message
    assert "assistant" in roles


def test_rag_context_included_in_system_prompt(client, mock_pipeline):
    """The system message must include context retrieved by the pipeline."""
    captured_messages = []

    async def _fake_create(**kwargs):
        captured_messages.extend(kwargs["messages"])

        async def _empty():
            return
            yield

        return _empty()

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=_fake_create)

    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        client.post("/api/chat", json={"message": "What is David's background?"})

    system_msg = next(m for m in captured_messages if m["role"] == "system")
    # The mock pipeline returns SAMPLE_CHUNKS[:3]; check one appears in context
    assert "AI Engineer" in system_msg["content"] or "David" in system_msg["content"]


# ---------------------------------------------------------------------------
# Groq API error
# ---------------------------------------------------------------------------

def test_groq_error_yields_error_event(client, mock_pipeline):
    """When Groq fails, the stream signals an error via the data stream protocol."""
    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=Exception("API down"))

    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post("/api/chat", json={"message": "Hello"})

    # HTTP 200 because the response already started streaming
    assert response.status_code == 200
    # AI SDK data stream v1 error type: 3:"message"\n
    assert '3:"Generation failed"' in response.text
