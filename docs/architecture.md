# Architecture

## System Diagram

```
Browser → Next.js (Vercel)                     Python FastAPI (Railway)
            ├── Static pages (SSG)               ├── POST /api/chat
            │   ├── Home (hero, projects,        │     ├── Embed query (sentence-transformers)
            │   │   about, contact)              │     ├── Hybrid search (FAISS + BM25)
            │   └── Project detail pages (MDX)   │     ├── Cross-encoder re-ranking
            ├── /api/chat (proxy) ─────────────→ │     ├── Prompt construction
            │     (forwards to FastAPI)          │     └── Groq LLM (streaming)
            └── Static assets                    ├── FAISS index (pre-built, loaded at startup)
                                                 └── Rate limiting (in-memory + Groq backstop)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend Framework | Next.js 15 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| Project Content | MDX (`@next/mdx`) |
| Backend Framework | Python FastAPI |
| RAG Pipeline | FAISS + BM25 (hybrid), sentence-transformers, cross-encoder re-ranking |
| LLM API | Groq (`llama-3.3-70b-versatile`) |
| Streaming | Vercel AI SDK (`useChat` hook) |
| Frontend Deployment | Vercel (free tier) |
| Backend Deployment | Railway (free tier, 500 hrs/month) |
| Frontend Testing | Vitest + React Testing Library |
| Backend Testing | pytest |
| Linting | ESLint + Prettier (frontend), Ruff (backend) |
| Analytics | Vercel Analytics (free tier) |

## Key Decisions

**Separate Python backend.** The RAG pipeline depends on FAISS, sentence-transformers, and cross-encoder re-ranking — all Python-native ML libraries. A dedicated FastAPI service avoids serverless cold-start issues with large ML models and enables proper server-side rate limiting.

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
│   ├── rag/pipeline.py            Embedding, hybrid search, re-ranking
│   └── routes/
│       ├── chat.py                POST /api/chat
│       └── health.py              GET /api/health
├── scripts/build_index.py         Offline index builder
└── indexes/                       Pre-built FAISS index, BM25 model, chunks JSON
```

## Data Flow: Chat Request

1. User types a message in the chatbot widget
2. `useChat` (Vercel AI SDK) sends `POST /api/chat` to Next.js proxy
3. Next.js proxy forwards to `POST /api/chat` on FastAPI
4. FastAPI embeds the query, runs hybrid search, re-ranks results
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
