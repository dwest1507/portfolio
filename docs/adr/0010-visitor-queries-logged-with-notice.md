---
status: accepted
---

# Visitor questions are logged, minimally and with notice, to ground the Golden Set

Every paraphrase and conceptual case was authored, and authored questions drift toward
phrasings real visitors never type. Production logs the text of each question and the
number of chunks retrieved for it, and nothing else: no IP address, no conversation
history, no answer. The chat interface tells visitors that questions are logged
anonymously and answered by OpenAI.

Retrieved-chunk counts give the Empty Context rate in production, which BM25-only
retrieval made a design assumption without measuring.

Moving a logged question into the Golden Set is a manual act: it is read, stripped of
anything identifying, labelled, and marked with Case Origin `visitor`. Given ADR-0003, no
visitor text enters the repository unreviewed.

## Considered Options

- **No logging; hand-write colloquial cases** — rejected as the only source: it is still a
  guess at what visitors type. It remains the source until logs accumulate.

## Amendment (2026-10-11): no access log in production

"No IP address" has to hold for the service logs as a whole, not just the record. Uvicorn's
access log wrote a `POST /api/chat` line with the client's address immediately after each
`visitor_query` line, so the two could be paired by order and timestamp. Production now
starts uvicorn with `--no-access-log` (`backend/Dockerfile`); errors and startup messages
are still logged. Local development keeps the access log, since nothing local is collected.
