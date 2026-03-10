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

## Critical Rules

### 1. Fresh Start
This is a **NEW** project. Do not reference or build on:
- OpenAgency OS (archived)
- Interpretation Engine (archived)
- Gating API (archived)
- Any code in `projects/_archive/`

### 2. Build Protocol — 6-Stage Cycle
Full spec: `build/BUILD_PROTOCOL.md`. Follow it strictly.

At the start of each stage, **state explicitly which stage you are entering**.

| Stage | Name | Key action |
|-------|------|------------|
| 1 | INTAKE | Read every file listed in the WO. Nothing else. |
| 2 | INTERPRET | Write interpretation.md. Notify Kevin immediately. Wait for evaluation. |
| 3 | BUILD | Implement with TDD after Kevin approves. |
| 4 | VERIFY | Tests green, ruff clean, smoke test. |
| 5 | COMMIT | Write completed.md, clean commit, push. |
| 6 | REPORT | Notify Kevin, prep next phase WO. |

Never skip a stage. Never merge stages. Always announce stage transitions.

### 3. Briefs Are Read-Only
The `briefs/` folder contains the product specification.
- Read them for understanding
- Never modify them
- They are the source of truth for product behavior

---

## Working Style

### TDD by Default
- Write failing tests first, implement to pass, refactor
- Never mark a phase complete without tests passing

### Self-Improvement Loop
- After ANY correction from Kevin: update `build/lessons.md` with the pattern
- Review lessons at session start

### Verification Before Done
- Never mark a task complete without proving it works
- Ask yourself: "Would a staff engineer approve this?"

### Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- Skip this for simple, obvious fixes — don't over-engineer

### Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding.
- Zero context switching required from Kevin.

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
# Run locally
uvicorn app.main:app --reload

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```
