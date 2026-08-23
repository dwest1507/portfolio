#!/usr/bin/env bash
# Backend lint gate: Ruff check + format check.
# Called by `make backend-lint` and .github/workflows/backend-ci.yml.
set -euo pipefail
cd "$(dirname "$0")/../backend"

echo "==> Ruff check"
uv run ruff check .

echo "==> Ruff format check"
uv run ruff format --check .

echo "backend-lint: OK"
