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

   Redaction and detection are deliberately asymmetric. The redactor in
   `build_index.py` is **precise** — it strips only unambiguous phone shapes
   (parenthesized area code, or dot/dash separators) and labelled ones
   (`Phone: 586 555 0147`). It rewrites the corpus silently, so a false positive
   there deletes real content — a metric, an ID, a quantity — with no signal
   that anything was lost. The guard in `tests/test_pii.py` is **broad**: it
   matches bare 10-digit runs and punctuation-free international forms too. Its
   only power is to fail a build, so a false positive costs one human glance.

   The consequence is intentional: a bare `5865550147` in a source document is
   not silently redacted, it fails the test, and the source gets fixed. That is
   the stated order of operations — the sources should be clean to begin with,
   and redaction is only the backstop.
2. **Chunk** — ~200–300 token chunks with overlap; paragraph-based splitting to preserve complete thoughts
3. **Embed** — `sentence-transformers` (`all-mpnet-base-v2`) generates a vector per chunk
4. **Index** — Builds a FAISS index (vector search) and a BM25 index (keyword search).
   BM25 terms are lowercased, stopword-filtered, and Snowball-stemmed by
   `app/rag/tokenize.py` — the same tokenizer the query path uses, so index and
   query terms always agree.
5. **Save** — Writes `backend/indexes/faiss.index`, `bm25.pkl`, and `chunks.json`

The indexes are committed to the repo. `chunks.json` and `bm25.pkl` are loaded into memory
at FastAPI startup; `faiss.index` is not, because the served pipeline does not use it —
steps 3 and 4's vector half exist for the evaluation harness. See
[evaluation.md](evaluation.md).

The three artefacts are built together and must stay together. `RAGPipeline.__init__`
refuses to construct when `bm25.pkl` and `chunks.json` disagree on how many documents
exist, because BM25 returns *positions* that `sparse_search` hands straight to
`chunks[i]`: a stale pickle either raises on a live request or, worse, serves the text of
the wrong chunk with no error at all. The equivalent check for `faiss.index` moved to the
lazy loader when dense retrieval left the serving path — a stale dense index can now only
mislead the harness, which is who it raises for. Rebuild all three with `make build-index`
and commit them together.

## Runtime Pipeline (`POST /api/chat`)

```
User query
    │
    ▼
BM25 keyword search
(shared stemmed, stopword-filtered tokenizer)
Top 5 chunks selected — fewer if the query
shares no term with any chunk
    │
    ▼
Prompt construction
(system + context + history)
    │
    ▼
Groq API (GROQ_MODEL env var)
Streaming SSE response
```

No embedding model, no vector search, no re-ranker. The pipeline used to run all three;
the evaluation harness measured each against plain BM25 on this corpus and none of them
won, so they were removed from the serving path. `RAGPipeline` still implements them and
the harness still measures them on every run — see [evaluation.md](evaluation.md) and
[ADR-0004](adr/0004-retrieval-shipped-arm-chosen-by-measurement.md).

An empty context is a deliberate outcome rather than a bug: the system prompt tells the
model to say so honestly when the context does not contain the answer, which is a better
failure than five irrelevant chunks to sound confident from.

It is *stated*, not merely left blank. `build_messages` substitutes
`(No relevant context was retrieved for this question.)` for an empty context, and the
system prompt names the conversation history as history rather than context. Both exist
for the same reason: a bare `Context:` heading tells a model instructed to use only the
context that there is nothing to use, while leaving up to ten prior turns in the window as
the one remaining source of material to answer from.

### Prompt Template

```
System: You are David West's AI assistant on his portfolio website.
Answer questions about David's experience, skills, and projects using
ONLY the provided context. If the context doesn't contain the answer,
say so honestly. Be concise and professional. Do not make up information.
Earlier turns of the conversation are history, not context: never answer
from them when the context below is empty.

Context:
{top 5 retrieved chunks, or "(No relevant context was retrieved for this question.)"}

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

| Purpose | Model | Where it runs |
|---------|-------|---------------|
| LLM | `openai/gpt-oss-120b` via Groq, overridable with `GROQ_MODEL` | Production |
| Embedding | `sentence-transformers/all-mpnet-base-v2` | Index build + eval only |
| Re-ranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Eval only |

Neither model is installed in the production image: `faiss-cpu` and `sentence-transformers`
live in the `dev` dependency group, which the Dockerfile's `uv sync --no-dev` skips.

## Environment Variables

| Variable | Where | Description |
|----------|-------|-------------|
| `GROQ_API_KEY` | Railway (backend) | Groq API key |
| `CHAT_API_URL` | Vercel (frontend) | URL of the FastAPI backend |
| `ALLOWED_ORIGINS` | Railway (backend) | CORS allowed origins (Vercel URL) |

## Fusion

Dense and sparse results are combined with weighted reciprocal-rank fusion:
each list contributes `weight / (k + rank)` for the documents it returns, with
dense weighted 0.7 and sparse 0.3.

The damping constant `k` is **1**, not the 60 from Cormack et al. (2009). That
default assumes ranked lists thousands of documents long; here the lists are 10
items, where `k=60` varies the rank term by only 1.15x across the whole list
while the 0.7/0.3 weights vary by 2.33x. The weights then dominate outright:
every dense hit outscores every sparse hit, and BM25 can never introduce a
candidate the dense arm missed — which is the only reason the sparse arm is
there. `k=1` places a sparse-only top hit around 4th in the fused list, inside
the candidate set, while leaving the top dense hit in front.

RRF replaced an earlier scheme that min-max normalized each retriever's scores
and summed them. That was unsound: normalizing a list against itself forces its
top hit to 1.0 and its last hit to 0.0 regardless of absolute quality, so a
list of uniformly irrelevant results contributed exactly as much as a list of
excellent ones, and the lowest-ranked candidate of each list was always
discarded at zero. Rank position is scale-free and has neither problem.

## Evaluation

Retrieval quality is measured against a 55-question golden set and gated in CI.
See [evaluation.md](evaluation.md).
