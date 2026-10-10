"""Tests for app.llm — model wiring and a live provider smoke check."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import dotenv_values
from groq import AsyncGroq

from app.llm import MAX_TOKENS, NO_CONTEXT, SYSTEM_PROMPT, build_messages, generate_stream
from eval.generation import groq_generator, openai_generator


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


# ---------------------------------------------------------------------------
# Empty retrieval
# ---------------------------------------------------------------------------


def test_an_empty_context_is_stated_rather_than_left_blank():
    """BM25-only retrieval can return nothing; the prompt has to say so.

    `RAGPipeline.retrieve` returns no chunks when the question shares no term with the
    corpus, which is deliberate. What is not safe is rendering that as a bare "Context:"
    heading: the model is instructed to answer from the context alone and then handed an
    empty section, with the conversation history still in the window as the only material
    left to draw on. Naming the emptiness is what turns "say so honestly" into an
    instruction the model can follow.
    """
    system = build_messages("", [], "What is the capital of France?")[0]["content"]

    assert NO_CONTEXT in system
    assert not system.rstrip().endswith("Context:")


def test_history_is_marked_as_history_not_context():
    """The instruction that makes an empty context safe when prior turns are present."""
    assert "history, not context" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Groq generator for the generation eval
# ---------------------------------------------------------------------------


def _fake_completions_client(text: str = "An answer.", model: str = "openai/gpt-oss-120b"):
    """A synchronous Groq or OpenAI client whose completion records its request."""
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=1200, completion_tokens=300, total_tokens=1500, queue_time=0.01
        ),
        model=model,
    )
    return client


def test_the_eval_prompt_is_the_production_prompt(client, mock_pipeline):
    """The Groq generator sends exactly what the chat endpoint sends for the same input.

    An eval prompt that drifted from production's would measure answers no visitor gets,
    so the generator has no prompt of its own: both go through the production builder.
    """
    question = "What is David's background?"
    chunks = mock_pipeline.retrieve.return_value

    served = {}

    async def _fake_create(**kwargs):
        served.update(kwargs)

        async def _empty():
            return
            yield

        return _empty()

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=_fake_create)
    with patch("app.llm.AsyncGroq", return_value=mock_groq):
        client.post("/api/chat", json={"message": question})

    groq = _fake_completions_client()
    groq_generator(groq, model=served["model"])(question, chunks)
    evaluated = groq.chat.completions.create.call_args.kwargs

    for setting in ("model", "messages", "temperature", "max_tokens"):
        assert evaluated[setting] == served[setting], setting


def test_the_groq_generator_reports_billed_usage_and_the_answering_model():
    """The model is the one Groq says answered, not the one requested."""
    groq = _fake_completions_client(
        text="David is an AI Engineer.", model="openai/gpt-oss-120b-0901"
    )

    generation = groq_generator(groq, model="openai/gpt-oss-120b")("Who is David?", ["ctx"])

    assert generation.text == "David is an AI Engineer."
    assert generation.usage == {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
    }
    assert generation.model == "openai/gpt-oss-120b-0901"


def test_the_openai_generator_reports_billed_usage_and_the_answering_model():
    """Billed usage includes reasoning tokens, which OpenAI counts as completion tokens."""
    openai = _fake_completions_client(
        text="David is an AI Engineer.", model="gpt-6-luna-2026-08-01"
    )

    generation = openai_generator(openai, model="gpt-6-luna", reasoning_effort="low")(
        "Who is David?", ["ctx"]
    )

    assert generation.text == "David is an AI Engineer."
    assert generation.usage == {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
    }
    assert generation.model == "gpt-6-luna-2026-08-01"


def test_the_openai_generator_sends_the_production_prompt_and_no_temperature():
    """OpenAI's reasoning models only accept the default temperature, so none is sent.

    The reasoning effort is sent instead: it is part of what is being measured.
    """
    openai = _fake_completions_client()

    openai_generator(openai, model="gpt-6-luna", reasoning_effort="low")("Who is David?", ["ctx"])
    request = openai.chat.completions.create.call_args.kwargs

    assert request == {
        "model": "gpt-6-luna",
        "messages": build_messages("ctx", [], "Who is David?"),
        "reasoning_effort": "low",
        "max_completion_tokens": MAX_TOKENS,
    }
