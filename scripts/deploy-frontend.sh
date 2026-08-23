#!/usr/bin/env bash
# Deploy the frontend to Vercel.
# Usage: deploy-frontend.sh [production|preview]   (default: preview)
# Called by `make deploy-frontend` / `make deploy-frontend-preview` and
# .github/workflows/deploy.yml / deploy-preview.yml.
#
# NOT part of `make ci-cd` — production deploys are meant to run from GitHub
# Actions on main. Running locally requires the same env vars the workflows use:
#   VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID
set -euo pipefail
cd "$(dirname "$0")/../frontend"

mode="${1:-preview}"
case "$mode" in production | preview) ;; *)
  echo "usage: $0 [production|preview]" >&2
  exit 2
  ;;
esac

for var in VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID; do
  if [ -z "${!var:-}" ]; then
    echo "error: $var is not set (see docs/ci-cd.md)" >&2
    exit 1
  fi
done

if ! command -v vercel > /dev/null; then
  echo "==> Installing Vercel CLI"
  npm install --global vercel@latest
fi

prod_flag=""
[ "$mode" = "production" ] && prod_flag="--prod"

echo "==> vercel pull ($mode)"
vercel pull --yes --environment="$mode" --token="$VERCEL_TOKEN"

echo "==> vercel build"
vercel build $prod_flag --token="$VERCEL_TOKEN"

echo "==> vercel deploy"
url=$(vercel deploy --prebuilt $prod_flag --token="$VERCEL_TOKEN")
echo "Deployed to $url"

# Expose the URL to GitHub Actions when running there
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "url=$url" >> "$GITHUB_OUTPUT"
fi
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "Deployed ($mode): $url" >> "$GITHUB_STEP_SUMMARY"
fi

# Smoke test production only (preview URLs may sit behind Vercel deployment protection)
if [ "$mode" = "production" ]; then
  echo "==> Smoke test"
  for i in $(seq 1 10); do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
    if [ "$status" = "200" ]; then
      echo "Frontend healthy (HTTP $status)"
      echo "deploy-frontend: OK"
      exit 0
    fi
    echo "Attempt $i: HTTP $status — retrying in 10s"
    sleep 10
  done
  echo "error: frontend never became healthy" >&2
  exit 1
fi

echo "deploy-frontend: OK"
