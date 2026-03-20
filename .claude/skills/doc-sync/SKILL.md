---
name: doc-sync
description: Keep project documentation in sync with code changes. Use when a feature is added, changed, or removed and documentation needs updating. Covers SPEC.md, README.md, and the docs/ directory.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Documentation Sync Skill

This project follows **spec-driven development**. Every code change must keep documentation in sync. This skill guides you through auditing and updating all relevant docs.

## Document Hierarchy

| File/Dir | Purpose | When to Update |
|----------|---------|----------------|
| `SPEC.md` | Single source of truth — requirements, architecture, API contracts, task list | Any new/changed/removed feature, endpoint, component, or behavior |
| `README.md` | Root entry point — quick start, project structure, dev commands, links to docs/ | Setup changes, new make targets, new docs/ pages |
| `docs/architecture.md` | System design, data flow, tech stack, API reference | Architecture changes, new endpoints, tech stack changes |
| `docs/chatbot-rag.md` | RAG pipeline — index build, runtime pipeline, models, rate limiting | Any change to the chat endpoint, RAG logic, models, or rate limits |
| `docs/design-system.md` | Cyberpunk design tokens, typography, animations, responsive strategy | Design token changes, new visual signatures, animation policy changes |
| `docs/deployment.md` | Vercel + Railway deploy steps, env vars, cold start handling | New env vars, deployment config changes, new services |
| `docs/testing.md` | Test coverage approach, how to run tests, test matrices | New test categories, changed test commands, coverage policy changes |

### docs/ vs README philosophy

- **`docs/`** is where the full story lives — detailed walkthroughs, configuration tables, edge cases, examples.
- **`README.md`** is the entry point — brief orientation + links into `docs/`. It should not duplicate what `docs/` already covers.
- When adding substantial detail, put it in `docs/` (create a new file if needed) and link to it from `README.md`.

## Workflow

### 1. Identify What Changed

```bash
# See all modified files since last commit
git diff --name-only HEAD

# Or compare to main
git diff --name-only main...HEAD
```

### 2. Determine Documentation Impact

| Changed Area | Check These Docs |
|---|---|
| New API endpoint | `SPEC.md` → API Routes section; `docs/architecture.md` → API Reference |
| Removed/renamed endpoint | `SPEC.md` → API Routes section; `docs/architecture.md` → API Reference |
| Rate limit change | `SPEC.md` → Rate Limiting; `docs/chatbot-rag.md` → Rate Limiting table |
| New env variable | `SPEC.md` → Environment Variables; `docs/deployment.md` → env var tables |
| New `make` target | `README.md` → Development section; `Makefile` |
| New component or page | `SPEC.md` → Pages & Components; `docs/architecture.md` → Frontend Structure |
| New backend module | `SPEC.md` → Architecture; `docs/architecture.md` → Backend Structure |
| RAG pipeline change | `SPEC.md` → AI Chatbot (RAG); `docs/chatbot-rag.md` |
| Model change | `SPEC.md` → RAG Pipeline; `docs/chatbot-rag.md` → Models Used table |
| Design token change | `SPEC.md` → Design System; `docs/design-system.md` |
| New test category or policy | `SPEC.md` → Testing; `docs/testing.md` |
| Deployment config change | `SPEC.md` → Deployment; `docs/deployment.md` |
| Architecture change | `SPEC.md` → Architecture; `docs/architecture.md` |
| Task completed | `SPEC.md` → Task List (mark `[x]`) |

### 3. Update SPEC.md First

SPEC.md is always updated **before or alongside** the implementation — never after.

Key sections to know:
- **Architecture diagram** — ASCII art near the top; update if data flow changes
- **API Routes** — both the Next.js proxy and the FastAPI endpoints
- **Pages & Components** — component tree and page descriptions
- **AI Chatbot (RAG)** — pipeline steps, models, rate limits, env vars
- **Deployment** — env var tables for Vercel and Railway
- **Task List** — mark tasks `[x]` as they are completed

### 4. Update docs/

For any changed area with a corresponding `docs/` file, update it with full detail. If the change introduces a new topic with enough depth to warrant its own page, create a new file in `docs/` and link to it from `README.md`.

### 5. Update README.md

Update only if: quick-start steps changed, a new `make` target was added, a new `docs/` file was created, or the project structure changed. Keep it brief — link to `docs/` rather than duplicating content.

### 6. Verify Consistency

```bash
# Check SPEC.md references endpoints that actually exist in routes
grep "POST /api\|GET /api" SPEC.md
grep "@router.post\|@router.get\|@app.post\|@app.get" backend/app/routes/*.py

# Check README make targets match the Makefile
grep "make " README.md
grep "^[a-z][a-z_-]*:" Makefile
```

## Rules

1. **SPEC.md is the source of truth** — if code and spec conflict, update one consciously. Never leave them out of sync.
2. **`docs/` holds the detail** — `README.md` links to `docs/`, it does not duplicate it.
3. **Mark tasks complete** — when a task in `SPEC.md § 13` is finished, mark it `[x]`.
4. **One commit, all docs** — documentation updates belong in the same commit as the code change that required them.

## Quick Checklist

Before marking a feature complete, verify:

- [ ] `SPEC.md` reflects the new/changed behavior
- [ ] Completed tasks in `SPEC.md` Task List are marked `[x]`
- [ ] All new endpoints appear in `SPEC.md` API Routes and `docs/architecture.md`
- [ ] All new env vars are documented in `SPEC.md` and `docs/deployment.md`
- [ ] Relevant `docs/` file is updated (or a new one created) with full detail
- [ ] `README.md` links to any new `docs/` files; no detail duplicated from `docs/`
- [ ] No references to deleted endpoints, components, or files remain in any doc
