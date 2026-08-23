#!/usr/bin/env bash
# Deploy the backend to Railway, then wait for /api/health.
# Called by `make deploy-backend` and .github/workflows/deploy.yml.
#
# NOT part of `make ci-cd` — production deploys are meant to run from GitHub
# Actions on main. Running locally requires the same env vars the workflow uses:
#   RAILWAY_TOKEN, RAILWAY_SERVICE, and optionally BACKEND_URL for the health check.
set -euo pipefail
cd "$(dirname "$0")/../backend"

for var in RAILWAY_TOKEN RAILWAY_SERVICE; do
  if [ -z "${!var:-}" ]; then
    echo "error: $var is not set (see docs/ci-cd.md)" >&2
    exit 1
  fi
done

if ! command -v railway > /dev/null; then
  echo "==> Installing Railway CLI"
  npm install --global @railway/cli
fi

echo "==> railway up (service: $RAILWAY_SERVICE)"
railway up --service "$RAILWAY_SERVICE" --ci

if [ -n "${BACKEND_URL:-}" ]; then
  echo "==> Health check ($BACKEND_URL/api/health)"
  # Allow time for model loading on startup
  for i in $(seq 1 30); do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/health" || true)
    if [ "$status" = "200" ]; then
      echo "Backend healthy (HTTP $status)"
      echo "deploy-backend: OK"
      exit 0
    fi
    echo "Attempt $i: HTTP $status — retrying in 10s"
    sleep 10
  done
  echo "error: backend never became healthy" >&2
  exit 1
fi

echo "deploy-backend: OK (no BACKEND_URL set — health check skipped)"
