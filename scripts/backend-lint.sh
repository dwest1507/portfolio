#!/usr/bin/env bash
# Backend lint gate: lockfile check + Ruff check + format check.
# Called by `make backend-lint` and .github/workflows/backend-ci.yml.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Fail on a uv.lock that no longer matches pyproject.toml (e.g. a version bump that
# skipped the lockfile), here on the PR that caused it. The other scripts run uv
# --frozen, so nothing downstream would re-lock and notice.
echo "==> uv lockfile check"
uv lock --check

echo "==> Ruff check"
uv run --frozen ruff check .

echo "==> Ruff format check"
uv run --frozen ruff format --check .

echo "backend-lint: OK"
