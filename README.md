# David West — Portfolio

Personal portfolio website for David West, an AI Engineer with 5+ years of data science and AI experience. Features a cyberpunk design system and an AI-powered chatbot recruiters can use to ask questions about qualifications.

**Stack:** Next.js 15 · React 19 · TypeScript · Tailwind CSS v4 · Python FastAPI · Groq

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
├── frontend/          Next.js 15 app (pages, components, styles)
├── backend/           Python FastAPI (RAG pipeline, chat endpoint)
├── docs/              Detailed documentation
│   └── resume.txt     Resume source used for RAG indexing
└── Makefile           Dev automation commands
```

See [docs/architecture.md](docs/architecture.md) for the full system design.

---

## Key Features

- **4 project showcases** with filterable cards and MDX detail pages
- **AI chatbot** — floating widget with streaming responses, powered by a hybrid RAG pipeline (FAISS + BM25 + cross-encoder re-ranking) and Groq LLM
- **Cyberpunk design system** — glitch effects, neon glow, scanlines, chromatic aberration

---

## Development

```bash
make dev-frontend    # Next.js on :3000
make dev-backend     # FastAPI on :8000
make test            # Run all tests (pytest + vitest)
make lint            # Ruff + ESLint
make build-index     # Rebuild RAG search indexes
make stop            # Kill dev servers
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, tech decisions |
| [docs/chatbot-rag.md](docs/chatbot-rag.md) | RAG pipeline details (chunking, embedding, search, re-ranking) |
| [docs/design-system.md](docs/design-system.md) | Cyberpunk design tokens, typography, animations |
| [docs/deployment.md](docs/deployment.md) | Deploying to Vercel + Railway, environment variables |
| [docs/testing.md](docs/testing.md) | Test coverage approach, running tests |
| [SPEC.md](SPEC.md) | Full project specification |
