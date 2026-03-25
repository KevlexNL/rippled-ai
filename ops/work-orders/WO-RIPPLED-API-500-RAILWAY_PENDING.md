# Work Order

## Title
Diagnose and fix Railway API 500 errors — all authenticated endpoints broken

## Primary Type
Blocker

## Priority
Critical

## Why This Matters
The production app is completely unusable. Every API endpoint returns HTTP 500 when called with a valid x-user-id header from an authenticated session. The IMAP poller is still running (source items ingested at 16:04 UTC today) but the web API is dead. Users cannot access the dashboard, surface list, or any data.

## Problem Observed
- All API endpoints return 500: `/api/v1/stats`, `/api/v1/sources`, `/api/v1/surface/main`, `/api/v1/surface/best-next-moves`, `/api/v1/contexts`, `/api/v1/integrations/google/status`
- Browser dashboard shows blank loading spinner indefinitely
- The same API calls work correctly when tested locally against the production DB
- Health endpoint returns 200, so the app process is running but request handling is broken
- Most recent code commits: WO-002 context grouping (2026-03-23), WO-004 email source deactivation (2026-03-23)
- Last successful git push: `a177ded` (2026-03-24 docs commit)

## Desired Behavior
All API endpoints return correct responses for authenticated requests. Dashboard loads normally.

## Relevant Product Truth
The app must function as a working MVP. A completely broken API prevents all user interaction and defeats the entire purpose.

## Scope
- Check Railway deployment logs for the current web service
- Identify the 500 error root cause (schema mismatch, missing env var, import error, ORM change)
- Fix the breaking change
- Verify all core endpoints respond correctly with the production user-id

## Out of Scope
- Infrastructure changes (scaling, new services)
- Feature work

## Constraints
- Must not break working Celery worker (source ingestion is currently functional)
- Fix must be deployable via git push to Railway

## Acceptance Criteria
- `GET /api/v1/stats` with header `x-user-id: 441f9c1f-9428-477e-a04f-fb8d5e654ec2` returns 200 with valid JSON
- `GET /api/v1/surface/main` with same header returns 200
- `GET /api/v1/contexts` with same header returns 200
- Dashboard loads without blank screen in browser

## Verification
### Automated
- Run existing test suite against local dev server post-fix
- Verify no regressions in routes/commitments, routes/sources, routes/surface

### Browser / Manual
- Log in at https://rippled-ai-production.up.railway.app/login
- Verify dashboard loads with data visible

### Observability
- Check Railway logs for the exact exception being thrown on 500 responses

## Approval Needed
No

## Escalate If
- The issue is a Railway infrastructure problem (not code) — escalate to Kevin
- The fix requires a breaking schema migration

## Notes for Trinity
Start with Railway deployment logs — look for startup errors or exception traces. The most likely cause is a code change in the last 2 commits (WO-002 context grouping, WO-004 email deactivation) introducing an ORM model reference or schema change that fails at runtime on Railway but not locally. Check `app/api/routes/contexts.py`, `app/models/schemas.py`, and `app/models/orm.py` for any field referenced in the new code that may not exist in the production DB schema.
