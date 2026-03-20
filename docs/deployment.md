# Deployment

## Overview

| Service | Platform | Free Tier |
|---------|----------|-----------|
| Frontend | Vercel | 100 GB bandwidth, 6,000 build min/month |
| Backend | Railway | 500 execution hours/month |
| LLM | Groq | 14,400 requests/day, 30 req/min |
| Analytics | Vercel Analytics | 2,500 events/month |

## Frontend (Vercel)

1. Connect the repo to Vercel (import from GitHub)
2. Set build settings:
   - **Root directory:** `frontend`
   - **Build command:** `next build`
   - **Node.js version:** 20.x
3. Add environment variable:

   | Variable | Value |
   |----------|-------|
   | `CHAT_API_URL` | Railway backend URL (e.g. `https://your-app.railway.app`) |

4. Push to `main` to trigger a production deploy. Any other branch creates a preview deployment.

## Backend (Railway)

1. Create a new Railway project, add a service from the repo
2. Set service settings:
   - **Root directory:** `backend`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Python version:** 3.11+
3. Add environment variables:

   | Variable | Value |
   |----------|-------|
   | `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
   | `ALLOWED_ORIGINS` | Vercel production URL (e.g. `https://your-site.vercel.app`) |

4. **Before deploying:** run `make build-index` locally and commit the generated index files in `backend/indexes/`. They are loaded at startup.

## Cold Start Handling

Railway free tier sleeps services after inactivity (~30–60s cold start). Options:

- **Accept it** — the frontend shows a loading state while the backend wakes up
- **Keep-warm pings** — use [UptimeRobot](https://uptimerobot.com) (free) to ping `GET /api/health` every 5 minutes during business hours

## Local Environment

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
- [ ] `GROQ_API_KEY` set in Railway
- [ ] `ALLOWED_ORIGINS` set to Vercel production URL in Railway
- [ ] `CHAT_API_URL` set to Railway URL in Vercel
- [ ] Production build verified (`next build` passes)
- [ ] Chatbot end-to-end tested in production
- [ ] (Optional) UptimeRobot keep-warm monitor configured
