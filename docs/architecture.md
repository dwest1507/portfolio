# Architecture

## System Diagram

```
Browser → Next.js (Vercel)                     Python FastAPI (Railway)
            ├── Static pages (SSG)               ├── POST /api/chat
            │   ├── Home (hero, projects,        │     ├── BM25 keyword search
            │   │   about, contact)              │     ├── Top 5 chunks as context
            │   └── Project detail pages (MDX)   │     ├── Prompt construction
            ├── /api/chat (proxy) ─────────────→ │     └── OpenAI LLM (streaming)
            │     (forwards to FastAPI)          ├── BM25 index (stemmed, stopword-filtered)
            └── Static assets                    ├── chunks.json (the corpus)
                                                 └── Rate limiting (per-IP + global daily cap;
                                                     OpenAI project budget as backstop)
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
| Retrieval Eval | 111 answerable golden questions split 68 dev / 43 held-out (plus 20 Out-of-Scope Cases the harness skips) across three query categories (`direct`, `paraphrase`, `conceptual`); hit@5 / recall@5 / MRR / nDCG@5, gated in CI on the shipped arm |
| LLM API | OpenAI (`OPENAI_MODEL`, default `gpt-6-luna`) |
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

**OpenAI for LLM, chosen by measurement.** Generation moved from Groq's free tier to
OpenAI's `gpt-6-luna` after the generation eval compared it with the Groq baseline and
`gpt-6.1-sol` ([ADR-0008](adr/0008-generation-moves-to-openai.md)). A paid API behind an
anonymous endpoint is guarded by a global daily request cap in the app and a hard
monthly budget on the OpenAI project.

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
├── eval/                          Golden set, retrieval + generation harnesses, Judge, publishing, baselines
└── indexes/                       BM25 model, chunks JSON, FAISS index (eval-only)
```

## Data Flow: Chat Request

1. User types a message in the chatbot widget
2. `useChat` (Vercel AI SDK) sends `POST /api/chat` to Next.js proxy
3. Next.js proxy forwards to `POST /api/chat` on FastAPI
4. FastAPI runs BM25 keyword search over the chunk index and takes the top 5, and logs
   the question text with the number of chunks retrieved — nothing else (ADR-0010)
5. Constructs a prompt with context chunks + conversation history
6. Streams the OpenAI response back through the proxy to the browser (past the global
   daily cap, steps 4–5 are skipped and a "resting for today" message is streamed instead)
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

// Response: streamed text (SSE). Past the global daily cap (DAILY_REQUEST_CAP per UTC
// day), the stream is a single polite "the assistant is resting for today" message.
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
