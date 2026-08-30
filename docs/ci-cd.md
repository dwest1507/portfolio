# CI Pipeline

The pipeline's logic lives in **`scripts/`** at the repo root; `.github/workflows/`
and the `Makefile` both call the same scripts, so a check behaves identically locally
and in CI.

GitHub Actions **does not deploy**. Vercel and Railway deploy from `main` through their
own git integrations — see [deployment.md](deployment.md). Actions is purely the
quality gate: tests, linting, security scans, and performance budgets.

## Running the pipeline locally

```bash
make ci-cd   # every CI check, in order — exactly what the PR gates run
```

`make ci-cd` runs: frontend quality (ESLint, Prettier, tsc) → frontend tests →
frontend build → backend lint (ruff) → backend tests → security audits
(npm audit + pip-audit) → Lighthouse budget.

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

What can't run locally: CodeQL, gitleaks, and dependency review are GitHub-hosted
analyses inside `security.yml`. Everything else is script-for-script identical.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `frontend-ci.yml` | PRs and pushes to `main` touching `frontend/**`; manual dispatch | `scripts/frontend-quality.sh` (ESLint, Prettier, tsc), `frontend-test.sh` (Vitest), `frontend-build.sh` |
| `backend-ci.yml` | PRs and pushes to `main` touching `backend/**`; manual dispatch | `scripts/backend-lint.sh` (ruff check + format), `backend-test.sh` (pytest, ML models mocked) |
| `security.yml` | PRs, pushes to `main`, weekly cron | CodeQL (TS + Python), gitleaks secret scan, `scripts/security-audit.sh` (npm audit prod/high+, pip-audit), dependency review on PRs |
| `lighthouse.yml` | PRs touching `frontend/**` | `scripts/lighthouse.sh` — Lighthouse CI against the production build; asserts ≥ 0.9 on accessibility / best-practices / SEO (performance warns) per `frontend/lighthouserc.json` |
| `release.yml` | Pushes to `main` | [Release Please](https://github.com/googleapis/release-please) — maintains the release PR, then tags and publishes the GitHub Release when it merges |

Node is pinned by `frontend/.nvmrc` and read via `node-version-file:` in every
workflow — CI must resolve `package-lock.json` with the same npm major that generated
it, or `npm ci` fails on peer dependencies.

## Making CI block deploys

Since the platforms deploy on push to `main` independent of Actions, CI is advisory
unless `main` is protected. Add a branch protection rule requiring the CI checks and
merge through PRs — the setup is in
[deployment.md § Optional: gate deploys behind CI](deployment.md#optional-gate-deploys-behind-ci).

## Backend container

Railway builds `backend/Dockerfile`. The service's builder must be set to **Dockerfile**
in the dashboard — new services default to Railpack, which ignores the Dockerfile and
would install dependencies and download models at runtime. Build and deploy settings all
live in the dashboard; see [deployment.md](deployment.md#step-2--deploy-the-backend-railway):

- `python:3.14-slim` + `uv sync --frozen --no-dev` from `uv.lock`
- Embedding + cross-encoder models are **baked into the image**, so cold starts never
  download from Hugging Face
- FAISS/BM25 indexes are copied from `backend/indexes/` (build them with `make build-index`
  and commit before deploying)
- Runs as a non-root user; Railway health-checks `/api/health` with a 300s startup budget

## Releases

`release.yml` runs Release Please on every push to `main`. It reads
`release-please-config.json` and `.release-please-manifest.json` at the repo root and
keeps an open **release PR** in sync with the conventional commits landed since the last
release. Merging that PR is what cuts a release:

- bumps the version in `frontend/package.json` and `backend/pyproject.toml`
  (the `# x-release-please-version` comment marks the line release-please rewrites)
- writes the entry into `CHANGELOG.md`
- updates `.release-please-manifest.json`
- creates the `v<version>` tag and the GitHub Release

Frontend and backend are versioned together as one unit — `release-type: simple` with
both version files listed under `extra-files`. Commits that aren't conventional
(`feat:`, `fix:`, `feat!:`/`BREAKING CHANGE:`, …) are ignored, so they never appear in
the changelog and never trigger a bump. To force a specific version, add a
`Release-As: X.Y.Z` footer to a commit on `main`.

Nothing about releases gates or triggers deploys — Vercel and Railway still deploy from
`main` on every push, tag or not.

## Dependency updates

`.github/dependabot.yml` opens weekly grouped PRs for npm (frontend) and uv (backend),
monthly for GitHub Actions. Each PR runs the full CI + security gauntlet before merge.
