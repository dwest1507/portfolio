# Deployment

## Overview

| Service | Platform | Free Tier |
|---------|----------|-----------|
| Frontend | Vercel | 100 GB bandwidth, 6,000 build min/month |
| Backend | Railway | 500 execution hours/month |
| LLM | Groq | 14,400 requests/day, 30 req/min |
| Analytics | Vercel Analytics | 2,500 events/month |

Deploys are performed by GitHub Actions (`.github/workflows/deploy.yml`), **not** by the
Vercel/Railway git integrations — see [ci-cd.md](ci-cd.md). The steps below are the
one-time setup; after that, every push to `main` that passes CI deploys automatically.

## One-time setup: Vercel (frontend)

1. Create a Vercel account and install the Vercel CLI locally (`npm i -g vercel`)
2. From `frontend/`, run `vercel link` and create a new project when prompted
   - Do **not** connect the GitHub repo in the Vercel dashboard (Actions handles deploys)
3. Copy `orgId` and `projectId` from the generated `frontend/.vercel/project.json`
4. In the Vercel dashboard, add the production environment variable:

   | Variable | Value |
   |----------|-------|
   | `CHAT_API_URL` | Railway backend URL (e.g. `https://your-app.up.railway.app`) |

5. Create an access token (Account Settings → Tokens)
6. Add GitHub repo secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

## One-time setup: Railway (backend)

1. Create a Railway account and a new project with an **empty service**
   (no repo connection — Actions pushes the code with `railway up`)
2. The service builds from `backend/Dockerfile` automatically
   (`backend/railway.json` sets the builder, `/api/health` healthcheck, and restart policy)
3. Add service environment variables:

   | Variable | Value |
   |----------|-------|
   | `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
   | `ALLOWED_ORIGINS` | Vercel production URL (e.g. `https://your-site.vercel.app`) |

4. Generate a project token (Project Settings → Tokens) and add it as the GitHub repo
   secret `RAILWAY_TOKEN`
5. Add GitHub repo variables: `RAILWAY_SERVICE` (the service name) and `BACKEND_URL`
   (the public Railway URL, once known)
6. **Before deploying:** run `make build-index` locally and commit the generated index
   files in `backend/indexes/`. They are baked into the container image.

## First deploy

1. Merge/push to `main` (or run the **Deploy** workflow manually from the Actions tab)
2. The backend deploy waits for `/api/health` to return 200 (model loading can take a bit)
3. Once the Railway URL is live, confirm `CHAT_API_URL` in Vercel and `BACKEND_URL` in
   GitHub variables point at it, then redeploy the frontend if needed (manual dispatch)

## Cold start handling

Railway free tier sleeps services after inactivity (~30–60s cold start). Options:

- **Accept it** — the frontend shows a loading state while the backend wakes up
- **Keep-warm pings** — use [UptimeRobot](https://uptimerobot.com) (free) to ping
  `GET /api/health` every 5 minutes during business hours

## Local environment

Create `backend/.env`:

```
GROQ_API_KEY=your_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

The frontend reads `CHAT_API_URL` from `.env.local` in `frontend/`:

```
CHAT_API_URL=http://localhost:8000
```

## Checklist

- [ ] `make build-index` run and indexes committed
- [ ] Vercel project linked; `VERCEL_TOKEN` / `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID` GitHub secrets set
- [ ] Railway service created; `RAILWAY_TOKEN` secret and `RAILWAY_SERVICE` / `BACKEND_URL` variables set
- [ ] `GROQ_API_KEY` + `ALLOWED_ORIGINS` set in Railway
- [ ] `CHAT_API_URL` set to Railway URL in Vercel
- [ ] Deploy workflow green; smoke test and health check passed
- [ ] Chatbot end-to-end tested in production
- [ ] (Optional) UptimeRobot keep-warm monitor configured
