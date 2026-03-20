"""POST /api/chat — RAG pipeline + Groq streaming."""
import json
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from groq import AsyncGroq
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import GROQ_API_KEY
from ..rag.pipeline import get_pipeline

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

SYSTEM_PROMPT = (
    "You are David West's AI assistant on his portfolio website. "
    "Answer questions about David's experience, skills, and projects using "
    "ONLY the provided context. If the context doesn't contain the answer, "
    "say so honestly. Be concise and professional. Do not make up information."
)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list)


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    pipeline = get_pipeline()

    # Retrieve context
    context_chunks = pipeline.retrieve(body.message)
    context = "\n\n---\n\n".join(context_chunks)

    # Build message list for Groq
    system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context}"
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for msg in body.history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    client = AsyncGroq(api_key=GROQ_API_KEY)

    async def generate():
        try:
            stream = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                stream=True,
                max_tokens=1024,
                temperature=0.3,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    # Vercel AI SDK data stream format (v1): 0:"token"\n
                    yield f"0:{json.dumps(token)}\n"
            yield f'd:{json.dumps({"finishReason": "stop"})}\n'
        except Exception:
            # Can't change HTTP status after streaming starts; signal via stream
            # AI SDK data stream v1 error type: 3:"message"\n
            yield '3:"Generation failed"\n'

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
