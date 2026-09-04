# Testing

## Philosophy

Focus on business logic, interactive components, and API behavior. Skip snapshot testing static layout components with no conditional logic.

## Running Tests

```bash
make test                  # Run all tests (pytest + vitest)

# Frontend only
cd frontend
npm test                   # Watch mode
npm run test -- --run      # Single run
npm run test -- --coverage # With coverage report

# Backend only
cd backend
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=app
```

## Frontend Tests (Vitest + React Testing Library)

| Priority | Component | What's Tested |
|----------|-----------|---------------|
| High | `FilterBar` | Filters update visible cards; "All" resets; active state styling |
| High | `ProjectsSection` | Correct cards shown/hidden after filter selection |
| High | `ChatbotWidget` | Open/close toggle; message display; input handling; error state |
| High | `ChatInput` | Debounce (3s); 50-message limit enforcement; empty input prevention |
| Medium | `ProjectCard` | Renders title, description, tags, and links |
| Medium | `ChatMessage` | User vs assistant message rendering |
| Low | `Header` | Nav links render; mobile menu works |

Test files live in `frontend/__tests__/` (one file per component). jsdom shims for
`IntersectionObserver` and `scrollIntoView` are provided by `frontend/vitest.setup.ts`;
the `useChat` hook from `@ai-sdk/react` is mocked in `ChatbotWidget.test.tsx`.

All suites also run in CI on every PR (`.github/workflows/frontend-ci.yml`,
`backend-ci.yml`) and gate production deploys — see [ci-cd.md](ci-cd.md).

## Backend Tests (pytest)

| Priority | Area | What's Tested |
|----------|------|---------------|
| High | `POST /api/chat` | Valid request returns streamed response |
| High | `POST /api/chat` | Empty message → 400 |
| High | `POST /api/chat` | Message > 500 chars → 400 |
| High | `POST /api/chat` | Groq API error → 500 with safe message |
| High | RAG pipeline | Hybrid search returns relevant chunks |
| High | RAG pipeline | Cross-encoder re-ranking improves result order |
| High | RAG pipeline | Prompt construction includes context and history |
| Medium | Rate limiting | Exceeding 30 req/min → 429 |
| Medium | Chunking | Correct chunk sizes with overlap |
| High | PII guard | No phone number or street address in the committed index or any indexed source, including the project MDX |
| High | PII asymmetry | Broad detector catches bare digit runs; precise redactor leaves metrics and IDs untouched |
| High | Tokenizer | Stemming unifies "engineer"/"engineering"; stopwords dropped; "R" survives |
| High | RRF fusion | Agreement between retrievers wins; weights shift order; no item zeroed; a BM25-only hit reaches the candidate set |
| Medium | Eval metrics | recall@k, hit@k, MRR, nDCG@k computed correctly |
| Medium | `GET /api/health` | Returns 200 `{ "status": "ok" }` |

Test files are in `backend/tests/`. Fixtures (including mock indexes) are defined
in `backend/tests/conftest.py`. The FastAPI `TestClient` import is deferred into
the `client` fixture so the tests that never touch the HTTP layer (tokenizer,
fusion, PII, chunking) can run without importing FastAPI.

## Retrieval Evaluation

Unit tests check that retrieval code behaves as written; they cannot tell you
whether retrieval is any *good*. That is measured separately by a 55-question
golden set scored on hit@5, recall@5, MRR, and nDCG@5, and gated in CI:

```bash
make eval        # all arms (downloads ~500MB of models on first run)
make eval-fast   # BM25 arm only — no model download
```

See [evaluation.md](evaluation.md) for method, current numbers, and thresholds.
