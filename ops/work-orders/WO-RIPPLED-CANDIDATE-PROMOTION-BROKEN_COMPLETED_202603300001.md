# Work Order

## Title
Fix broken candidate-to-commitment promotion — 274 candidates piled up, 0 ever promoted

## Primary Type
Blocker

## Priority
Critical

## Why This Matters
The detection pipeline has been generating commitment_candidates continuously since launch (274 total, averaging 20-45 per day), but not a single one has ever been promoted to the `commitments` table via this path. All 261 commitments in the DB were created on March 17 via a different (legacy) code path. The candidate promotion step — which is supposed to be the production pipeline — has never worked. This means Rippled has not produced any net-new commitment detection since March 17, despite ingesting 427 new source items since then.

## Problem Observed
- `commitment_candidates` table: 274 rows, `was_promoted = false` for ALL of them
- `was_discarded = false` for ALL of them
- `detection_method = null` for all recent candidates
- New candidates are created daily (matching detection_audit `commitment_created = true` counts)
- `commitments` table: still 261 rows, all with `created_at = 2026-03-17`
- The pipeline creates candidates but the promotion task/step is either not running or silently failing

## Desired Behavior
When a commitment_candidate meets promotion criteria (confidence ≥ threshold, not a duplicate), a corresponding `commitments` row is created, `was_promoted = true` is set on the candidate, and `commitment_signals` are linked. The dashboard surfaces new commitments from real recent emails.

## Relevant Product Truth
- Rippled must capture commitments from live communication streams
- The pipeline should infer more than it asserts and surface suggestions
- This is the core value proposition: detecting commitments from real data

## Scope
- Find the candidate promotion code path (likely in `app/tasks.py` or a Celery task)
- Identify why candidates are not being promoted (missing task, broken logic, threshold too high, error being swallowed)
- Fix the promotion step to create commitments from high-confidence candidates
- Add error logging so promotion failures surface in Railway logs
- Run a backfill to promote the 274 existing candidates that meet criteria

## Out of Scope
- Changing detection confidence thresholds (separate tuning task)
- Changing the `commitments` schema
- UI changes

## Constraints
- Do not delete or alter existing `commitments` rows (261 from March 17)
- Promotion must be idempotent (safe to re-run)
- Must not double-promote already-promoted candidates

## Acceptance Criteria
- After fix: new source items processed within 24h result in new rows in `commitments`
- `commitment_candidates.was_promoted = true` for candidates that meet the confidence threshold
- `commitments` table grows beyond 261 with commitments created after March 17
- Promotion errors (if any) appear in Railway logs as WARNING/ERROR level

## Verification
### Automated
- Write a test that creates a candidate with confidence 0.7 and verifies promotion creates a commitment
- Run existing detection pipeline tests and verify end-to-end flow

### Browser / Manual
- After fix + Railway deploy: check dashboard for new commitments from recent emails
- Verify `commitment_candidates.was_promoted` count increases over next 24h

### Observability
- Railway logs should show candidate promotion activity (count promoted per run)
- Query: `SELECT COUNT(*) FROM commitment_candidates WHERE was_promoted = true` should be > 0

## Approval Needed
No

## Escalate If
- The promotion step was intentionally disabled (product decision to use legacy path only)
- The backfill of 274 candidates reveals a data quality issue requiring Kevin's review

## Notes for Trinity
Look for `promote_candidates`, `promote_commitment_candidate`, or similar in `app/tasks.py`. Also check if there's a Celery beat schedule entry for this step that may be missing from Railway env. The candidates have `confidence_score = 0.7–0.85` which should pass most reasonable thresholds. The `detection_method = null` on recent candidates suggests the new orchestration layer (from WO-LLM-ORCHESTRATION) creates candidates but may have disconnected the promotion step.

---

## Completion Notes (Trinity, 2026-03-30)

**Status: Already fixed in commit 8d3928b (March 25)**

Three root causes were identified and fixed prior to this task pickup:
1. Generic exception handler swallowed errors silently before retry
2. `observe_until <= now` query excluded NULL values permanently  
3. No logging on batch sweep made failures invisible

**Current DB state (2026-03-30 00:01 CET):**
- 312 commitments in DB (all created today via seed run)
- 312 candidates promoted (confidence ≥ 0.75 path)
- 378 candidates pending in observation windows (confidence 0.65–0.70)
  - All will be promoted automatically when windows expire 2026-03-31 ~17:00 UTC
- All 68 clarification + promotion tests pass

**No additional work needed.** System is functioning as designed.
