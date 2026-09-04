# Context Map

## Contexts

- [Backend](./backend/CONTEXT.md) — the RAG pipeline that answers questions about David's
  experience, and the evaluation harness that measures whether its retrieval works
- [Frontend](./frontend/CONTEXT.md) — the portfolio site, including the public write-up
  that publishes the evaluation's results

## Relationships

- **Backend → Frontend**: the evaluation harness is the single source of truth for which
  retrieval configurations exist. It emits a Measured Run, which the frontend renders. The
  frontend never names an Arm the harness has not reported.
- **Frontend → Backend**: project write-ups under `frontend/content/projects/*.mdx` are
  source documents for the index the backend serves, so frontend prose is part of the
  corpus the backend's evaluation measures.
