# CLAUDE.md — Instructions for Claude Code

## Project: Rippled.ai
Commitment intelligence engine. Observes meetings/Slack/email, detects commitments, surfaces what matters.

## Stack
- FastAPI (Python 3.11+)
- PostgreSQL via Supabase
- Alembic for migrations
- Celery + Redis for background jobs
- Deployed on Railway

## Critical Rules

### 1. Fresh Start
This is a **NEW** project. Do not reference or build on:
- OpenAgency OS (archived)
- Interpretation Engine (archived)
- Gating API (archived)
- Any code in `projects/_archive/`

### 2. Build Protocol
Follow `build/BUILD_PROTOCOL.md` strictly:
- Read ONLY files listed in your Work Order
- Write interpretation FIRST, then STOP
- Wait for approval before implementing
- Document all decisions

### 3. Briefs Are Read-Only
The `briefs/` folder contains the product specification.
- Read them for understanding
- Never modify them
- They are the source of truth for product behavior

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
# Run locally
uvicorn app.main:app --reload

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```
