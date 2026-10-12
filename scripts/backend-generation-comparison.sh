#!/usr/bin/env bash
# Comparison run: answers the golden question set on both splits with every Candidate Arm
# (never a Reference Arm), judges the answers, and reports each Arm's won/lost against the
# Shipped Arm by ADR-0006's test (eval/compare_arms.py, ADR-0009).
# Called by `make generation-comparison` and .github/workflows/generation-comparison.yml.
#
# Needs OPENAI_CI_API_KEY and JEV_API_KEY: CI's own keys, never production's. A run costs
# about four generation gate runs, which is why it runs only on demand.
#
# Set PUBLISH_EVAL=1 to also publish the held-out results as the Comparison section of
# frontend/data/generationResults.json. CI does this only for a run dispatched on main.
set -euo pipefail
cd "$(dirname "$0")/../backend"

# Config import requires these. The run never uses production's OPENAI_API_KEY: it
# generates with OPENAI_CI_API_KEY.
export OPENAI_API_KEY="${OPENAI_API_KEY:-test_key}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000}"

# Set COMPARISON_RUN_OUTPUT to a path to keep every Arm's judged run on both splits, the
# `dev` results the Shipped Arm decision is made on among them; CI uploads it as an artifact.
ARGS=()
if [ "${PUBLISH_EVAL:-0}" = "1" ]; then
  ARGS+=(--publish)
fi
if [ -n "${COMPARISON_RUN_OUTPUT:-}" ]; then
  ARGS+=(--output "$COMPARISON_RUN_OUTPUT")
fi

echo "==> Comparison run (Candidate Arms, dev and holdout)"
# --frozen: measure the committed uv.lock and never rewrite it (see backend-eval.sh).
# The guarded expansion avoids bash 3.2's `set -u` trap on an empty array (see backend-eval.sh).
uv run --frozen python eval/compare_arms.py ${ARGS[@]+"${ARGS[@]}"}

echo "generation-comparison: OK"
