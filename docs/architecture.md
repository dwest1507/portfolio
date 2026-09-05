# Architecture

## System Diagram

```
Browser → Next.js (Vercel)                     Python FastAPI (Railway)
            ├── Static pages (SSG)               ├── POST /api/chat
            │   ├── Home (hero, projects,        │     ├── BM25 keyword search
            │   │   about, contact)              │     ├── Top 5 chunks as context
            │   └── Project detail pages (MDX)   │     ├── Prompt construction
            ├── /api/chat (proxy) ─────────────→ │     └── Groq LLM (streaming)
            │     (forwards to FastAPI)          ├── BM25 index (stemmed, stopword-filtered)
            └── Static assets                    ├── chunks.json (the corpus)
                                                 └── Rate limiting (in-memory + Groq backstop)
```

The served path carries no embedding model, no vector index and no re-ranker. It used to
carry all three; the evaluation harness measured them against plain BM25 on this corpus
and none of them won, so they were removed from production. They are still implemented in
`app/rag/pipeline.py` and still measured on every eval run — see
[docs/evaluation.md](evaluation.md) for the numbers and the reasoning.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend Framework | Next.js 15 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| Project Content | MDX (`@next/mdx`) |
| Backend Framework | Python FastAPI |
| RAG Pipeline (served) | BM25 over a stemmed, stopword-filtered index. No model weights. |
| RAG Pipeline (measured) | Also FAISS + sentence-transformers, weighted reciprocal-rank fusion, and cross-encoder re-ranking — eval-only, `dev` dependency group |
| Retrieval Eval | 55-question golden set split 33 dev / 22 held-out; hit@5 / recall@5 / MRR / nDCG@5, gated in CI on the shipped arm |
| LLM API | Groq (`GROQ_MODEL`, default `openai/gpt-oss-120b`) |
| Streaming | Vercel AI SDK (`useChat` hook) |
| Frontend Deployment | Vercel (free tier) |
| Backend Deployment | Railway (free tier, 500 hrs/month) |
| Frontend Testing | Vitest + React Testing Library |
| Backend Testing | pytest |
| Linting | ESLint + Prettier (frontend), Ruff (backend) |
| Analytics | Vercel Analytics (free tier) |

## Key Decisions

**Separate Python backend.** Originally because the RAG pipeline depended on FAISS,
sentence-transformers and cross-encoder re-ranking — Python-native ML libraries whose
cold-start cost is a poor fit for serverless. The evaluation has since removed all three
from the serving path, so that reason no longer holds; the service stays because the index
builder and the eval harness are Python, `rank-bm25` and the shared tokenizer are Python,
and server-side rate limiting still wants a long-lived process.

**Static-first frontend.** The Next.js app is entirely SSG except for the `/api/chat` proxy route. All project data and MDX content are defined in code — no CMS, no database.

**Next.js proxy for chat.** The frontend `/api/chat` route proxies to the FastAPI backend. This keeps the backend URL private and avoids CORS issues in the browser.

**Groq for LLM.** Fast inference on the free tier. Consistent with other projects in this portfolio.

**No light mode.** The cyberpunk design is dark-only — no theme toggle needed.

## Frontend Structure

```
frontend/
├── app/
│   ├── api/chat/route.ts          Proxy to FastAPI backend
│   ├── projects/[slug]/page.tsx   SSG project detail pages
│   ├── layout.tsx                 Root layout (header, footer, chatbot, analytics)
│   └── page.tsx                   Home page
├── components/
│   ├── layout/                    Header, Footer, Section, ScanlineOverlay
│   ├── home/                      Hero, ProjectsSection, ProjectCard, FilterBar,
│   │                              AboutSection, ContactSection
│   ├── chatbot/                   ChatbotWidget, ChatMessage, ChatInput
│   ├── projects/                  ProjectDetail, mdxComponents
│   └── ui/                        Button, Card, Tag, FadeIn
├── content/projects/              MDX write-ups for each project
└── data/projects.ts               Project metadata (slug, title, tags, URLs)
```

## Backend Structure

```
backend/
├── app/
│   ├── main.py                    FastAPI app, CORS, middleware
│   ├── config.py                  Environment variable loading
│   ├── rag/pipeline.py            BM25 retrieval (served); dense + re-ranking (measured)
│   └── routes/
│       ├── chat.py                POST /api/chat
│       └── health.py              GET /api/health
├── scripts/build_index.py         Offline index builder
├── eval/                          Golden set, retrieval harness, publishing
└── indexes/                       BM25 model, chunks JSON, FAISS index (eval-only)
```

## Data Flow: Chat Request

1. User types a message in the chatbot widget
2. `useChat` (Vercel AI SDK) sends `POST /api/chat` to Next.js proxy
3. Next.js proxy forwards to `POST /api/chat` on FastAPI
4. FastAPI runs BM25 keyword search over the chunk index and takes the top 5
5. Constructs a prompt with context chunks + conversation history
6. Streams Groq LLM response back through the proxy to the browser
7. `useChat` renders tokens as they arrive

## API Reference

### `POST /api/chat`

```json
// Request
{
  "message": "What experience does David have with LLMs?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}

// Response: streamed text (SSE)
```

| Status | Condition |
|--------|-----------|
| 400 | Empty message or message > 500 characters |
| 429 | Rate limit exceeded (30 req/min per IP) |
| 502 | Backend unavailable |
| 500 | Unexpected error |

### `GET /api/health`

```json
{ "status": "ok" }
```
