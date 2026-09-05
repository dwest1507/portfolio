"""LLM generation: prompt construction + Groq streaming."""

from collections.abc import AsyncIterator
from typing import Literal

from groq import AsyncGroq
from pydantic import BaseModel

from .config import GROQ_API_KEY, GROQ_MODEL


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


def build_messages(
    context: str,
    history: list[Message],
    message: str,
) -> list[dict]:
    """Construct the Groq message list from RAG context, history, and the new user message."""
    system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context.strip() or NO_CONTEXT}"
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})
    return messages


async def generate_stream(
    messages: list[dict],
    client: AsyncGroq | None = None,
) -> AsyncIterator[str]:
    """Stream plain text tokens from Groq for the given message list."""
    if client is None:
        client = AsyncGroq(api_key=GROQ_API_KEY)

    stream = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        max_tokens=1024,
        temperature=0.3,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token
