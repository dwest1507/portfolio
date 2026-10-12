#!/usr/bin/env bash
# Backend tests (pytest; ML models and OpenAI are mocked by the suite).
# Called by `make backend-test` and .github/workflows/backend-ci.yml.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Same dummy values the CI job uses; tests never call real services
export OPENAI_API_KEY="${OPENAI_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

echo "==> Pytest"
uv run --frozen pytest tests/ -v

echo "backend-test: OK"
