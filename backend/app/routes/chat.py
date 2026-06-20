"""POST /api/chat — RAG retrieval + LLM generation + SSE streaming."""
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..llm import Message, build_messages, generate_stream
from ..rag.pipeline import get_pipeline

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list)


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    pipeline = get_pipeline()
    context_chunks = pipeline.retrieve(body.message)
    context = "\n\n---\n\n".join(context_chunks)

    messages = build_messages(context, body.history, body.message)

    async def generate():
        try:
            async for token in generate_stream(messages):
                yield f"0:{json.dumps(token)}\n"
            yield f'd:{json.dumps({"finishReason": "stop"})}\n'
        except Exception:
            yield '3:"Generation failed"\n'

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
