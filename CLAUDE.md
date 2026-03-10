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

### 2. Build Protocol
Follow `build/BUILD_PROTOCOL.md`. Key principle: **interpret then build immediately**.
- Read ONLY files listed in your Work Order
- Write interpretation to `build/phases/XX/interpretation.md`
- **Proceed to implementation without waiting for approval**
- Document all decisions
- Only stop if you hit a genuine blocker (see BUILD_PROTOCOL for the full list)

### 3. Briefs Are Read-Only
The `briefs/` folder contains the product specification.
- Read them for understanding
- Never modify them
- They are the source of truth for product behavior

---

## Working Style

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### Self-Improvement Loop
- After ANY correction from Kevin: update `build/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start

### Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from Kevin
- Go fix failing CI tests without being told how

### Core Principles
- **Simplicity First:** Make every change as simple as possible. Impact minimal code.
- **No Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.

---

## Task Management

When working on a phase:
1. **Plan First:** Write plan to phase folder with checkable items
2. **Build immediately** after interpretation — no waiting for approval
3. **Track Progress:** Mark items complete as you go
4. **Explain Changes:** High-level summary at each step
5. **Document Results:** Update `decisions.md` and `completed.md`
6. **Capture Lessons:** Update `build/lessons.md` after corrections
7. **Report to Kevin** via Telegram when phase completes

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
