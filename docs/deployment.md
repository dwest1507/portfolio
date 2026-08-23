# Deployment

## Overview

| Service | Platform | Free Tier |
|---------|----------|-----------|
| Frontend | Vercel | 100 GB bandwidth, 6,000 build min/month |
| Backend | Railway | 500 execution hours/month |
| LLM | Groq | 14,400 requests/day, 30 req/min |
| Analytics | Vercel Analytics | 2,500 events/month |

Deploys are handled by the **native Vercel and Railway git integrations**: both
platforms watch this repo and redeploy on every push to `main`. GitHub Actions runs
tests, linting, security scans, and Lighthouse (see [ci-cd.md](ci-cd.md)) but does not
deploy — there are no deploy tokens in GitHub.

```
push / merge to main
   │
   ├─ GitHub Actions ─► CI + security + Lighthouse (quality signal)
   ├─ Vercel          ─► builds frontend/  ─► production frontend
   └─ Railway         ─► builds backend/Dockerfile ─► production backend
```

Because the platforms deploy independently of CI, a red CI run does **not** block a
deploy. Run `make ci-cd` before pushing, or merge through a PR with branch protection
requiring the CI checks (see [Optional: gate deploys behind CI](#optional-gate-deploys-behind-ci)).

This is a monorepo, so each platform is pointed at its own subdirectory and told to
ignore changes outside it.

---

## Step 1 — Before anything else: build the indexes

The RAG indexes are committed to the repo and copied into the backend image at build
time. Without them the backend starts but cannot answer questions.

```bash
make build-index
git add backend/indexes && git commit -m "chore: rebuild RAG indexes"
```

Re-run this whenever `backend/data/` changes.

---

## Step 2 — Deploy the backend (Railway)

Do the backend first: the frontend needs the backend's URL.

1. Sign in at [railway.com](https://railway.com) with GitHub.
2. **New Project → Deploy from GitHub repo** → select this repository. Authorize the
   Railway GitHub App for the repo if prompted.
3. Open the created service → **Settings** and set these. There is no config file in
   the repo — Railway's Config as Code (`railway.json` / `railway.toml`) is deprecated
   and stops being read on 2026-12-01, so the service is configured here:

   | Setting | Value | Section |
   |---------|-------|---------|
   | Root Directory | `backend` | Source |
   | Branch | `main` | Source |
   | Watch Paths | `backend/**` | Source |
   | Healthcheck Path | `/api/health` | Deploy |
   | Healthcheck Timeout | `300` | Deploy |
   | Restart Policy | On Failure, 3 max retries | Deploy |

   - The builder needs no setting: with the root directory at `backend`, Railway
     detects `backend/Dockerfile` and uses it. Leave build and start commands empty —
     the Dockerfile's `CMD` starts uvicorn on `$PORT`.
   - **Set the healthcheck timeout explicitly.** The image bakes the embedding and
     cross-encoder models, so first boot is slow; the default timeout is far shorter
     and is the most likely cause of a deploy stalling on "waiting for healthcheck".
   - Watch paths keep frontend-only pushes from rebuilding the container.
4. **Variables** tab → add:

   | Variable | Value |
   |----------|-------|
   | `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
   | `ALLOWED_ORIGINS` | Vercel production URL — fill in after Step 3, e.g. `https://your-site.vercel.app` |
   | `PORT` | `8000` |

   The Dockerfile starts uvicorn on `${PORT:-8000}`, so 8000 is also the fallback —
   pinning `PORT` just keeps the app and the domain's target port from ever disagreeing.
5. **Settings → Networking → Generate Domain** to get a public URL
   (`https://<something>.up.railway.app`). When prompted for a **target port**, enter
   **`8000`** — the port the container listens on (`EXPOSE 8000` in the Dockerfile).
   Copy the generated URL.
6. Wait for the first build. It takes several minutes — the image bakes the embedding
   and cross-encoder models in so cold starts never hit Hugging Face.
7. Verify:

   ```bash
   curl https://<your-app>.up.railway.app/api/health
   ```

   Expect `200` with a JSON body. If the deploy is stuck "waiting for healthcheck",
   check the deploy logs for a model-download or index-missing error.

---

## Step 3 — Deploy the frontend (Vercel)

1. Sign in at [vercel.com](https://vercel.com) with GitHub.
2. **Add New → Project** → import this repository.
3. In the import screen:
   - **Root Directory**: `frontend` — and tick **Include files outside the root
     directory** off (nothing outside `frontend/` is needed).
   - **Framework Preset**: Next.js (auto-detected). Leave build/output settings alone.
4. **Environment Variables** — add before the first build:

   | Variable | Environments | Value |
   |----------|--------------|-------|
   | `CHAT_API_URL` | Production, Preview | The Railway URL from Step 2 |

   This is server-only (used by the `/api/chat` route handler), so it is deliberately
   *not* `NEXT_PUBLIC_`.
5. **Deploy**. Copy the production URL.
6. **Settings → Git → Ignored Build Step**: choose *"Only build if there are changes in
   the Root Directory"* (or the command `git diff --quiet HEAD^ HEAD -- .`), so
   backend-only pushes don't burn build minutes.

---

## Step 4 — Close the CORS loop

Back in Railway → **Variables**, set `ALLOWED_ORIGINS` to the Vercel production URL
(no trailing slash, comma-separated if you add a custom domain later):

```
ALLOWED_ORIGINS=https://your-site.vercel.app
```

Saving a variable triggers a redeploy. Once it's live, open the site and send a message
in the chatbot — if the request fails with a CORS error in the browser console,
`ALLOWED_ORIGINS` doesn't match the origin exactly.

---

## Everyday deploys

Push to `main` (directly or by merging a PR):

- Vercel builds `frontend/` and promotes it to production; PRs get an automatic
  **preview deployment** with the URL commented on the PR by Vercel's GitHub app.
- Railway rebuilds the backend image only if files under `backend/**` changed.

Both platforms support rollback from their dashboards: Vercel → Deployments →
*Promote to Production* on an earlier build; Railway → Deployments → *Redeploy* on an
earlier one.

To force a redeploy without a code change: Vercel → Deployments → *Redeploy*;
Railway → *Deploy* on the service (or just save a variable).

## Optional: gate deploys behind CI

The platforms deploy on push regardless of CI status. To make CI actually blocking,
protect `main` in GitHub → **Settings → Branches → Add rule**:

- Require a pull request before merging
- Require status checks to pass: `Lint, format & types`, `Unit tests`,
  `Production build`, `Ruff lint & format`, `Pytest`, `Lighthouse CI`,
  `CodeQL (javascript-typescript)`, `CodeQL (python)`, `npm audit (frontend)`,
  `pip-audit (backend)`

Then nothing reaches `main` — and therefore neither platform — without green CI.

## Cold start handling

Railway's free tier sleeps services after inactivity (~30–60s cold start). Options:

- **Accept it** — the frontend shows a loading state while the backend wakes up
- **Keep-warm pings** — use [UptimeRobot](https://uptimerobot.com) (free) to ping
  `GET /api/health` every 5 minutes during business hours

## Local environment

Create `backend/.env`:

```
GROQ_API_KEY=your_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

And `frontend/.env.local`:

```
CHAT_API_URL=http://localhost:8000
```

## Checklist

- [ ] `make build-index` run and `backend/indexes/` committed
- [ ] Railway project created from the GitHub repo; root directory `backend`, watch paths `backend/**`, healthcheck `/api/health` with a 300s timeout
- [ ] `GROQ_API_KEY` set in Railway; public domain generated
- [ ] `/api/health` returns 200 on the Railway URL
- [ ] Vercel project imported; root directory `frontend`
- [ ] `CHAT_API_URL` set in Vercel (Production + Preview) to the Railway URL
- [ ] `ALLOWED_ORIGINS` in Railway set to the Vercel production URL
- [ ] Chatbot tested end-to-end in production
- [ ] (Optional) Branch protection on `main` requiring the CI checks
- [ ] (Optional) UptimeRobot keep-warm monitor configured
