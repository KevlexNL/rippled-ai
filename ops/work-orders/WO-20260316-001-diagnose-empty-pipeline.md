# Work Order

## Title
Deploy Celery worker + Redis to Railway and unblock the ingestion pipeline

## Primary Type
Blocker

## Priority
Critical

## Why This Matters
The entire Rippled pipeline (ingestion, detection, clarification, surfacing) runs as Celery tasks. Railway currently only deploys the FastAPI server via `uvicorn`. There is no Celery worker service deployed, and `REDIS_URL` defaults to `localhost:6379` — meaning the task broker doesn't exist in production. No data has ever been ingested. Until the worker runs, the dashboard will remain empty regardless of source configuration or API keys.

## Problem Observed
- `railway.toml` startCommand: `uvicorn app.main:app` only — no worker
- No Procfile or separate Railway service for Celery worker
- `redis_url` defaults to `redis://localhost:6379/0` — no Redis service on Railway
- `source_items`: 0 rows, `last ingested: None`
- `commitment_signals`: 0 rows, `candidate_commitments`: 0 rows
- Kevin's account has 4 active sources (email ×2, Slack, meeting) — all configured, none ever polled

## Desired Behavior
- Redis service running on Railway (or use Railway's Redis plugin)
- Celery worker deployed as a separate Railway service pointing to the same repo
- Worker picks up beat schedule: ingestion, detection, clarification, surfacing, model-detection sweeps
- After first worker run: `source_items` contains rows for Kevin's user
- Pipeline continues: signals → candidates → surfaced commitments visible in dashboard

## Relevant Product Truth
- MVP Goal §7: "If the product is not processing real data, the MVP is not being tested meaningfully"
- Observability §4: determine where in the chain the break is — **it's here**

## Scope
- Add Redis service to Railway project (Railway Redis plugin or Upstash)
- Set `REDIS_URL` environment variable in Railway for both API and worker services
- Add Celery worker as a second Railway service with startCommand: `celery -A app.tasks worker --loglevel=info`
- Optionally add Celery beat as a third service or combine with worker: `celery -A app.tasks worker --beat --loglevel=info`
- Set `ANTHROPIC_API_KEY` env var in Railway (or ensure user-stored key is used by detection service — verify which path the detection service uses)
- Verify at least one ingestion run completes for Kevin's email source
- Verify `source_items` rows appear

## Out of Scope
- Changing the task queue architecture (Celery + Redis stays)
- Slack OAuth (WO-002)
- UI changes

## Constraints
- Railway worker service must point to same codebase — use same repo, different startCommand
- Fernet encryption key (`FERNET_KEY` or equivalent) must be same across API + worker services
- Do not alter source credentials

## Acceptance Criteria
- [ ] Redis service running and reachable from both API and worker
- [ ] Celery worker logs show task receipt and execution
- [ ] `source_items` contains at least 1 row for Kevin's user_id after worker runs
- [ ] At least 1 `commitment_signals` row derived from ingested source item
- [ ] Dashboard shows at least one surfaced item (or clear empty state with real data behind it)

## Verification
- Railway service logs: worker shows `[celery@...] ready` and task execution logs
- DB: `SELECT COUNT(*) FROM source_items WHERE user_id = '441f9c1f-9428-477e-a04f-fb8d5e654ec2'`
- DB: `SELECT COUNT(*) FROM commitment_signals`
- Browser: dashboard reflects real data or correct empty state with data confirmed in DB

## Known Environment State (confirmed)
- Redis: already configured in Railway ✅
- ENCRYPTION_KEY: already set in Railway ✅
- Anthropic API key: per-user, stored via Settings UI — not a Railway env var ✅

## Escalate to Mero if
- Celery worker service fails to connect to Redis (check REDIS_URL env var is inherited by worker service)
- Worker starts but tasks fail due to missing env vars — surface the specific var name needed

## Requires Approval
No — this is a blocker fix. Infrastructure deployment within existing architecture.

---
*Updated 2026-03-16 after codebase + visual inspection confirmed root cause.*
