#!/usr/bin/env bash
# Retrieval quality gate: runs the golden question set through the RAG pipeline
# and fails if recall/MRR drop below the thresholds in eval/run_eval.py.
# Called by `make eval` and .github/workflows/backend-ci.yml.
#
# Pass arm names to restrict the run, e.g.:
#   ./scripts/backend-eval.sh bm25        # keyword only; no model download
#   ./scripts/backend-eval.sh             # all arms (needs the ST models)
#
# Set PUBLISH_EVAL=1 to also write the measured run to frontend/data/evalResults.json and
# refresh the generated table in docs/evaluation.md. CI does this only on pushes to main;
# see docs/adr/0001-generated-eval-results.md.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Config import requires these; the eval never calls Groq.
export GROQ_API_KEY="${GROQ_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

# Note: build the array from "$#", not from "${#ARMS[@]}" on an array assigned
# from an empty "$@". Under `set -u`, bash 3.2 (still the default /bin/bash on
# macOS) treats an empty array as unset and aborts on the expansion, so a
# no-argument `make eval` died before running anything.
if [ "$#" -eq 0 ]; then
  ARMS=(bm25 dense hybrid rerank)
else
  ARMS=("$@")
fi

# Publishing is a separate invocation rather than an appended array element: an empty
# array expanded under `set -u` is the bash 3.2 trap documented above, and --publish
# refuses a partial run anyway, so there is nothing to accumulate.
if [ "${PUBLISH_EVAL:-0}" = "1" ]; then
  echo "==> Retrieval eval (arms: ${ARMS[*]}; publishing results)"
  uv run python eval/run_eval.py --arms "${ARMS[@]}" --check --failures --publish
else
  echo "==> Retrieval eval (arms: ${ARMS[*]})"
  uv run python eval/run_eval.py --arms "${ARMS[@]}" --check --failures
fi

echo "backend-eval: OK"
