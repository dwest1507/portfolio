#!/usr/bin/env bash
# Retrieval quality gate: runs the golden question set through the RAG pipeline
# and fails if recall/MRR drop below the thresholds in eval/run_eval.py.
# Called by `make eval` and .github/workflows/backend-ci.yml.
#
# Pass arm names to restrict the run, e.g.:
#   ./scripts/backend-eval.sh bm25        # keyword only; no model download
#   ./scripts/backend-eval.sh             # all arms (needs the ST models)
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Config import requires these; the eval never calls Groq.
export GROQ_API_KEY="${GROQ_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

ARMS=("$@")
if [ ${#ARMS[@]} -eq 0 ]; then
  ARMS=(bm25 dense hybrid rerank)
fi

echo "==> Retrieval eval (arms: ${ARMS[*]})"
uv run python eval/run_eval.py --arms "${ARMS[@]}" --check --failures

echo "backend-eval: OK"
