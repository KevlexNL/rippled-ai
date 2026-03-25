# Work Order

## Title
Fix runaway detection re-scan loop — 27 items being scanned ~240x/day, $5.29 wasted

## Primary Type
Observability Gap / Blocker

## Priority
High

## Why This Matters
The detection Celery task is re-scanning the same source items every time it runs, without any guard to skip already-processed items. 27 non-suppressed items have been scanned 2,398 times each (since March 16). The total detection_audit table has 60,689 rows for only 688 source items. 60,146 of these are suppressed (cheap), but 418 tier_3 LLM calls and 174 tier_2 calls are being made repeatedly on the same items. Total detection cost so far: $5.29. At this rate: ~$0.50/day in unnecessary re-processing costs.

## Problem Observed
- `detection_audit` table: 60,689 rows for 688 source items
- 27 items have 2,398 scans each (first: 2026-03-16, last: 2026-03-25 — every single day)
- Distribution: 224 single-scan, 235 few-scans, 27 with >10 scans
- The `source_items.seed_processed_at` column exists but appears to not be checked before re-scanning
- Total cost: $5.29 and growing ~$0.50/day

## Desired Behavior
Each source item is processed by the detection pipeline exactly once (or re-processed only when explicitly triggered). The `seed_processed_at` or equivalent flag is set after first scan and checked before re-scanning. New items ingested by the IMAP poller are scanned once. Items that produce candidates are not re-scanned unless the candidate was discarded with a "retry" flag.

## Relevant Product Truth
- Cost efficiency is critical for sustainable MVP operation
- Detection should be reliable, not noisy — re-running the same items produces no new signal

## Scope
- Find the Celery detection task and identify why it lacks a "skip if already processed" guard
- Implement the guard using `seed_processed_at` (already on the schema) or `detection_audit` existence check
- Add logging: count of items scanned vs. skipped per detection run
- Backfill `seed_processed_at` for all 688 existing items that have been processed

## Out of Scope
- Changing detection prompts or confidence thresholds
- Changing which items are suppressed

## Constraints
- Must not skip items that haven't been processed yet (new ingestions from IMAP should still be detected)
- Guard must be compatible with Railway's stateless Celery workers (use DB state, not in-memory)

## Acceptance Criteria
- After fix: new `detection_audit` rows are only created for items that haven't been scanned before (or new items)
- `seed_processed_at` is populated for all processed items
- Daily detection_audit row count drops to match new item ingestion rate (typically 20-70/day)
- No item accumulates more than 1 audit record per legitimate trigger

## Verification
### Automated
- Write a test that runs detection twice on the same item and verifies only 1 audit record is created

### Browser / Manual
- Monitor Railway logs for 24h after fix — detection task should log "N new items, M skipped"

### Observability
- Query: `SELECT COUNT(*) FROM detection_audit WHERE created_at >= NOW() - INTERVAL '1 day'` should drop to ~20-70 (matching daily ingestion)
- Cost estimate from new detection_audit records should be near zero for already-processed items

## Approval Needed
No

## Escalate If
- The re-scan is intentional (e.g., designed to re-evaluate on new prompts) — escalate to Kevin with cost data

## Notes for Trinity
Look in `app/tasks.py` for the detection Celery task. Check if it queries all source_items (or all active ones) without filtering on `seed_processed_at IS NULL`. The fix is likely a single WHERE clause addition. Also check if there's a Celery beat schedule that triggers this too frequently. The `source_items.seed_processed_at` column exists in the schema — just needs to be used as the guard.
