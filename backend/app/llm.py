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
    "say so honestly. Be concise and professional. Do not make up information."
)


def build_messages(
    context: str,
    history: list[Message],
    message: str,
) -> list[dict]:
    """Construct the Groq message list from RAG context, history, and the new user message."""
    system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context}"
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
