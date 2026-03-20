.PHONY: help install dev dev-frontend dev-backend build-index test lint clean stop

help:
	@echo "Available commands:"
	@echo "  make install       - Install frontend and backend dependencies"
	@echo "  make dev           - Run both frontend and backend locally"
	@echo "  make dev-frontend  - Run frontend only"
	@echo "  make dev-backend   - Run backend only"
	@echo "  make build-index   - Build FAISS + BM25 indexes from resume and project data"
	@echo "  make stop          - Stop running dev servers"
	@echo "  make test          - Run frontend and backend tests"
	@echo "  make lint          - Run frontend and backend linters"
	@echo "  make clean         - Remove caches and build artifacts"

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

test:
	@echo "Running backend tests..."
	cd backend && uv run pytest tests/ -v
	@echo "Running frontend tests..."
	cd frontend && npm run test -- --run

lint:
	@echo "Running backend linting..."
	cd backend && uv run ruff check .
	@echo "Running frontend linting..."
	cd frontend && npm run lint

clean:
	@echo "Cleaning up..."
	cd backend && rm -rf .pytest_cache .ruff_cache __pycache__ app/__pycache__
	cd frontend && rm -rf .next node_modules
