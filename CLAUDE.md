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

## Deferred Review Comments — @REVIEW_LATER

Use `@REVIEW_LATER` comments to flag things that need human review after some real-world usage. These are scanned weekly by an automated cron and surfaced to Kevin.

### Format
```python
# @REVIEW_LATER(YYYY-MM-DD): short title
# Action: what to do / what to query when reviewing
# Context: why this exists and what decision it feeds into
```

### Rules
- Use `YYYY-MM-DD` for the target review date (when enough usage data should exist)
- **Action** should be a concrete step — e.g. a SQL query, a grep, a specific check
- **Context** should reference the decision doc or brief section it relates to
- Once acted on (reviewed + resolved), **remove the comment** from the code
- Do NOT leave resolved comments in place — they become noise

### Example
```python
# @REVIEW_LATER(2026-03-30): commitment_type enum expansion
# Action: SELECT commitment_type, COUNT(*) FROM commitments WHERE commitment_type = 'other' GROUP BY 1 ORDER BY 2 DESC
# Context: Enum 'other' is a catch-all fallback. After ~3 weeks of real ingestion, promote frequent patterns to named values via migration. See build/phases/01-schema/qa-decisions.md Q4
```

### When to use
- Decisions made before real usage data exists (enum values, thresholds, config defaults)
- Architecture choices that should be revisited after scale/complexity increases
- Anything described as "good enough for MVP, revisit later"

### ⚠️ When NOT to use — the MVP viability rule
`@REVIEW_LATER` is for **refinement**, not for deferring things that need to work.

Do NOT use it to skip:
- Core functionality the product depends on to be usable
- Data integrity constraints (these must be right from the start)
- Anything a user would hit in normal usage

Ask yourself: **"If this is wrong or missing, does the product still work as intended?"**
- Yes → safe to defer with `@REVIEW_LATER`
- No → it must be built now, not tagged

A viable MVP is one where the core loop works end-to-end. Deferred reviews are for polish, extensibility, and data-driven tuning — not for holes in the foundation.

---

## Commands
```bash
# Run locally
uvicorn app.main:app --reload

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```
