---
name: test-coverage
description: Ensure meaningful test coverage across the frontend and backend. Use when adding new features, components, endpoints, or service methods to verify tests exist and coverage is complete.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Test Coverage Skill

This project targets **meaningful coverage** — business logic, interactive components, and API behavior. Skip snapshot testing static layout components with no conditional logic. See `SPEC.md §12` for the full coverage policy.

## Coverage Targets

| Layer | Test Runner | Config |
|-------|-------------|--------|
| Backend | pytest | `backend/pyproject.toml` |
| Frontend | Vitest + React Testing Library | `frontend/vitest.config.mts` |

## Test Locations

| What | Where |
|------|-------|
| Backend endpoint tests | `backend/tests/test_chat.py`, `test_health.py` |
| Backend RAG pipeline tests | `backend/tests/test_rag.py` |
| Backend fixtures | `backend/tests/conftest.py` |
| Frontend component tests | `frontend/__tests__/` (to be created per component) |

## Workflow

### 1. Run the Existing Suite

```bash
make test

# Backend only (with coverage)
cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend only
cd frontend && npm run test -- --run
```

### 2. Map Changed Files to Required Tests

| Changed Area | Required Tests |
|---|---|
| New FastAPI route in `backend/app/routes/` | `backend/tests/test_<name>.py` — validation, success, error cases |
| Change to RAG pipeline in `backend/app/rag/pipeline.py` | `backend/tests/test_rag.py` — affected methods |
| Change to `scripts/build_index.py` | `backend/tests/test_rag.py` — chunking / stripping helpers |
| New interactive React component | `frontend/__tests__/<Component>.test.tsx` — render, states, interactions |
| Change to existing component | Extend its test file |

### 3. Write Backend Tests

Backend tests use `pytest` with FastAPI's synchronous `TestClient`. The `conftest.py` provides two key fixtures:

- **`mock_pipeline`** — a `MagicMock` of `RAGPipeline` with `retrieve` returning sample chunks; avoids loading real ML models
- **`client`** — a `TestClient` with `get_pipeline` patched in both `app.rag.pipeline` and `app.routes.chat`

**Groq streaming helper** (defined in `test_chat.py`):

```python
def _mock_groq_stream(tokens: list[str]):
    """Build an async mock that yields token chunks like the real Groq stream."""
    async def _stream():
        for token in tokens:
            chunk = MagicMock()
            chunk.choices[0].delta.content = token
            yield chunk

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_stream())
    return mock_client
```

**Key patterns:**

```python
# Endpoint — happy path with streamed response
def test_valid_request_streams_response(client, mock_pipeline):
    mock_groq = _mock_groq_stream(["Hello", " world"])
    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post("/api/chat", json={"message": "What is David's background?"})
    assert response.status_code == 200
    tokens = _parse_data_stream(response.text)
    assert tokens == ["Hello", " world"]

# Validation — Pydantic rejects bad input with 422
def test_empty_message_returns_422(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422

# Groq error — stream signals error via data stream protocol (HTTP 200, error event in body)
def test_groq_error_yields_error_event(client, mock_pipeline):
    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=Exception("API down"))
    with patch("app.routes.chat.AsyncGroq", return_value=mock_groq):
        response = client.post("/api/chat", json={"message": "Hello"})
    assert '3:"Generation failed"' in response.text

# RAG pipeline — with fake indexes in tmp_path
def test_hybrid_search_returns_chunks(fake_indexes):
    indexes_dir, chunks = fake_indexes
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.random.rand(1, 768).astype(np.float32)
    mock_cross_encoder = MagicMock()
    mock_cross_encoder.predict.return_value = np.array([0.9, 0.7, 0.5])
    with patch("app.rag.pipeline.INDEXES_DIR", indexes_dir), \
         patch("app.rag.pipeline.SentenceTransformer", return_value=mock_embedder), \
         patch("app.rag.pipeline.CrossEncoder", return_value=mock_cross_encoder):
        from app.rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        results = pipeline._hybrid_search("AI Engineer", top_k=3)
    assert len(results) > 0
```

Always test:
- Success path (correct response shape, correct status code)
- Validation errors (422 for bad input — handled by Pydantic)
- Error propagation (Groq failure → error event in stream body, not HTTP 500)
- RAG pipeline methods: search, re-ranking, prompt construction

### 4. Write Frontend Tests

Frontend tests use **Vitest** + **React Testing Library**. Test files go in `frontend/__tests__/` mirroring the component structure.

**Setup** (`vitest.setup.ts` already configured):
- jsdom environment
- `@testing-library/jest-dom` matchers available

**Key patterns:**

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FilterBar } from '@/components/home/FilterBar'

// Renders without error
it('renders all filter tags', () => {
  render(<FilterBar tags={['All', 'Python', 'Next.js']} active="All" onSelect={vi.fn()} />)
  expect(screen.getByText('Python')).toBeInTheDocument()
})

// User interaction
it('calls onSelect when a tag is clicked', async () => {
  const onSelect = vi.fn()
  render(<FilterBar tags={['All', 'Python']} active="All" onSelect={onSelect} />)
  await userEvent.click(screen.getByText('Python'))
  expect(onSelect).toHaveBeenCalledWith('Python')
})

// All active = 'All' resets filters
it('shows All as active by default', () => {
  render(<FilterBar tags={['All', 'Python']} active="All" onSelect={vi.fn()} />)
  expect(screen.getByText('All')).toHaveAttribute('aria-pressed', 'true')
})
```

**Priority components to test** (from `SPEC.md §12`):

| Priority | Component | Focus |
|----------|-----------|-------|
| High | `FilterBar` | Tag clicks, "All" resets, active state |
| High | `ProjectsSection` | Correct cards shown/hidden after filter |
| High | `ChatbotWidget` | Open/close, message display, input, error state |
| High | `ChatInput` | Debounce, 50-message limit, empty input blocked |
| Medium | `ProjectCard` | Renders title, description, tags, links |
| Medium | `ChatMessage` | User vs assistant rendering |
| Low | `Header` | Nav links, mobile menu |

Skip: `Hero`, `AboutSection`, `ContactSection`, `Footer`, `ScanlineOverlay` — static layout with no conditional logic.

### 5. Verify Coverage

```bash
# Backend — check for missing lines
cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend — run all tests
cd frontend && npm run test -- --run
```

## Rules

1. **Test behavior, not implementation** — assert on outputs and side-effects, not internal state.
2. **No real ML models in tests** — mock `SentenceTransformer`, `CrossEncoder`, and `AsyncGroq`. Use the `fake_indexes` fixture (tmp_path) for FAISS/BM25 tests.
3. **No real Groq API calls** — always patch `app.routes.chat.AsyncGroq`.
4. **Static components need no tests** — only test components with conditional rendering, state, or user interactions.
5. **One test file per source file** — `test_chat.py` covers `routes/chat.py`; `test_rag.py` covers `rag/pipeline.py` and `scripts/build_index.py`.

## Quick Checklist

Before marking a feature complete, verify:

- [ ] `make test` passes with zero failures
- [ ] New backend routes have tests: success, validation (422), error case
- [ ] New RAG pipeline methods have tests in `test_rag.py`
- [ ] New interactive components have tests: render, all UI states, user interactions
- [ ] No real API calls or model loading in any test
- [ ] No `# pragma: no cover` added without justification
