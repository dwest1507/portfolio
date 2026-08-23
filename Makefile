.PHONY: help install dev dev-frontend dev-backend build-index test lint clean stop \
	frontend-quality frontend-test frontend-build backend-lint backend-test \
	security-audit lighthouse ci-cd deploy-frontend deploy-frontend-preview deploy-backend

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
	@echo "  make ci-cd                   - Run ALL CI checks locally (no deploys)"
	@echo "  make frontend-quality        - ESLint + Prettier check + TypeScript check"
	@echo "  make frontend-test           - Vitest (single run)"
	@echo "  make frontend-build          - Next.js production build"
	@echo "  make backend-lint            - Ruff check + format check"
	@echo "  make backend-test            - Pytest"
	@echo "  make security-audit          - npm audit + pip-audit"
	@echo "  make lighthouse              - Lighthouse CI budget check (needs Chrome)"
	@echo ""
	@echo "Deploys (run by GitHub Actions on main; local runs need the same env vars):"
	@echo "  make deploy-frontend         - Deploy frontend to Vercel (production)"
	@echo "  make deploy-frontend-preview - Deploy frontend to Vercel (preview)"
	@echo "  make deploy-backend          - Deploy backend to Railway"

install:
	@echo "Installing backend dependencies..."
	cd backend && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev:
	@echo "Starting full stack... (Press Ctrl+C to stop)"
	@$(MAKE) -j2 dev-frontend dev-backend

build-index:
	@echo "Building FAISS + BM25 indexes..."
	cd backend && uv run python scripts/build_index.py

stop:
	@echo "Stopping running servers on ports 3000 and 8000..."
	-@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	-@lsof -ti:8000 | xargs kill -9 2>/dev/null || true

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

security-audit:
	./scripts/security-audit.sh all

lighthouse:
	./scripts/lighthouse.sh

# Everything the PR/push gates run, in one command. Deploys are intentionally
# excluded — those only run from GitHub Actions on main.
ci-cd: frontend-quality frontend-test frontend-build backend-lint backend-test security-audit lighthouse
	@echo ""
	@echo "ci-cd: all checks passed ✔"

# Convenience aliases kept for muscle memory
test: backend-test frontend-test

lint: frontend-quality backend-lint

# ---------------------------------------------------------------------------
# Deploys — NOT part of ci-cd. GitHub Actions runs these on push to main;
# the make targets exist so the logic can be exercised locally.
# ---------------------------------------------------------------------------

deploy-frontend:
	./scripts/deploy-frontend.sh production

deploy-frontend-preview:
	./scripts/deploy-frontend.sh preview

deploy-backend:
	./scripts/deploy-backend.sh

clean:
	@echo "Cleaning up..."
	cd backend && rm -rf .pytest_cache .ruff_cache __pycache__ app/__pycache__
	cd frontend && rm -rf .next node_modules
