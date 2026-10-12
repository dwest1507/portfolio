#!/usr/bin/env bash
# Generation quality gate: answers the golden question set with the Shipped Arm and the
# OpenAI model the Floors were measured on, judges the answers, and fails if Faithfulness
# or Decline accuracy drops below its Floor (eval/generation.py, ADR-0007).
# Called by `make generation-gate` and .github/workflows/generation-gate.yml.
#
# Needs OPENAI_CI_API_KEY and JEV_API_KEY: CI's own keys, never production's. Each run
# costs a few cents, which is why the workflow runs only on generation-relevant changes.
#
# Set PUBLISH_EVAL=1 to also publish the held-out results as the Shipped Arm section of
# frontend/data/generationResults.json. CI does this only on pushes to main.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Config import requires these. The gate never uses production's OPENAI_API_KEY: it
# generates with OPENAI_CI_API_KEY.
export OPENAI_API_KEY="${OPENAI_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

# Set GENERATION_RUN_OUTPUT to a path to keep the judged run (every answer, judgment and
# Contradiction) as JSON; CI uploads it as an artifact.
ARGS=()
if [ "${PUBLISH_EVAL:-0}" = "1" ]; then
  ARGS+=(--publish)
fi
if [ -n "${GENERATION_RUN_OUTPUT:-}" ]; then
  ARGS+=(--output "$GENERATION_RUN_OUTPUT")
fi

echo "==> Generation gate (full golden set)"
# --frozen: measure the committed uv.lock and never rewrite it (see backend-eval.sh).
# The guarded expansion avoids bash 3.2's `set -u` trap on an empty array (see backend-eval.sh).
uv run --frozen python eval/gate_generation.py ${ARGS[@]+"${ARGS[@]}"}

echo "generation-gate: OK"
