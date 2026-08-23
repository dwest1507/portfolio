# CI/CD Pipeline

All automation lives in `.github/workflows/`. Deploys are driven by GitHub Actions —
the Vercel/Railway git integrations are intentionally **not** used, so nothing reaches
production without CI passing first.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `frontend-ci.yml` | PRs touching `frontend/**`; called by Deploy | ESLint, Prettier check, `tsc --noEmit`, Vitest, production build |
| `backend-ci.yml` | PRs touching `backend/**`; called by Deploy | Ruff check + format check, pytest (ML models mocked) |
| `security.yml` | PRs, pushes to `main`, weekly cron | CodeQL (TS + Python), gitleaks secret scan, `npm audit` (prod deps, high+), `pip-audit`, dependency review on PRs |
| `lighthouse.yml` | PRs touching `frontend/**` | Lighthouse CI against the production build; asserts ≥ 0.9 on accessibility / best-practices / SEO (performance warns) per `frontend/lighthouserc.json` |
| `deploy-preview.yml` | PRs touching `frontend/**` | Vercel preview deployment, URL commented on the PR |
| `deploy.yml` | Push to `main`, manual dispatch | Change detection → re-runs the relevant CI workflows → deploys frontend (Vercel CLI) and/or backend (Railway CLI) → post-deploy health checks |

## Deploy flow (`deploy.yml`)

```
push to main
   │
   ├─ changes: dorny/paths-filter → frontend? backend?
   │
   ├─ frontend changed ──► frontend-ci ──► deploy-frontend (Vercel)
   │                                          vercel pull → build → deploy --prebuilt --prod
   │                                          └─ smoke test: GET / must return 200
   │
   └─ backend changed ───► backend-ci ───► deploy-backend (Railway)
                                              railway up --service $RAILWAY_SERVICE --ci
                                              └─ health check: GET /api/health must return 200
```

- A `production-deploy` concurrency group serializes deploys and never cancels one mid-flight.
- `workflow_dispatch` redeploys both services regardless of what changed (useful after env var changes).
- Deploy jobs run in the `production-frontend` / `production-backend` GitHub environments, so
  approval gates can be added later from repo settings without touching the workflows.

## Required repository secrets

| Secret | Used by | Where to get it |
|--------|---------|-----------------|
| `VERCEL_TOKEN` | deploy, preview | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | deploy, preview | `frontend/.vercel/project.json` after `vercel link` |
| `VERCEL_PROJECT_ID` | deploy, preview | same file |
| `RAILWAY_TOKEN` | deploy | Railway project → Settings → Tokens (project token) |

## Required repository variables

| Variable | Used by | Value |
|----------|---------|-------|
| `RAILWAY_SERVICE` | deploy | Railway service name (e.g. `backend`) |
| `BACKEND_URL` | deploy health check | Public Railway URL (e.g. `https://….up.railway.app`) |

## Backend container

Railway builds `backend/Dockerfile` (configured by `backend/railway.json`):

- `python:3.14-slim` + `uv sync --frozen --no-dev` from `uv.lock`
- Embedding + cross-encoder models are **baked into the image**, so cold starts never
  download from Hugging Face
- FAISS/BM25 indexes are copied from `backend/indexes/` (build them with `make build-index`
  and commit before deploying)
- Runs as a non-root user; Railway health-checks `/api/health` with a 300s startup budget

## Dependency updates

`.github/dependabot.yml` opens weekly grouped PRs for npm (frontend) and uv (backend),
monthly for GitHub Actions. Each PR runs the full CI + security gauntlet before merge.
