"""Tests for POST /api/chat."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.daily_cap import RESTING_MESSAGE, DailyCap
from app.llm import MAX_TOKENS, REASONING_EFFORT


def _mock_openai_stream(tokens: list[str]):
    """Build an async mock that yields token chunks like the real OpenAI stream."""

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
    mock_openai = _mock_openai_stream(tokens)

    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
        response = client.post(
            "/api/chat",
            json={"message": "What is David's background?"},
        )

    assert response.status_code == 200
    body = response.text
    parsed = _parse_data_stream(body)
    assert parsed == tokens


def test_response_content_type(client, mock_pipeline):
    mock_openai = _mock_openai_stream(["ok"])
    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
        response = client.post("/api/chat", json={"message": "Hello"})
    assert "text/plain" in response.headers["content-type"]


def test_stream_ends_with_finish_marker(client, mock_pipeline):
    mock_openai = _mock_openai_stream(["done"])
    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
        response = client.post("/api/chat", json={"message": "Hello"})
    assert 'd:{"finishReason": "stop"}' in response.text


def test_conversation_history_is_forwarded(client, mock_pipeline):
    """History should be included in the messages sent to OpenAI."""
    captured_messages = []

    async def _fake_create(**kwargs):
        captured_messages.extend(kwargs["messages"])

        async def _empty():
            return
            yield  # make it an async generator

        return _empty()

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(side_effect=_fake_create)

    history = [
        {"role": "user", "content": "What are your skills?"},
        {"role": "assistant", "content": "Python, FastAPI, FAISS..."},
    ]

    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
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

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(side_effect=_fake_create)

    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
        client.post("/api/chat", json={"message": "What is David's background?"})

    system_msg = next(m for m in captured_messages if m["role"] == "system")
    # The mock pipeline returns SAMPLE_CHUNKS[:3]; check one appears in context
    assert "AI Engineer" in system_msg["content"] or "David" in system_msg["content"]


def _capturing_openai(captured: dict):
    """An OpenAI client whose streamed completion records its request and yields nothing."""

    async def _fake_create(**kwargs):
        captured.update(kwargs)

        async def _empty():
            return
            yield

        return _empty()

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(side_effect=_fake_create)
    return mock_openai


def test_production_streams_the_configured_model_with_the_eval_sampling_settings(
    client, mock_pipeline
):
    """Visitors are served what the generation eval measures (ADR-0007, ADR-0008).

    The configured model answers, streamed, with the pinned reasoning effort and the
    shared completion cap. No temperature is sent: OpenAI's reasoning models reject any
    but the default, so the reasoning effort is what production and the eval pin instead
    (ADR-0007 amendment, 2026-10-10).
    """
    captured = {}
    with (
        patch("app.llm.AsyncOpenAI", return_value=_capturing_openai(captured)),
        patch("app.llm.OPENAI_MODEL", "sentinel-model"),
    ):
        client.post("/api/chat", json={"message": "What is David's background?"})

    assert captured["model"] == "sentinel-model"
    assert captured["stream"] is True
    assert captured["reasoning_effort"] == REASONING_EFFORT
    assert captured["max_completion_tokens"] == MAX_TOKENS
    assert "temperature" not in captured


# ---------------------------------------------------------------------------
# Global daily cap
# ---------------------------------------------------------------------------


class _Clock:
    """A settable UTC date, so a test can move the cap into tomorrow."""

    def __init__(self, today: date):
        self.today = today

    def __call__(self) -> date:
        return self.today


def test_requests_past_the_daily_cap_get_the_resting_message(client, mock_pipeline):
    """A paid model behind an anonymous endpoint: past the cap, nothing reaches OpenAI.

    The visitor is told the assistant is resting rather than shown an error, and the
    stream still ends normally so the frontend renders it as an ordinary reply.
    """
    mock_openai = _mock_openai_stream(["Answered."])
    with (
        patch("app.routes.chat.daily_cap", DailyCap(limit=1)),
        patch("app.llm.AsyncOpenAI", return_value=mock_openai),
    ):
        first = client.post("/api/chat", json={"message": "Hello"})
        second = client.post("/api/chat", json={"message": "Hello again"})

    assert _parse_data_stream(first.text) == ["Answered."]
    assert second.status_code == 200
    assert _parse_data_stream(second.text) == [RESTING_MESSAGE]
    assert 'd:{"finishReason": "stop"}' in second.text
    assert "resting for today" in RESTING_MESSAGE
    assert mock_openai.chat.completions.create.await_count == 1


def test_the_daily_cap_skips_retrieval_once_reached(client, mock_pipeline):
    """A capped request does no work at all, not even the cheap retrieval step."""
    with patch("app.routes.chat.daily_cap", DailyCap(limit=0)):
        client.post("/api/chat", json={"message": "Hello"})

    mock_pipeline.retrieve.assert_not_called()


def test_the_daily_cap_resets_on_the_next_utc_day(client, mock_pipeline):
    clock = _Clock(date(2026, 10, 11))
    with patch("app.routes.chat.daily_cap", DailyCap(limit=1, today=clock)):
        with patch("app.llm.AsyncOpenAI", return_value=_mock_openai_stream(["one"])):
            client.post("/api/chat", json={"message": "Hello"})
        capped = client.post("/api/chat", json={"message": "Hello"})

        clock.today = date(2026, 10, 12)
        with patch("app.llm.AsyncOpenAI", return_value=_mock_openai_stream(["two"])):
            tomorrow = client.post("/api/chat", json={"message": "Hello"})

    assert _parse_data_stream(capped.text) == [RESTING_MESSAGE]
    assert _parse_data_stream(tomorrow.text) == ["two"]


def test_the_daily_cap_is_configured_by_environment():
    """The production cap comes from DAILY_REQUEST_CAP, so it can move without a deploy."""
    from app.config import DAILY_REQUEST_CAP
    from app.routes.chat import daily_cap

    assert daily_cap.limit == DAILY_REQUEST_CAP


# ---------------------------------------------------------------------------
# OpenAI API error
# ---------------------------------------------------------------------------


def test_openai_error_yields_error_event(client, mock_pipeline):
    """When OpenAI fails, the stream signals an error via the data stream protocol."""
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("API down"))

    with patch("app.llm.AsyncOpenAI", return_value=mock_openai):
        response = client.post("/api/chat", json={"message": "Hello"})

    # HTTP 200 because the response already started streaming
    assert response.status_code == 200
    # AI SDK data stream v1 error type: 3:"message"\n
    assert '3:"Generation failed"' in response.text
