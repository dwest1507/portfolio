#!/usr/bin/env bash
# Dependency vulnerability audits: npm audit (frontend) + pip-audit (backend).
# Usage: security-audit.sh [frontend|backend|all]   (default: all)
# Called by `make security-audit` and .github/workflows/security.yml.
#
# Note: CodeQL, gitleaks, and dependency review also run in security.yml but are
# GitHub-hosted analyses that cannot run identically outside Actions.
set -euo pipefail
cd "$(dirname "$0")/.."

target="${1:-all}"

audit_frontend() {
  echo "==> npm audit (production deps, high severity and above)"
  (cd frontend && npm audit --omit=dev --audit-level=high)
}

audit_backend() {
  echo "==> pip-audit (locked production deps)"
  local reqs rc=0
  reqs=$(mktemp /tmp/portfolio-audit-XXXXXX.txt)
  (cd backend && uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements-txt) > "$reqs"
  # --no-deps: the uv export is already a complete locked set, so audit it
  # directly instead of letting pip-audit rebuild the environment.
  # Pin the interpreter to the project's Python so wheel resolution matches uv.lock.
  uvx --python "$(cat backend/.python-version)" pip-audit --requirement "$reqs" --no-deps || rc=$?
  rm -f "$reqs"
  return "$rc"
}

case "$target" in
  frontend) audit_frontend ;;
  backend) audit_backend ;;
  all)
    audit_frontend
    audit_backend
    ;;
  *)
    echo "usage: $0 [frontend|backend|all]" >&2
    exit 2
    ;;
esac

echo "security-audit ($target): OK"
