"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .config import ALLOWED_ORIGINS
from .rag.pipeline import get_pipeline
from .routes.chat import router as chat_router
from .routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load models at startup so the first request isn't slow
    get_pipeline()
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Portfolio Chatbot API", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(health_router, prefix="/api")
