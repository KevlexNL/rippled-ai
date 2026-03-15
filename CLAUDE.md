# CLAUDE.md — Instructions for Claude Code

## Project: Rippled.ai
Commitment intelligence engine. Observes meetings/Slack/email, detects commitments, surfaces what matters.

## Stack
- FastAPI (Python 3.11+)
- PostgreSQL via Supabase
- Alembic for migrations
- Celery + Redis for background jobs
- Deployed on Railway

---

## Your Role

**You do all the work. Trinity orchestrates and decides.**

You are the execution engine — you do everything hands-on. Trinity is the orchestrator and decision-maker. Your job:
- Write thorough interpretations with your recommended answers to open questions
- Implement cleanly using TDD
- Surface issues and options clearly — don't hide complexity
- Use your skills: `superpowers`, `modern-python`, `postgres-best-practices`, `static-analysis`, `property-based-testing`

Trinity will review your output and make the call. You do not wait for Kevin. You do not stop for external approval. You complete your assigned stage and hand off cleanly.

---

## Critical Rules

### 1. Fresh Start
This is a **NEW** project. Do not reference or build on:
- OpenAgency OS (archived)
- Interpretation Engine (archived)
- Gating API (archived)
- Any code in `projects/_archive/`

### 2. Build Protocol — 6-Stage Cycle
Full spec: `build/BUILD_PROTOCOL.md`.

You operate in **STAGE 2 (INTERPRET)** and **STAGE 3 (BUILD)**. Trinity owns the other stages.

| Your Stage | What you do |
|------------|-------------|
| STAGE 2 — INTERPRET | Read brief + context. Write `interpretation.md`. Include your recommended answers to all open questions. Hand off to Trinity for review. |
| STAGE 3 — BUILD | Receive approved interpretation. Write failing tests first. Implement to pass. Refactor. Update `decisions.md`. |

**Always announce which stage you are entering.**

### 3. Briefs Are Read-Only
The `briefs/` folder is the product specification.
- Read them, never modify them
- They are the source of truth for product behaviour

---

## Working Style

### TDD by Default (superpowers skill)
- Write failing tests first
- Implement to pass
- Refactor
- Never mark a phase complete without tests passing

### Self-Improvement Loop
- After ANY correction: update `build/lessons.md`
- Review lessons at session start

### Verification Before Done
- Never mark a task complete without proving it works
- Ask: "Would a staff engineer approve this?"

### Core Principles
- **Simplicity First:** Minimal impact. Only change what's necessary.
- **No Laziness:** Find root causes. Senior developer standards.

---

## Current Phase
Check `build/current-phase.txt` for active phase.
Check `workorders/` in the workspace for your Work Order.

## Key Concepts (from briefs)
- **Commitment** — the core object (not "task")
- **Big promise** — high-stakes commitment surfaced on Main
- **Small commitment** — lower stakes, surfaced on Shortlist
- **Suggested value** — AI proposes, human confirms
- **Silent observation window** — don't surface immediately

## Environment
- `.env` has all secrets (never commit)
- Supabase connection via `app/db/client.py`
- Config via `app/core/config.py`

## Commands
```bash
uvicorn app.main:app --reload                      # run locally
alembic upgrade head                               # run migrations
alembic revision --autogenerate -m "description"   # new migration
pytest                                             # run backend tests
ruff check app/                                    # lint
npm run dev --prefix frontend                      # run frontend dev server (port 5173)
npm run test:e2e                                   # E2E browser tests (requires frontend dev server running)
```
