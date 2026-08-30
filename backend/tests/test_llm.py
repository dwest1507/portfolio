"""Tests for app.llm — model wiring and a live provider smoke check."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from dotenv import dotenv_values
from groq import AsyncGroq

from app.llm import build_messages, generate_stream


@pytest.mark.asyncio
async def test_model_comes_from_config_not_hardcoded():
    """Regression: the Groq model must be the configured one.

    A hardcoded model silently rots when the provider decommissions it
    (llama-3.3-70b-versatile, Aug 2026) and there is no way to swap it
    without a code change.
    """
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)

        async def _empty():
            return
            yield

        return _empty()

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=_fake_create)

    with (
        patch("app.llm.AsyncGroq", return_value=mock_groq),
        patch("app.llm.GROQ_MODEL", "sentinel-model"),
    ):
        async for _ in generate_stream(build_messages("ctx", [], "hi")):
            pass

    assert captured["model"] == "sentinel-model"


@pytest.mark.live
@pytest.mark.asyncio
async def test_configured_model_exists_at_groq():
    """Live smoke check: the configured model is real and streams.

    Deselected by default; run with `pytest -m live` and a real GROQ_API_KEY.
    This is the only seam that catches a provider-side model decommission —
    every other test mocks Groq.
    """
    # conftest pins a fake GROQ_API_KEY before .env loads, so read the real one here.
    key = dotenv_values(Path(__file__).parent.parent / ".env").get("GROQ_API_KEY")
    if not key:
        pytest.skip("needs a real GROQ_API_KEY in backend/.env")

    messages = build_messages("David is an engineer.", [], "Hi")
    tokens = [t async for t in generate_stream(messages, client=AsyncGroq(api_key=key))]
    assert "".join(tokens).strip()
