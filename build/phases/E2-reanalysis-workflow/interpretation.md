# E2 Re-analysis Workflow — Interpretation

**Stage:** INTERPRET  
**Date:** 2026-04-03

---

## What Exists

A `run_reanalysis_sweep` Celery task already exists (`app/tasks.py:744-799`) with:
- Beat schedule entry (every 10 min)
- Query for `flag_reanalysis=true` candidates (excluding promoted/discarded)
- Enqueue to `run_model_detection_pass`
- Flag cleared after enqueue
- 6 unit tests in `tests/test_reanalysis_sweep.py`

## Critical Gap Found

**`run_model_detection_pass` silently skips already-processed candidates.** Line 622:

```python
if candidate.model_called_at is not None:
    return {"status": "already_processed", "candidate_id": candidate_id}
```

If a candidate was already model-classified and later flagged for reanalysis (e.g., meeting transcript updated with better attribution), the sweep enqueues it but model detection immediately returns `already_processed`. The flag gets cleared but **no re-analysis actually happens**. This is a silent no-op bug.

## What Needs to Change

### 1. Reset `model_called_at` in sweep (fix the silent no-op)
When `run_reanalysis_sweep` clears `flag_reanalysis`, it must also set `model_called_at = NULL`. This makes the candidate eligible for re-processing by `run_model_detection_pass`.

**Why not modify `run_model_detection_pass`?** Adding a `force` parameter would change the interface for all callers. Resetting at the sweep level is cleaner — the sweep is the only entry point that needs forced re-processing.

### 2. Add `POST /candidates/{id}/reanalyze` API endpoint
Brief says "User manually requests re-analysis (if UI exists for this)" and "API endpoint is sufficient." Add a simple endpoint that sets `flag_reanalysis=true` on a candidate. The sweep picks it up within 10 minutes.

### 3. Per-candidate reanalysis logging
Current implementation only logs a summary count. Add per-candidate `logger.info` for traceability.

## What NOT to Change

- **Don't re-run full detection pipeline** (`run_detection()`). That function takes a `source_item_id` and creates *new* candidates. For reanalysis of an existing candidate, model re-classification is the correct approach — it re-evaluates whether the candidate is a real commitment.
- **Don't change the `flag_reanalysis` schema** (per brief).
- **Don't change `run_model_detection_pass` signature** — keep it simple, reset at sweep level.

## Implementation Plan

1. Modify `run_reanalysis_sweep` in `app/tasks.py`:
   - Reset `model_called_at = NULL` alongside `flag_reanalysis = False`
   - Add per-candidate log line
2. Add `POST /candidates/{candidate_id}/reanalyze` to `app/api/routes/candidates.py`
3. Update tests:
   - Verify `model_called_at` reset in UPDATE statement
   - Test API endpoint
   - Test idempotency (flagging already-flagged candidate)
4. Run full test suite

## Assumptions

- Resetting `model_called_at` is safe because the sweep also excludes promoted/discarded candidates
- The 10-minute beat interval is acceptable latency for manual trigger (user sets flag, sweep picks up next cycle)
- No need for immediate synchronous reanalysis — async via sweep is sufficient
