#!/usr/bin/env bash
# Frontend unit tests (Vitest, single run).
# Called by `make frontend-test` and .github/workflows/frontend-ci.yml.
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  echo "error: frontend/node_modules missing — run 'make install' first" >&2
  exit 1
fi

echo "==> Vitest"
npm run test -- --run

echo "frontend-test: OK"
