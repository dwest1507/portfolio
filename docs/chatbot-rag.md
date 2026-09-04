# AI Chatbot & RAG Pipeline

The chatbot answers recruiter questions about David's experience, skills, and projects using a Retrieval-Augmented Generation (RAG) pipeline backed by Groq for LLM inference.

## User Experience

- Floating button (bottom-right) with neon glow, opens a ~400×500px chat panel
- Terminal-style input with `>` prefix
- Responses stream token-by-token
- Welcome message: *"Hi! I'm David's AI assistant. Ask me anything about his experience, skills, or projects."*
- Chat history persists for the browser session (cleared on tab close)
- Max 50 messages per session; 1 message per 3 seconds (client-side debounce)

## Index Build (Offline)

Run once before deploying (or when source data changes):

```bash
make build-index
```

`scripts/build_index.py` performs:

1. **Load sources** — `docs/resume.txt`, `docs/chatbot-questions.md`, and the
   project write-ups in `frontend/content/projects/*.mdx`, then **redact**
   contact PII (street address, phone numbers) before anything is indexed. The
   chatbot reads indexed text back to anyone who asks for it, so what goes in
   the index is published.
2. **Chunk** — ~200–300 token chunks with overlap; paragraph-based splitting to preserve complete thoughts
3. **Embed** — `sentence-transformers` (`all-mpnet-base-v2`) generates a vector per chunk
4. **Index** — Builds a FAISS index (vector search) and a BM25 index (keyword search).
   BM25 terms are lowercased, stopword-filtered, and Snowball-stemmed by
   `app/rag/tokenize.py` — the same tokenizer the query path uses, so index and
   query terms always agree.
5. **Save** — Writes `backend/indexes/faiss.index`, `bm25.pkl`, and `chunks.json`

The indexes are committed to the repo and loaded into memory at FastAPI startup.

## Runtime Pipeline (`POST /api/chat`)

```
User query
    │
    ▼
Embed query (all-mpnet-base-v2)
    │
    ├──► FAISS semantic search  ─┐
    │    (top-k candidates)      ├──► Weighted RRF fusion
    └──► BM25 keyword search   ──┘     (0.7 semantic / 0.3 keyword)
                                 │
                                 ▼
                    Cross-encoder re-ranking
                    (ms-marco-MiniLM-L-6-v2)
                    Top 5 chunks selected
                                 │
                                 ▼
                    Prompt construction
                    (system + context + history)
                                 │
                                 ▼
                    Groq API (GROQ_MODEL env var)
                    Streaming SSE response
```

### Prompt Template

```
System: You are David West's AI assistant on his portfolio website.
Answer questions about David's experience, skills, and projects using
ONLY the provided context. If the context doesn't contain the answer,
say so honestly. Be concise and professional. Do not make up information.

Context:
{top 5 re-ranked chunks}

Conversation history:
{last 10 messages}
```

## Rate Limiting

| Layer | Limit |
|-------|-------|
| Client-side | 50 messages/session, 1 message/3 seconds |
| FastAPI (`slowapi`) | 30 requests/minute per IP |
| Groq backstop | 14,400 requests/day, 30 req/min (free tier) |

## Error Handling

- **API failure** — displays *"Sorry, I'm having trouble responding right now. Please try again."* (no raw error details exposed)
- **Truncated response** — appends `...` rather than cutting mid-word

## Models Used

| Purpose | Model |
|---------|-------|
| Embedding | `sentence-transformers/all-mpnet-base-v2` |
| Re-ranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | `openai/gpt-oss-120b` via Groq, overridable with `GROQ_MODEL` |

## Environment Variables

| Variable | Where | Description |
|----------|-------|-------------|
| `GROQ_API_KEY` | Railway (backend) | Groq API key |
| `CHAT_API_URL` | Vercel (frontend) | URL of the FastAPI backend |
| `ALLOWED_ORIGINS` | Railway (backend) | CORS allowed origins (Vercel URL) |

## Fusion

Dense and sparse results are combined with weighted reciprocal-rank fusion:
each list contributes `weight / (60 + rank)` for the documents it returns.

RRF replaced an earlier scheme that min-max normalized each retriever's scores
and summed them. That was unsound: normalizing a list against itself forces its
top hit to 1.0 and its last hit to 0.0 regardless of absolute quality, so a
list of uniformly irrelevant results contributed exactly as much as a list of
excellent ones, and the lowest-ranked candidate of each list was always
discarded at zero. Rank position is scale-free and has neither problem.

## Evaluation

Retrieval quality is measured against a 55-question golden set and gated in CI.
See [evaluation.md](evaluation.md).
