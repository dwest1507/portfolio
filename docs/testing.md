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

Test files live alongside source files or in `frontend/__tests__/`.

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
| Medium | `GET /api/health` | Returns 200 `{ "status": "ok" }` |

Test files are in `backend/tests/`. Fixtures (including mock indexes) are defined in `backend/tests/conftest.py`.
