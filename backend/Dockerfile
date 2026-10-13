# Production image for the FastAPI RAG backend (Railway).
#
# There are no model weights in this image, and that is the interesting part. The
# evaluation harness measured semantic search, hybrid fusion and cross-encoder
# re-ranking against plain BM25 on this corpus, and plain BM25 won — so the served
# pipeline is keyword retrieval over a pickled index. See docs/evaluation.md.
#
# What that removes: ~500MB of embedding and re-ranking weights that used to be baked in
# here, the ML runtime wheels, the Hugging Face cache directory, and the model-loading step
# from container start.

FROM python:3.14-slim

# uv for fast, reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for layer caching. --no-dev is what keeps onnxruntime,
# tokenizers and huggingface-hub out: they are declared in the dev group because only the
# index builder and the eval harness use them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

# Application code + pre-built indexes. onnx_embeddings.npy ships too — it is a few hundred
# KB, and shipping the whole directory keeps the image a faithful copy of what was measured.
COPY app ./app
COPY indexes ./indexes

# Run as an unprivileged user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# --no-access-log: uvicorn's access log would print a "POST /api/chat" line with the
# client's address right after each visitor_query line, linking a logged question to an
# IP. ADR-0010 promises the visitor query log carries none, so production keeps no access
# log at all. Errors and startup messages still go to the service logs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
