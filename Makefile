# `dev` and `stop` use bash builtins (wait -n, trap).
SHELL := /bin/bash

.PHONY: help install dev dev-frontend dev-backend build-index test lint clean stop \
	frontend-quality frontend-test frontend-build backend-lint backend-test frontend-deps \
	security-audit lighthouse ci-cd eval eval-fast

help:
	@echo "Available commands:"
	@echo "  make install                 - Install frontend and backend dependencies"
	@echo "  make dev                     - Run both frontend and backend locally"
	@echo "  make dev-frontend            - Run frontend only"
	@echo "  make dev-backend             - Run backend only"
	@echo "  make build-index             - Build FAISS + BM25 indexes from resume and project data"
	@echo "  make stop                    - Stop running dev servers"
	@echo "  make test                    - Run frontend and backend tests"
	@echo "  make lint                    - Run frontend and backend linters"
	@echo "  make clean                   - Remove caches and build artifacts"
	@echo ""
	@echo "CI checks (same scripts GitHub Actions runs — see scripts/):"
	@echo "  make ci-cd                   - Run ALL CI checks locally"
	@echo "  make frontend-quality        - ESLint + Prettier check + TypeScript check"
	@echo "  make frontend-test           - Vitest (single run)"
	@echo "  make frontend-build          - Next.js production build"
	@echo "  make backend-lint            - Ruff check + format check"
	@echo "  make backend-test            - Pytest"
	@echo "  make eval                    - Retrieval quality eval (all arms; downloads models)"
	@echo "  make eval-fast               - Retrieval eval, BM25 arm only (no model download)"
	@echo "  make security-audit          - npm audit + pip-audit"
	@echo "  make lighthouse              - Lighthouse CI budget check (needs Chrome)"
	@echo ""
	@echo "Deploys are handled by the Vercel and Railway git integrations"
	@echo "(push to main) — see docs/deployment.md."

install:
	@echo "Installing backend dependencies..."
	cd backend && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Reinstall frontend deps when node_modules is missing (e.g. after `make clean`)
# or when package-lock.json has actually changed. The stamp records the lockfile's
# hash rather than its mtime, so `git checkout`/`git pull` touching the file does
# not trigger a needless full reinstall.
frontend-deps:
	@cd frontend && \
	  stamp=node_modules/.deps-stamp; \
	  want=$$(sha256sum package-lock.json | cut -d' ' -f1); \
	  if [ ! -d node_modules ] || [ ! -f "$$stamp" ] || [ "$$(cat "$$stamp")" != "$$want" ]; then \
	    echo "Frontend dependencies missing or stale; running npm ci..."; \
	    npm ci && printf '%s' "$$want" > "$$stamp"; \
	  fi

dev-frontend: frontend-deps
	cd frontend && npm run dev

# The backend needs no equivalent rule: `uv run` syncs .venv from uv.lock itself,
# and `clean` does not delete .venv.
dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Both servers share a fate: if either exits, take the other down too. A
# frontend left running against a dead backend just serves chat errors with no
# hint that the backend is the part that died.
dev: frontend-deps
	@echo "Starting full stack... (Press Ctrl+C to stop)"
	@set -m; \
	( cd backend && exec uv run uvicorn app.main:app --reload --port 8000 ) & back=$$!; \
	( cd frontend && exec npm run dev ) & front=$$!; \
	trap 'kill $$back $$front 2>/dev/null' EXIT INT TERM; \
	wait -n $$back $$front; \
	echo ""; \
	echo "A dev server exited — stopping the other half of the stack."; \
	kill $$back $$front 2>/dev/null || true; \
	wait $$back $$front 2>/dev/null || true

build-index:
	@echo "Building FAISS + BM25 indexes..."
	cd backend && uv run python scripts/build_index.py

# Only ever targets processes *listening* on the port. A bare `lsof -ti:3000`
# also matches clients connected to it — it will happily kill your browser.
stop:
	@echo "Stopping running servers on ports 3000 and 8000..."
	@for port in 3000 8000; do \
		pids=$$( { ss -lptnH "sport = :$$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2; \
		           lsof -ti tcp:$$port -sTCP:LISTEN 2>/dev/null; } | sort -u | tr '\n' ' ' ); \
		if [ -z "$$pids" ]; then \
			echo "  port $$port: nothing listening"; \
		else \
			echo "  port $$port: stopping $$pids"; \
			kill $$pids 2>/dev/null || true; \
			sleep 1; \
			kill -9 $$pids 2>/dev/null || true; \
		fi; \
	done

# ---------------------------------------------------------------------------
# CI checks — thin wrappers over scripts/, which are the single source of
# truth shared with .github/workflows/. Behavior is identical locally and in CI.
# ---------------------------------------------------------------------------

frontend-quality:
	./scripts/frontend-quality.sh

frontend-test:
	./scripts/frontend-test.sh

frontend-build:
	./scripts/frontend-build.sh

backend-lint:
	./scripts/backend-lint.sh

backend-test:
	./scripts/backend-test.sh

eval:
	./scripts/backend-eval.sh

eval-fast:
	./scripts/backend-eval.sh bm25

security-audit:
	./scripts/security-audit.sh all

lighthouse:
	./scripts/lighthouse.sh

# Everything the PR/push gates run, in one command. There is nothing to deploy
# here — Vercel and Railway deploy from main via their git integrations.
ci-cd: frontend-quality frontend-test frontend-build backend-lint backend-test eval security-audit lighthouse
	@echo ""
	@echo "ci-cd: all checks passed ✔"

# Convenience aliases kept for muscle memory
test: backend-test frontend-test

lint: frontend-quality backend-lint

clean:
	@echo "Cleaning up..."
	cd backend && rm -rf .pytest_cache .ruff_cache __pycache__ app/__pycache__
	cd frontend && rm -rf .next node_modules
