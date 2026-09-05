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
# see docs/adr/0001-generated-eval-results.md. The published run measures the held-out
# split and always runs every arm, whatever this script was called with.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Config import requires these; the eval never calls Groq.
export GROQ_API_KEY="${GROQ_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

# The full arm list is NOT repeated here. Arms are added and retired in
# eval/publish.py (ARM_SPECS), and a copy of the list in this script would go stale
# the first time one changed — publishing a table missing a row, or failing on an arm
# that no longer exists. With no arguments, run_eval.py runs every arm it knows about.
#
# Note: branch on "$#", not on "${#ARM_ARGS[@]}" for an array assigned from an empty
# "$@". Under `set -u`, bash 3.2 (still the default /bin/bash on macOS) treats an empty
# array as unset and aborts on the expansion, so a no-argument `make eval` died before
# running anything.
if [ "$#" -eq 0 ]; then
  ARM_ARGS=()
  DESCRIBED="all"
else
  ARM_ARGS=(--arms "$@")
  DESCRIBED="$*"
fi

# The gate runs over the whole golden set, where the floors are calibrated.
echo "==> Retrieval eval (arms: ${DESCRIBED}; gating the full golden set)"
uv run python eval/run_eval.py ${ARM_ARGS[@]+"${ARM_ARGS[@]}"} --check --failures

# Publishing is a SECOND invocation, and not only because an empty array expanded under
# `set -u` is the bash 3.2 trap documented above. It measures a different sample: the
# held-out split, which nothing is ever tuned against, so the number on the public page
# is not the number a configuration was chosen by. --publish refuses any other split,
# and refuses a partial run, so nothing here needs to accumulate flags.
if [ "${PUBLISH_EVAL:-0}" = "1" ]; then
  echo "==> Retrieval eval (held-out split; publishing results)"
  uv run python eval/run_eval.py --split holdout --publish
fi

echo "backend-eval: OK"
