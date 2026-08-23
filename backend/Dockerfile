# Production image for the FastAPI RAG backend (Railway).
# Models are baked into the image so container startup never hits Hugging Face.

FROM python:3.14-slim

# uv for fast, reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.hf-cache

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

# Pre-download embedding + re-ranking models into the image
RUN python -c "\
from sentence_transformers import CrossEncoder, SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-mpnet-base-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Application code + pre-built FAISS/BM25 indexes
COPY app ./app
COPY indexes ./indexes

# Run as an unprivileged user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
