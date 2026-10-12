"""POST /api/chat — RAG retrieval + LLM generation + SSE streaming."""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import DAILY_REQUEST_CAP
from ..daily_cap import RESTING_MESSAGE, DailyCap
from ..llm import Message, build_messages, format_context, generate_stream
from ..rag.pipeline import get_pipeline
from ..visitor_log import log_visitor_query

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

#: Shared by every visitor, alongside the per-IP limit (ADR-0008).
daily_cap = DailyCap(DAILY_REQUEST_CAP)

FINISH = f"d:{json.dumps({'finishReason': 'stop'})}\n"
STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list)


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    if not daily_cap.admit():
        # Same stream format as an answer, so the frontend shows it as an ordinary reply.
        return _stream([f"0:{json.dumps(RESTING_MESSAGE)}\n", FINISH])

    pipeline = get_pipeline()
    context_chunks = pipeline.retrieve(body.message)
    # Before generation, so a question still counts when the model call fails (ADR-0010).
    log_visitor_query(body.message, len(context_chunks))
    context = format_context(context_chunks)

    messages = build_messages(context, body.history, body.message)

    async def generate():
        try:
            async for token in generate_stream(messages):
                yield f"0:{json.dumps(token)}\n"
            yield FINISH
        except Exception:
            # Log the real cause server-side; never leak provider errors to the client.
            logger.exception("LLM generation failed")
            yield '3:"Generation failed"\n'

    return _stream(generate())


def _stream(lines) -> StreamingResponse:
    """A Vercel AI SDK data stream (v1) response, the format the frontend reads."""
    return StreamingResponse(lines, media_type="text/plain; charset=utf-8", headers=STREAM_HEADERS)
