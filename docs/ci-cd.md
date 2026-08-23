# CI/CD Pipeline

The pipeline's logic lives in **`scripts/`** at the repo root; `.github/workflows/`
and the `Makefile` both call the same scripts, so a check behaves identically locally
and in CI. Deploys are driven by GitHub Actions — the Vercel/Railway git integrations
are intentionally **not** used, so nothing reaches production without CI passing first.

## Running the pipeline locally

```bash
make ci-cd   # every CI check, in order — exactly what the PR gates run
```

`make ci-cd` runs: frontend quality (ESLint, Prettier, tsc) → frontend tests →
frontend build → backend lint (ruff) → backend tests → security audits
(npm audit + pip-audit) → Lighthouse budget. Deploys are **not** included — those
only run from GitHub Actions on `main`.

Each check also has its own target for debugging a single failure:

| Make target | Script | Mirrors |
|-------------|--------|---------|
| `make frontend-quality` | `scripts/frontend-quality.sh` | frontend-ci → quality job |
| `make frontend-test` | `scripts/frontend-test.sh` | frontend-ci → test job |
| `make frontend-build` | `scripts/frontend-build.sh` | frontend-ci → build job |
| `make backend-lint` | `scripts/backend-lint.sh` | backend-ci → lint job |
| `make backend-test` | `scripts/backend-test.sh` | backend-ci → test job |
| `make security-audit` | `scripts/security-audit.sh all` | security → npm-audit + pip-audit jobs |
| `make lighthouse` | `scripts/lighthouse.sh` | lighthouse workflow (needs Chrome) |
| `make deploy-frontend[-preview]` | `scripts/deploy-frontend.sh` | deploy / deploy-preview workflows |
| `make deploy-backend` | `scripts/deploy-backend.sh` | deploy workflow |

The deploy scripts exist locally so their logic can be exercised (they validate
their env vars — `VERCEL_TOKEN`/`VERCEL_ORG_ID`/`VERCEL_PROJECT_ID`,
`RAILWAY_TOKEN`/`RAILWAY_SERVICE` — and fail fast with a clear message if unset),
but production deploys are meant to happen only via Actions.

What can't run locally: CodeQL, gitleaks, and dependency review are GitHub-hosted
analyses inside `security.yml`; the PR preview-URL comment is GitHub-only glue in
`deploy-preview.yml`. Everything else is script-for-script identical.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `frontend-ci.yml` | PRs touching `frontend/**`; called by Deploy | `scripts/frontend-quality.sh` (ESLint, Prettier, tsc), `frontend-test.sh` (Vitest), `frontend-build.sh` |
| `backend-ci.yml` | PRs touching `backend/**`; called by Deploy | `scripts/backend-lint.sh` (ruff check + format), `backend-test.sh` (pytest, ML models mocked) |
| `security.yml` | PRs, pushes to `main`, weekly cron | CodeQL (TS + Python), gitleaks secret scan, `scripts/security-audit.sh` (npm audit prod/high+, pip-audit), dependency review on PRs |
| `lighthouse.yml` | PRs touching `frontend/**` | `scripts/lighthouse.sh` — Lighthouse CI against the production build; asserts ≥ 0.9 on accessibility / best-practices / SEO (performance warns) per `frontend/lighthouserc.json` |
| `deploy-preview.yml` | PRs touching `frontend/**` | `scripts/deploy-frontend.sh preview`, URL commented on the PR |
| `deploy.yml` | Push to `main`, manual dispatch | Change detection → re-runs the relevant CI workflows → `scripts/deploy-frontend.sh production` / `scripts/deploy-backend.sh` with built-in smoke/health checks |

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
