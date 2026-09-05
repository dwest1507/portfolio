# David West — Portfolio

Personal portfolio website for David West, an AI Engineer with 5+ years of data science and AI experience. Features a dark, Linear-inspired design system and an AI-powered chatbot recruiters can use to ask questions about qualifications.

**Stack:** Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · Python FastAPI · Groq

**Deployed at:** Vercel (frontend) · Railway (backend)

---

## Quick Start

**Prerequisites:** Node.js 20+, Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
# Install all dependencies
make install

# Run frontend + backend together
make dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### First-time setup

The RAG chatbot requires pre-built search indexes. Run this once before starting the backend:

```bash
make build-index
```

Create `backend/.env` with your credentials:

```
GROQ_API_KEY=your_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

---

## Project Structure

```
portfolio/
├── frontend/          Next.js 16 app (pages, components, styles)
├── backend/           Python FastAPI (RAG pipeline, chat endpoint)
├── scripts/           CI check scripts (shared by make and GitHub Actions)
├── docs/              Detailed documentation
│   └── resume.txt     Resume source used for RAG indexing
└── Makefile           Dev automation commands
```

See [docs/architecture.md](docs/architecture.md) for the full system design and
[docs/evaluation.md](docs/evaluation.md) for how retrieval quality is measured.

---

## Key Features

- **5 project showcases** with filterable cards and MDX detail pages — including a write-up of this site's own retrieval pipeline and eval results
- **AI chatbot** — floating widget with streaming responses, powered by a RAG pipeline (BM25 retrieval, chosen over hybrid search and cross-encoder re-ranking by [measurement](docs/evaluation.md)) and Groq LLM
- **Measured retrieval** — a 55-question golden set scores the pipeline on hit@5, recall@5, MRR, and nDCG@5, gated in CI so retrieval quality cannot regress silently ([docs/evaluation.md](docs/evaluation.md))
- **Dark design system** — near-black surfaces, a single sky-blue accent (`#0ea5e9`), Inter for text with monospace micro-labels

---

## Development

```bash
make dev-frontend    # Next.js on :3000
make dev-backend     # FastAPI on :8000
make test            # Run all tests (pytest + vitest)
make eval            # Retrieval quality eval (all arms; downloads models)
make eval-fast       # Retrieval eval, BM25 arm only (no model download)
make lint            # Ruff + ESLint + Prettier + tsc
make ci-cd           # Run every CI check locally — same scripts CI runs
make build-index     # Rebuild RAG search indexes
make stop            # Kill dev servers
```

The CI pipeline's logic lives in `scripts/` and is shared verbatim between `make`
targets and GitHub Actions, so `make ci-cd` reproduces the PR gates locally.
See [docs/ci-cd.md](docs/ci-cd.md) for the full target ↔ workflow mapping.

---

## Versioning

This project uses [Release Please](https://github.com/googleapis/release-please) for
automated versioning and changelog generation.

1. **Develop:** merge changes into `main` using
   [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, …).
2. **Release PR:** Release Please opens a PR that bumps the version and updates
   `CHANGELOG.md`.
3. **Merge:** merging that PR creates the git tag and GitHub Release.

Frontend (`frontend/package.json`) and backend (`backend/pyproject.toml`) share one
synchronized version, tracked in `.release-please-manifest.json`.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, tech decisions |
| [docs/chatbot-rag.md](docs/chatbot-rag.md) | RAG pipeline details (chunking, embedding, search, re-ranking) |
| [docs/design-system.md](docs/design-system.md) | Cyberpunk design tokens, typography, animations |
| [docs/deployment.md](docs/deployment.md) | Deploying to Vercel + Railway (native git integrations), environment variables |
| [docs/ci-cd.md](docs/ci-cd.md) | GitHub Actions pipeline — CI, security scans, Lighthouse, releases |
| [docs/testing.md](docs/testing.md) | Test coverage approach, running tests |
| [SPEC.md](SPEC.md) | Full project specification |
