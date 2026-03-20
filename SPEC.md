# Portfolio Website Specification

> **Owner:** David West
> **Status:** Draft
> **Created:** 2026-03-18
> **Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4, Vercel + Python FastAPI (Railway)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Success Criteria](#2-goals--success-criteria)
3. [Architecture](#3-architecture)
4. [Design System](#4-design-system)
5. [Pages & Components](#5-pages--components)
6. [AI Chatbot (RAG)](#6-ai-chatbot-rag)
7. [Project Data Model](#7-project-data-model)
8. [API Routes](#8-api-routes)
9. [SEO & Metadata](#9-seo--metadata)
10. [Analytics](#10-analytics)
11. [Deployment](#11-deployment)
12. [Testing](#12-testing)
13. [Task List](#13-task-list)

---

## 1. Overview

A modern portfolio website for David West, an AI Engineer with 5+ years of data science and AI experience and 8+ years in the defense industry. The site showcases 4 portfolio projects and includes an AI-powered chatbot that recruiters can use to ask questions about David's qualifications. The chatbot uses a Python FastAPI backend with a full RAG pipeline (FAISS + BM25 hybrid search, cross-encoder re-ranking) and Groq for LLM inference.

### What This Is

- A personal portfolio that positions David as an AI Engineer, with light mention of prior defense industry experience
- A recruiter-facing tool with an AI chatbot for Q&A about qualifications
- A showcase of 4 projects with filterable cards and detailed write-up pages (MDX)

### What This Is Not

- A blog or CMS
- A full SaaS application — no user accounts, no database beyond the RAG vector store, no persistent state

---

## 2. Goals & Success Criteria

| Goal | Metric |
|------|--------|
| Position David as an AI Engineer | Title, bio, and project framing all emphasize AI engineering |
| Demonstrate technical skill | The portfolio site itself is a demonstration (Next.js, FastAPI, RAG chatbot, modern stack) |
| Enable recruiter engagement | Chatbot answers questions about qualifications within 2 seconds |
| Modern, polished appearance | Cyberpunk/glitch dark design, responsive, accessible, fast (Lighthouse > 90) |
| Minimize cost | All services on free tiers (Vercel, Railway, Groq) |

---

## 3. Architecture

```
Browser → Next.js (Vercel)                    Python FastAPI (Railway)
            ├── Static pages (SSG)              ├── POST /api/chat
            │   ├── Home (hero, projects,       │     ├── Embed query (sentence-transformers)
            │   │   about, contact)             │     ├── Hybrid search (FAISS + BM25)
            │   └── Project detail pages (MDX)  │     ├── Cross-encoder re-ranking
            ├── /api/chat (proxy) ────────────→ │     ├── Prompt construction
            │     (forwards to FastAPI)         │     └── Groq LLM (streaming)
            └── Static assets                   ├── FAISS index (pre-built, loaded at startup)
                (images, fonts)                 └── Rate limiting (in-memory + Groq backstop)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend Framework | Next.js 15 (App Router) |
| Language (Frontend) | TypeScript |
| Styling | Tailwind CSS v4 |
| Project Content | MDX (via `@next/mdx` or `next-mdx-remote`) |
| Backend Framework | Python FastAPI |
| RAG Pipeline | FAISS + BM25 (hybrid search), sentence-transformers, cross-encoder re-ranking |
| LLM API | Groq (free tier) |
| Streaming | Vercel AI SDK (`ai` package) for client-side streaming hooks |
| Frontend Deployment | Vercel (free tier) |
| Backend Deployment | Railway (free tier, 500 hrs/month) |
| Frontend Testing | Vitest + React Testing Library |
| Backend Testing | pytest |
| Linting | ESLint + Prettier (frontend), Ruff (backend) |
| Analytics | Vercel Analytics (free tier) |

### Key Decisions

- **Separate Python backend.** The RAG pipeline uses FAISS, sentence-transformers, and cross-encoder re-ranking — all Python-native ML libraries. A separate FastAPI service avoids serverless cold-start issues with large ML models and enables proper server-side rate limiting. This also demonstrates backend engineering skills.
- **Groq for LLM.** David has a free Groq account and two projects built on Groq. Using it here reinforces his experience with the platform.
- **MDX for project detail content.** Project write-ups include code blocks, images, and structured sections. MDX is the standard approach for rich content in Next.js.
- **SSG for all frontend pages.** The Next.js app is entirely static except for the `/api/chat` proxy route. Project data and MDX content are defined in code, not fetched at runtime.
- **Vercel AI SDK for streaming.** Provides React hooks (`useChat`), handles SSE parsing, message state management, and abort handling out of the box.
- **No light mode.** The cyberpunk design system is dark-only. No theme toggle needed.

---

## 4. Design System

The site uses a **Cyberpunk / Glitch** design system. The full design token reference is defined in `.claude/skills/ui-design/SKILL.md` and should be treated as the authoritative source for all visual decisions. Below is a summary of the key elements.

### Design Philosophy

**"High-Tech, Low-Life."** The aesthetic is a digital dystopia — neon-drenched, gritty, imperfect, and aggressively futuristic-retro. The interface should feel alive and volatile, like a hacked terminal or forbidden interface. Draw from the visual language of Blade Runner, Akira, The Matrix, and Ghost in the Shell.

### Color Palette (Dark Mode Only)

| Token | Role | Value |
|-------|------|-------|
| `background` | Page background (void black) | `#0a0a0f` |
| `foreground` | Primary text | `#e0e0e0` |
| `card` | Card background | `#12121a` |
| `muted` | Elevated UI backgrounds | `#1c1c2e` |
| `mutedForeground` | Secondary text | `#6b7280` |
| `accent` | Primary neon (electric green) | `#00ff88` |
| `accentSecondary` | Secondary neon (hot magenta) | `#ff00ff` |
| `accentTertiary` | Tertiary neon (cyan) | `#00d4ff` |
| `border` | Subtle borders | `#2a2a3a` |
| `destructive` | Error/danger | `#ff3366` |

### Typography

- **Headings:** `"Orbitron", "Share Tech Mono", monospace` — geometric, futuristic
- **Body:** `"JetBrains Mono", "Fira Code", "Consolas", monospace` — terminal feel
- **Accent/Labels:** `"Share Tech Mono", monospace` — UI labels, timestamps, badges

### Visual Signatures

1. **Chromatic Aberration** — RGB color splitting on hero text (magenta/cyan offset shadows)
2. **Scanlines Overlay** — Subtle horizontal lines mimicking CRT refresh, applied full-page
3. **Glitch Effects** — Intentional clip-path animations, skewed transforms, flickering text
4. **Neon Glow** — Multi-layered box-shadow/text-shadow stacking on borders and text
5. **Corner Cuts** — Chamfered/clipped corners via `clip-path` instead of `border-radius`
6. **Circuit Patterns** — Decorative SVG/CSS grid backgrounds resembling PCB traces

### Layout Strategy

- `max-w-7xl` for main content, full-bleed sections with contained inner content
- 8px base grid, generous padding (`py-24` to `py-32` for sections)
- Asymmetric layouts: hero uses 60/40 split, at least one section with overlapping elements
- Subtle `rotate-1` or `skew-y-1` transforms on section containers

### Animations

- **Motion feel:** Sharp, digital, slightly mechanical. Quick snaps rather than smooth eases
- **Transitions:** `all 150ms cubic-bezier(0.4, 0, 0.2, 1)` or `all 100ms steps(4)` for digital feel
- **Glitched headlines:** Hero h1 has chromatic aberration + occasional glitch animation
- **Blinking cursors:** `animation: blink 1s step-end infinite`
- **Neon glow on hover:** Border and shadow transitions
- **Chatbot widget:** Slide-up open, slide-down close
- **Respect `prefers-reduced-motion`:** Disable glitch animations, keep static chromatic aberration

### Responsive Strategy

- Mobile-first breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px)
- Typography scales: Hero h1 `text-5xl` → `text-7xl` → `text-8xl`
- Grids: 1 column (mobile) → 2 columns (md) → 3 columns (lg)
- Minimum 44px touch targets on all interactive elements
- Maintain scanlines, chamfered corners, neon glows, and monospace on all sizes

### Accessibility

- WCAG 2.1 AA contrast ratios (accent green on dark bg = 7.5:1 — excellent)
- Focus-visible outlines with neon glow aesthetic
- Semantic HTML throughout
- `prefers-reduced-motion` respected for all animations

---

## 5. Pages & Components

### 5.1 Layout

```
<RootLayout>
  <Header />          — sticky top nav with name, nav links (no theme toggle — dark only)
  <main>{children}</main>
  <Footer />          — email link, LinkedIn link, copyright
  <ChatbotWidget />   — floating button (bottom-right), expands to chat panel
</RootLayout>
```

### 5.2 Home Page (`/`)

Sections rendered in order:

#### Hero Section
- Name: "David West"
- Title: "AI Engineer"
- One-liner tagline (e.g., "Building intelligent systems at the intersection of AI and software engineering")
- CTA button: "View My Work" (scrolls to projects) — use glitch button variant
- Background: Circuit grid pattern + gradient mesh with neon accent colors at low opacity
- Glitched headline with chromatic aberration effect
- Typewriter effect or trailing cursor on subtitle

#### Projects Section
- **Filter bar:** Horizontal row of tech stack tags (e.g., "All", "Python", "Next.js", "Groq", "LLM/RAG", "Streamlit", "AWS"). Clicking a tag filters the project cards. "All" is default.
- **Project cards grid:** 2 columns on desktop, 1 on mobile. Each card uses the cyberpunk card variant:
  - Chamfered corners via clip-path
  - Project thumbnail/screenshot
  - Project title
  - Short description (1-2 sentences)
  - Tech stack tags (neon pill badges)
  - Link to live app (external)
  - Link to detail page (internal)
  - Hover: translateY(-1px), border becomes accent, neon glow

#### About Section
- Brief bio (3-4 sentences) emphasizing AI engineering experience, with light mention of defense industry background
- Key skills displayed as categorized tag groups (e.g., Languages, Frameworks, Cloud, AI/ML)
- Terminal variant card styling for the skills section
- Link to LinkedIn

#### Contact Section
- Simple: "Get in touch" with email link and LinkedIn link
- No contact form
- Terminal aesthetic with `>` prefix

### 5.3 Project Detail Pages (`/projects/[slug]`)

One page per project, statically generated from MDX files. Each page contains:

- **Header:** Project title, short description, tech tags
- **Links:** Live app button, GitHub repo button
- **Overview:** 2-3 paragraph write-up of what the project does and why it was built
- **Architecture/Technical Details:** How it works, key technical decisions, diagrams if applicable
- **Screenshots/Demo:** Images or embedded content showing the project in action
- **Learnings:** What David learned or what the project demonstrates about his skills
- Back link to home page projects section

**Diamonds project (special case):** The detail page contains a written summary highlighting key findings and growth narrative. The original R notebook HTML is hosted as a static asset and linked from the detail page ("View Original Analysis" button), but is not embedded.

### 5.4 Component Tree

```
components/
├── layout/
│   ├── Header.tsx          — logo, nav links
│   ├── Footer.tsx          — email, LinkedIn, copyright
│   ├── Section.tsx         — reusable section wrapper with fade-in
│   └── ScanlineOverlay.tsx — full-page CRT scanline effect
├── home/
│   ├── Hero.tsx            — hero section with glitch effects
│   ├── ProjectsSection.tsx — filter bar + project grid
│   ├── ProjectCard.tsx     — individual project card (cyberpunk style)
│   ├── FilterBar.tsx       — tech stack tag filters
│   ├── AboutSection.tsx    — bio + skills
│   └── ContactSection.tsx  — email/LinkedIn links
├── projects/
│   └── ProjectDetail.tsx   — full project write-up layout (renders MDX)
├── chatbot/
│   ├── ChatbotWidget.tsx   — floating button + expandable panel
│   ├── ChatMessage.tsx     — single message bubble
│   └── ChatInput.tsx       — text input + send button (terminal style)
└── ui/
    ├── Button.tsx          — styled button variants (default, secondary, outline, ghost, glitch)
    ├── Tag.tsx             — tech stack pill/badge (neon glow)
    ├── Card.tsx            — card variants (default, terminal, holographic)
    └── Icon.tsx            — icon wrapper (lucide-react, thin stroke)
```

---

## 6. AI Chatbot (RAG)

### User Experience

- Floating circle button in the bottom-right corner with a chat icon (neon glow)
- Clicking opens a chat panel (~400px wide, ~500px tall on desktop; full-width on mobile)
- Terminal-style input with `>` prefix
- Welcome message: "Hi! I'm David's AI assistant. Ask me anything about his experience, skills, or projects."
- User types a question, gets a streamed response
- **Loading state:** Typing indicator (blinking cursor animation) while waiting for first token
- **Error state:** User-friendly message ("Sorry, I'm having trouble responding right now. Please try again.") on API failure. Does not expose raw error details.
- **Timeout handling:** If response is truncated due to timeout, append "..." rather than cutting mid-word
- Chat history persists for the browser session (cleared on tab close)
- Max 50 messages per session (client-side enforced)

### RAG Pipeline (Python FastAPI Backend)

#### Build Time (Pre-processing)

1. **Input:** David's resume (`resume.txt`) + project descriptions (from MDX content or project data)
2. **Chunking:** Split resume into ~200-300 token chunks with overlap. Project descriptions become their own chunks. Use paragraph-based splitting to preserve complete thoughts.
3. **Embedding:** Use `sentence-transformers` (`all-mpnet-base-v2`) to generate embeddings for each chunk
4. **Indexing:** Build a FAISS index + BM25 index from the chunks
5. **Output:** FAISS index files + pickled BM25 index + chunks JSON, committed to the backend repo

#### Runtime (FastAPI Endpoint)

`POST /api/chat`

1. **Receive:** User message + conversation history (last 10 messages for context)
2. **Embed query:** Generate embedding for the user's question using `sentence-transformers` (`all-mpnet-base-v2`)
3. **Hybrid search:** 70% semantic (FAISS) + 30% keyword (BM25), retrieve top candidates
4. **Cross-encoder re-ranking:** Re-rank retrieved passages using `ms-marco-MiniLM-L-6-v2` for final top 5 chunks
5. **Prompt construction:**
   ```
   System: You are David West's AI assistant on his portfolio website.
   Answer questions about David's experience, skills, and projects using
   ONLY the provided context. If the context doesn't contain the answer,
   say so honestly. Be concise and professional. Do not make up information.

   Context:
   {top 5 re-ranked chunks joined by newlines}

   Conversation history:
   {last 10 messages}
   ```
6. **Generate:** Call Groq API (`llama-3.3-70b-versatile` or latest available model) with streaming enabled
7. **Stream:** Return response as a streamed text response (SSE)

#### Next.js Proxy Route

The Next.js app has a thin `/api/chat` route that proxies requests to the FastAPI backend. This avoids CORS issues and keeps the backend URL private.

```typescript
// app/api/chat/route.ts — proxies to FastAPI backend
// Uses Vercel AI SDK streamText or similar for client integration
```

#### Rate Limiting

- **Client-side:** 50 messages per session, 1 message per 3 seconds (debounce)
- **Server-side (FastAPI):** In-memory rate limiting per IP (e.g., `slowapi`). Limits: 30 requests/minute per IP.
- **Backstop:** Groq's own rate limits (14,400 requests/day, 30 requests/minute on free tier)

#### Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | FastAPI (Railway) | Groq API key |
| `CHAT_API_URL` | Next.js (Vercel) | URL of the FastAPI backend |
| `ALLOWED_ORIGINS` | FastAPI (Railway) | CORS allowed origins (Vercel URL) |

---

## 7. Project Data Model

Projects are defined as a TypeScript array in `data/projects.ts` for metadata (slug, title, tags, URLs). Detailed content lives in MDX files under `content/projects/`.

```typescript
interface Project {
  slug: string;              // URL-friendly identifier
  title: string;             // Display name
  shortDescription: string;  // 1-2 sentences for the card
  thumbnail: string;         // Path to thumbnail image in /public
  tags: string[];            // Tech stack tags for filtering
  liveUrl: string;           // Link to deployed app
  repoUrl: string;           // Link to GitHub repo
  featured: boolean;         // For future use (e.g., highlight top projects)
  year: number;              // Year built, for ordering or context
}
```

> **Note:** `longDescription` has been removed from the interface. Detailed content is authored in MDX files at `content/projects/{slug}.mdx`.

### Projects

| # | Slug | Title | Tags | Live URL |
|---|------|-------|------|----------|
| 1 | `ai-music-gen` | Generate Music with AI | `Next.js`, `TypeScript`, `FastAPI`, `Python`, `Modal`, `Groq`, `LLM` | ai-music-gen.vercel.app |
| 2 | `nietzsche-chat` | Chat with Friedrich Nietzsche | `Streamlit`, `Python`, `Groq`, `LLM/RAG`, `LangChain`, `FAISS` | nietzsche-chat.streamlit.app |
| 3 | `baby-names` | Baby Name Popularity | `Streamlit`, `Python`, `Pandas`, `Scikit-Learn`, `XGBoost`, `Data Visualization` | baby-names-app-*.streamlit.app |
| 4 | `diamonds-price` | Diamonds: Predicting Price | `R`, `Scikit-Learn`, `Jupyter`, `Data Science` | (static HTML hosted on site) |

> **Note:** Tags in the table above are approximate. Finalize during implementation based on the actual tech stacks. The filter bar should show the union of all tags across projects.

### Project Detail Content (MDX)

Each project has an MDX file at `content/projects/{slug}.mdx` with structured sections:

- **Overview:** What the project does (user-facing description)
- **Motivation:** Why it was built (personal interest, problem it solves)
- **Architecture:** How it works (tech decisions, system diagram)
- **Skills Demonstrated:** What it shows about David's capabilities (relevant to AI engineering roles)

Initial drafts will be generated from each project's existing documentation and edited by David.

### Diamonds Project (Special Handling)

The diamonds project detail page includes a written summary of the analysis on the MDX page. The original R notebook HTML (~12.6MB) is hosted as a static asset in `/public/projects/diamonds-predicting-price.html` and linked via a "View Original Analysis" button. It is NOT embedded or iframed due to its size.

---

## 8. API Routes

### Frontend (Next.js)

#### `POST /api/chat` (Proxy)

Proxies chat requests from the browser to the FastAPI backend. Streams the response back to the client.

**Request:**
```json
{
  "message": "What experience does David have with LLMs?",
  "history": [
    { "role": "user", "content": "Tell me about David" },
    { "role": "assistant", "content": "David is an AI Engineer..." }
  ]
}
```

**Response:** Streamed text (SSE via Vercel AI SDK)

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | Empty message or message > 500 characters |
| 429 | Rate limit exceeded |
| 502 | Backend unavailable |
| 500 | Unexpected error |

### Backend (FastAPI)

#### `POST /api/chat`

The main RAG endpoint. See §6 for full pipeline details.

#### `GET /api/health`

Health check endpoint for monitoring and keep-warm pings.

**Response:** `{ "status": "ok" }`

---

## 9. SEO & Metadata

Every page should have proper metadata using Next.js App Router's built-in `metadata` export.

### Per-Page Metadata

| Page | Title | Description |
|------|-------|-------------|
| Home (`/`) | "David West — AI Engineer" | "AI Engineer with 5+ years of experience building intelligent systems. View projects and ask my AI assistant about my qualifications." |
| Project Detail | "{Project Title} — David West" | `{shortDescription}` from project data |

### Open Graph / Social Cards

All pages include Open Graph and Twitter Card metadata so links shared on LinkedIn, Slack, etc. render a proper preview card:

```typescript
export const metadata: Metadata = {
  openGraph: {
    title: "David West — AI Engineer",
    description: "...",
    type: "website",
    images: ["/og-image.png"],  // 1200x630 OG image
  },
  twitter: {
    card: "summary_large_image",
  },
};
```

A default OG image (`/public/og-image.png`, 1200x630) should be created matching the site's cyberpunk aesthetic.

---

## 10. Analytics

### Vercel Analytics (Free Tier)

Vercel Analytics is integrated for page view tracking with zero configuration overhead.

**Setup:**
```bash
npm install @vercel/analytics
```

```typescript
// app/layout.tsx
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

**What it tracks:**
- Page views and unique visitors
- Top pages and referrers
- Device and browser breakdown

**Free tier limits:** 2,500 events/month (sufficient for a portfolio site).

**No additional analytics tools.** Keep costs at zero.

---

## 11. Deployment

### Frontend: Vercel (Free Tier)

| Resource | Free Tier Limit | Expected Usage |
|----------|----------------|----------------|
| Bandwidth | 100 GB/month | Well under limit |
| Serverless Functions | 100 GB-hrs/month | Minimal — only `/api/chat` proxy |
| Builds | 6,000 min/month | ~2-3 min per build |
| Analytics | 2,500 events/month | Sufficient for portfolio traffic |

### Backend: Railway (Free Tier)

| Resource | Free Tier Limit | Expected Usage |
|----------|----------------|----------------|
| Execution | 500 hours/month | ~720 hrs if always on; use sleep-on-idle |
| Memory | 512 MB | FAISS index + models should fit |
| Networking | Outbound included | Groq API calls only |

**Cold start mitigation:** Railway free tier sleeps after inactivity. Options:
1. Accept the ~30-60s cold start on first chatbot message (show a loading state)
2. Use an external uptime monitor (e.g., UptimeRobot free tier) to ping `/api/health` every 5 minutes during business hours

### Environment Variables

**Vercel Dashboard:**
| Variable | Value |
|----------|-------|
| `CHAT_API_URL` | Railway backend URL |

**Railway Dashboard:**
| Variable | Value |
|----------|-------|
| `GROQ_API_KEY` | (from Groq dashboard) |
| `ALLOWED_ORIGINS` | Vercel production URL |

### Build & Deploy

**Frontend (Vercel):**
- Build command: `next build`
- Output: Hybrid — static pages (SSG) + one serverless function (`/api/chat` proxy)
- Node.js version: 20.x
- Auto-deploy: Push to `main` triggers production deploy
- Preview: Push to any other branch creates a preview deployment

**Backend (Railway):**
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Python version: 3.11+
- Auto-deploy: Push to `main` triggers production deploy
- Pre-processing: Run `python scripts/build_index.py` locally before deploying to generate FAISS/BM25 indexes

---

## 12. Testing

### Coverage Approach: Meaningful Coverage

Focus testing effort on business logic, interactive components, and API behavior. Skip snapshot-testing static layout components that have no conditional logic.

### Frontend Tests (Vitest + React Testing Library)

| Priority | Area | What to Test |
|----------|------|-------------|
| High | `FilterBar` | Filters update, "All" resets, active state |
| High | `ProjectsSection` | Filtering logic — correct cards shown/hidden |
| High | `ChatbotWidget` | Open/close toggle, message display, input handling, error states |
| High | `ChatInput` | Debounce, message limit enforcement, empty input prevention |
| Medium | `ProjectCard` | Renders title, description, tags, links |
| Medium | `ChatMessage` | Renders user vs assistant messages correctly |
| Low | `Header` | Nav links render, mobile menu works |

### Backend Tests (pytest)

| Priority | Area | What to Test |
|----------|------|-------------|
| High | `POST /api/chat` | Valid request returns streamed response |
| High | `POST /api/chat` | Empty message returns 400 |
| High | `POST /api/chat` | Long message (>500 chars) returns 400 |
| High | `POST /api/chat` | Groq API error returns 500 with safe message |
| High | RAG pipeline | Hybrid search returns relevant chunks |
| High | RAG pipeline | Cross-encoder re-ranking improves result order |
| High | RAG pipeline | Prompt construction includes context and history |
| Medium | Rate limiting | Exceeding rate limit returns 429 |
| Medium | Chunking | Produces correct chunk sizes with overlap |
| Medium | Health check | `GET /api/health` returns 200 |

### Running Tests

```bash
# Frontend
cd frontend  # (or root if monorepo)
npm test              # Run all tests
npm run test:watch    # Watch mode
npm run test:coverage # Coverage report

# Backend
cd backend
pytest tests/ -v               # Run all tests
pytest tests/ -v --cov=app     # With coverage
```

---

## 13. Task List

### Phase 1: Project Setup

- [x] Initialize Next.js 15 project with TypeScript and Tailwind CSS v4
- [x] Configure ESLint, Prettier, Vitest
- [x] Set up project structure (directories per §5.4)
- [x] Set up MDX support (`@next/mdx` or `next-mdx-remote`)
- [x] Define cyberpunk design tokens (CSS variables from §4)
- [x] Create base layout (`RootLayout`, `Header`, `Footer`, `ScanlineOverlay`)
- [x] Implement cyberpunk global styles (scanlines, circuit grid background, fonts)
- [x] Set up Vercel Analytics

### Phase 2: Home Page

- [X] Build `Hero` section with glitch effects, chromatic aberration, typewriter subtitle
- [X] Define project data model in `data/projects.ts` with all 4 projects
- [X] Build `ProjectCard` component (cyberpunk card with chamfered corners)
- [X] Build `FilterBar` component with neon tag filters
- [X] Build `ProjectsSection` with filtering logic
- [X] Build `AboutSection` with bio and categorized skills (terminal variant)
- [X] Build `ContactSection` with email and LinkedIn links
- [X] Add scroll-based fade-in animations

### Phase 3: Project Detail Pages

- [X] Create `/projects/[slug]` dynamic route with `generateStaticParams`
- [X] Build `ProjectDetail` layout component (renders MDX)
- [X] Write MDX content for each project (overview, architecture, learnings)
- [X] Add project screenshots/images to `/public`
- [X] Host diamonds R notebook HTML as static asset, link from detail page
- [X] Link cards on home page to detail pages
- [X] Add SEO metadata to all pages (§9)

### Phase 4: AI Chatbot Backend (Python FastAPI)

- [x] Initialize FastAPI project with project structure
- [x] Build RAG pre-processing script (`scripts/build_index.py`):
  - [x] Chunk resume and project descriptions
  - [x] Generate embeddings with `sentence-transformers` (`all-mpnet-base-v2`)
  - [x] Build FAISS index + BM25 index
  - [x] Save indexes and chunks to disk
- [x] Implement `POST /api/chat` endpoint:
  - [x] Query embedding
  - [x] Hybrid search (FAISS 70% + BM25 30%)
  - [x] Cross-encoder re-ranking (`ms-marco-MiniLM-L-6-v2`)
  - [x] Prompt construction with context + history
  - [x] Groq API streaming response
- [x] Implement `GET /api/health` endpoint
- [x] Add rate limiting (`slowapi`, 30 req/min per IP)
- [x] Add CORS configuration
- [x] Write backend tests

### Phase 5: AI Chatbot Frontend

- [x] Build Next.js `/api/chat` proxy route
- [x] Build `ChatbotWidget` (floating button with neon glow, expandable panel)
- [x] Build `ChatMessage` and `ChatInput` components (terminal style)
- [x] Implement client-side streaming display (Vercel AI SDK `useChat`)
- [x] Add loading state (typing indicator with blinking cursor)
- [x] Add error state (user-friendly message on failure)
- [x] Add timeout handling (append "..." on truncation)
- [x] Add session message limit (50) and input debounce (3s)

### Phase 6: Polish & Testing

- [ ] Write frontend tests for interactive components (§12)
- [ ] Responsive testing across breakpoints
- [ ] Lighthouse audit — target > 90 on all categories
- [ ] Accessibility audit (contrast, focus, semantics, reduced-motion)
- [ ] Final content review (bio, project descriptions, chatbot system prompt)

### Phase 7: Deploy

- [ ] Deploy FastAPI backend to Railway
- [ ] Set Railway environment variables (`GROQ_API_KEY`, `ALLOWED_ORIGINS`)
- [ ] Connect Next.js repo to Vercel
- [ ] Set Vercel environment variables (`CHAT_API_URL`)
- [ ] Verify production build, static pages, and chatbot functionality
- [ ] (Optional) Set up uptime monitor for Railway keep-warm pings
