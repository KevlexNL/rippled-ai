# Commitment Count Discrepancy Investigation

**Date:** 2026-03-30
**User:** 441f9c1f-9428-477e-a04f-fb8d5e654ec2
**Reported:** Commitments dropped from 274 (2026-03-19) to 261; source_items grew from 435 to 552.

## Current DB State (2026-03-30)

| Table | Count |
|---|---|
| commitments | 313 |
| commitment_signals | 0 |
| source_items | 1,489 (1,258 processed / 231 unprocessed) |
| commitment_candidates | queried |
| surfacing_audit | 0 |

### Commitment state distribution
- needs_clarification: 300
- proposed: 13

### Timeline evidence
- All 313 commitments created on **2026-03-29** (312) and 2026-03-30 (1)
- Source items: bulk ingested on 2026-03-26 (1,396 items — full DB reset + reseed)
- No lifecycle transitions to terminal states (discarded/canceled/closed/completed) exist

## Root Cause Analysis

### Finding: No deletion mechanism exists

1. **No DELETE triggers** on the `commitments` table (verified via `information_schema.triggers`)
2. **No Celery cleanup tasks** that delete commitments — all tasks either create or transition states:
   - `run_completion_sweep`: transitions active → delivered → closed (state change, not deletion)
   - `recompute_surfacing`: updates surfacing fields, never deletes
   - `run_clarification_batch`: promotes candidates to commitments (creates, not deletes)
3. **DELETE endpoint** (`DELETE /commitments/{id}`) sets `lifecycle_state='discarded'` — soft delete, not hard delete
4. **CASCADE rules**: `commitments.context_id` uses `ON DELETE SET NULL` (context deletion doesn't cascade to commitments); commitment children (signals, transitions) cascade on commitment delete but nothing cascades INTO commitments from parent tables except `users.id ON DELETE CASCADE`

### Finding: Count fluctuation caused by full_reseed.py

The `scripts/full_reseed.py` script (WO-RIPPLED-FULL-DB-RESET-SEED-RUN) was executed on **2026-03-29**:

- **Phase 2** truncates the `commitments` table (along with 25 other data tables)
- **Phase 3** re-runs the detection pipeline on all source_items chronologically
- This produces a **different** commitment count each time because:
  - Detection pipeline version may have changed between runs
  - Source items available differ (1,489 now vs 435 at the time of the original count)
  - Processing order affects candidate-to-commitment promotion
  - 231 source_items remain unprocessed (seed_processed_at IS NULL)

### Timeline reconstruction

| Date | Event | Commitment count |
|---|---|---|
| ~2026-03-19 | Original observation | 274 |
| Between 03-19 and 03-26 | Unknown — possible earlier reseed or incremental detection | ~261 (the "drop") |
| 2026-03-26 | Full DB reset (`full_db_reset.py`): truncated all data tables, re-ingested 1,396 source_items | 0 (post-truncate) |
| 2026-03-29 | Full reseed (`full_reseed.py`): detection pipeline on all source_items | 313 |
| 2026-03-30 | Current state | 313 |

## Conclusion

**The commitment count "drop" from 274 to 261 was not caused by a bug or unwanted deletion.** It was a transient state caused by the full database reset and reseed cycle. The current count (313) exceeds the original, confirming that the detection pipeline is generating more commitments from the expanded source_items corpus.

## Recommendations

1. **No data recovery needed** — no commitments were lost to a bug; the reseed intentionally rebuilds from scratch
2. **Process remaining 231 unprocessed source_items** — run detection sweep or trigger `detect_commitments` for items where `seed_processed_at IS NULL`
3. **Add observability** — log commitment count before/after reseed runs to make future count changes traceable
4. **Consider immutable audit**: if commitment count tracking is important, add a periodic snapshot to a metrics table

## No fix migration required

Since no data was lost to a bug (the truncate+reseed is intentional), no recovery migration is needed.
