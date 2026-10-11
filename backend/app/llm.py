"""LLM generation: prompt construction + OpenAI streaming."""

from collections.abc import AsyncIterator
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import OPENAI_API_KEY, OPENAI_MODEL


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


SYSTEM_PROMPT = (
    "You are David West's AI assistant on his portfolio website. "
    "Answer questions about David's experience, skills, and projects using "
    "ONLY the provided context. If the context doesn't contain the answer, "
    "say so honestly. Be concise and professional. Do not make up information. "
    "Earlier turns of the conversation are history, not context: never answer from "
    "them when the context below is empty."
)

#: Stands in for the context section when retrieval returned nothing.
#:
#: Since retrieval became BM25-only, a question sharing no term with any chunk retrieves
#: zero chunks rather than five weak ones (see RAGPipeline.retrieve). That is deliberate,
#: but an empty string leaves a bare "Context:" heading — the model is told to use only
#: the context and then shown nothing at all, with up to ten prior turns still in the
#: window as the one remaining source of material. Saying so explicitly is what makes
#: "say so honestly" actionable rather than merely unopposed.
NO_CONTEXT = "(No relevant context was retrieved for this question.)"

#: Generation settings shared by production and the generation eval, so the eval measures
#: what visitors are served (ADR-0007). OpenAI's reasoning models reject any temperature
#: but the default, so none is sent; the reasoning effort is pinned instead, at the value
#: the model was selected and the Floors measured with (ADR-0007 amendment, ADR-0008).
#: MAX_TOKENS caps reasoning and answer tokens together (`max_completion_tokens`).
REASONING_EFFORT = "low"
MAX_TOKENS = 1024

#: The temperature the Groq baseline was captured at, before the switch to OpenAI. Only
#: the eval's Groq generator (eval/generation.py) still uses it.
TEMPERATURE = 0


def format_context(chunks: list[str]) -> str:
    """Join retrieved chunk texts into the context section of the system prompt."""
    return "\n\n---\n\n".join(chunks)


def build_messages(
    context: str,
    history: list[Message],
    message: str,
) -> list[dict]:
    """Construct the chat message list from RAG context, history, and the new user message."""
    system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context.strip() or NO_CONTEXT}"
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})
    return messages


async def generate_stream(
    messages: list[dict],
    client: AsyncOpenAI | None = None,
) -> AsyncIterator[str]:
    """Stream plain text tokens from OpenAI for the given message list."""
    if client is None:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        stream=True,
        reasoning_effort=REASONING_EFFORT,
        max_completion_tokens=MAX_TOKENS,
    )
    async for chunk in stream:
        # A usage-only chunk has no choices; the first and last deltas carry no text.
        if not chunk.choices:
            continue
        token = chunk.choices[0].delta.content
        if token:
            yield token
