# D4 — User Feedback Loops: Interpretation

**Stage:** 2 — INTERPRET
**Date:** 2026-04-02
**Status:** Awaiting Trinity review

---

## What We're Building

A closed feedback loop: when a user dismisses, confirms, or corrects a commitment, that signal flows back into the detection, surfacing, and completion pipelines as per-user threshold adjustments. After 20+ feedback events, Rippled adapts — fewer false positives for users who dismiss often, higher confidence for senders they repeatedly confirm.

### Deliverables

1. **`user_feedback` table** — stores every feedback action with commitment context
2. **`threshold_adjustments` JSONB column** on `user_commitment_profiles` — computed per-user overrides
3. **`app/services/feedback_adapter.py`** — adaptation computation service
4. **Pipeline integration** — detection, surfacing, and completion pipelines read adjustments
5. **API endpoints** — feedback submission + stats transparency
6. **Celery task** — periodic recomputation
7. **Frontend** — dismiss/confirm/"not a commitment" actions on CommitmentRow

---

## What Already Exists to Extend

### UserCommitmentProfile (`orm.py:491`)
Already has per-user learning fields:
- `trigger_phrases`, `high_signal_senders`, `suppressed_senders` (JSONB)
- `sender_weights`, `phrase_weights` (JSONB)
- `total_items_processed`, `total_commitments_found`

**Decision:** Add `threshold_adjustments: JSONB` here. The model already stores per-user learning data — this is the natural home.

### Existing Feedback Tables (`orm.py:603-640`)
Two feedback models already exist:
- `SignalFeedback` — extraction review (rating 1-5, missed_commitments, false_positives)
- `OutcomeFeedback` — outcome review (was_useful, usefulness_rating, was_timely)

**These are Tier 2 internal review tools, not user-facing.** D4's `user_feedback` table is distinct: it captures lightweight user actions (dismiss/confirm/correct) on commitment cards from the frontend. No overlap — different purpose, different audience, different schema.

### Detection Pipeline (`detector.py`)
- `_compute_confidence()` at line 55 computes confidence from `pattern.base_confidence + external bonus`
- `run_detection()` at line 178 already loads `UserCommitmentProfile` (line 211)
- **Integration point:** After loading profile, also read `threshold_adjustments` and apply `detection_confidence_delta` + `sender_adjustments[sender]` + `pattern_adjustments[trigger_class]` to confidence.

### Surfacing Pipeline (`surfacing_runner.py`)
- `run_surfacing_sweep()` iterates active commitments and calls `route()` → `classify()` + `score()`
- The surfacing router (`surfacing_router.py:67`) applies thresholds via `classify()` and `score()`
- **Integration point:** Before calling `route()`, load the user's `threshold_adjustments` and pass `surfacing_threshold_delta` to `route()`. The router adjusts the priority score or the threshold check accordingly.

### Completion Pipeline (`completion/scorer.py`)
- `score_evidence()` at line 165 computes multi-dimensional scores
- `_compute_completion_confidence()` multiplies delivery by type multiplier
- **Integration point:** After computing `completion_confidence`, apply `completion_confidence_delta` from the user's adjustments.

### Commitments API (`api/routes/commitments.py`)
- Already has `_get_commitment_or_404()` with user scoping
- Skip endpoint at line 354 is a close analog for the feedback endpoint pattern
- **Decision:** Add feedback endpoint here (not a new file) — `POST /commitments/{id}/feedback`. It's a commitment sub-resource.

### User Settings API (`api/routes/user_settings.py`)
- Already returns user config (observation windows, auto-close)
- **Decision:** Add `GET /user/feedback-stats` here — it returns per-user feedback transparency data, fits naturally with settings.

### Celery Tasks (`tasks.py`)
- Has a well-established periodic task pattern (beat_schedule at line 68)
- **Decision:** Add `recompute-feedback-thresholds` daily task. Also trigger recomputation on-demand after every N feedback events (configurable, default 10).

### Frontend CommitmentRow (`frontend/src/components/CommitmentRow.tsx`)
- Currently shows: StatusDot, title, DeliveryBadge, ContextLine, clarification inline prompt
- No dismiss/confirm actions exist yet
- **Decision:** Add a small action bar (X dismiss, ✓ confirm, "Not a commitment") below each row. Only visible on non-clarification rows.

---

## Schema Decisions

### New Table: `user_feedback`

```sql
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    action TEXT NOT NULL,  -- 'dismiss' | 'confirm' | 'correct_owner' | 'correct_deadline' | 'correct_description' | 'mark_not_commitment' | 'mark_delivered' | 'reopen'
    field_changed TEXT,     -- nullable, e.g. 'owner', 'deadline'
    old_value TEXT,         -- nullable
    new_value TEXT,         -- nullable
    source_type TEXT,       -- denormalized from commitment for query efficiency
    trigger_class TEXT,     -- denormalized from originating candidate
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_user_feedback_user_id ON user_feedback(user_id);
CREATE INDEX ix_user_feedback_created_at ON user_feedback(created_at);
```

**Rationale for denormalizing `source_type` and `trigger_class`:** The adaptation service needs to aggregate feedback by sender and pattern. Joining through commitment → candidate → source_item on every recomputation is expensive. Denormalizing at write time (from the commitment's originating candidate) keeps the recompute query simple and fast.

**commitment_id is NOT NULL** (differs from brief's "nullable for general feedback"). Rationale: every feedback action in scope is commitment-specific. General feedback is out of scope per the brief. Removing the nullable simplifies the schema and avoids orphaned feedback rows.

### New Column on `user_commitment_profiles`

```sql
ALTER TABLE user_commitment_profiles
    ADD COLUMN threshold_adjustments JSONB;
```

JSONB schema:
```json
{
    "surfacing_threshold_delta": 0.05,
    "detection_confidence_delta": -0.03,
    "sender_adjustments": {"alice@example.com": 0.10},
    "pattern_adjustments": {"explicit_self_commitment": 0.02},
    "completion_confidence_delta": 0.0,
    "last_computed_at": "2026-04-02T12:00:00Z",
    "feedback_count": 45
}
```

All deltas are bounded to `[-0.15, +0.15]`. `sender_adjustments` and `pattern_adjustments` individual values are also bounded. This prevents runaway drift from concentrated feedback on a single sender/pattern.

---

## Service Design: `feedback_adapter.py`

### `compute_threshold_adjustments(user_id, db) -> dict`

Algorithm:
1. Query `user_feedback` for the user (all events, or last N=200 for performance)
2. Compute ratios:
   - **Dismiss rate** = count(dismiss + mark_not_commitment) / total over last 50 items
   - **Confirm rate per sender** = count(confirm for sender) / total(feedback for sender)
   - **Pattern dismiss rate** = count(dismiss for trigger_class) / total(feedback for trigger_class)
   - **Reopen rate** = count(reopen) / total(mark_delivered + confirm)
3. Apply rules (from brief):
   - Dismiss rate > 30% → `surfacing_threshold_delta += 0.05`
   - Confirm rate > 80% for a sender → `sender_adjustments[sender] = +0.10`
   - Pattern dismiss rate > 40% → `pattern_adjustments[trigger_class] = -0.05`
   - Reopen rate > 20% → `completion_confidence_delta = -0.05`
4. Cap all deltas to `[-0.15, +0.15]`
5. Return the full adjustments dict with `last_computed_at` and `feedback_count`

### `apply_detection_adjustment(base_confidence, profile, sender, trigger_class) -> float`
Convenience function for detector.py. Applies `detection_confidence_delta` + sender + pattern adjustments.

### `apply_surfacing_adjustment(priority_score, profile) -> int`
Convenience function for surfacing_runner.py. Adjusts priority score based on `surfacing_threshold_delta`.

### `apply_completion_adjustment(completion_confidence, profile) -> float`
Convenience function for scorer.py. Applies `completion_confidence_delta`.

### Minimum feedback guard
All adjustments return 0.0 / no-op when `feedback_count < 20`. This is enforced at read time (in the apply functions), not just at write time, as a safety net.

---

## Pipeline Integration Points

### 1. Detection (`detector.py`)
**Where:** After `_compute_confidence()` call (line 320 for Tier 2, line 249 for Tier 1)
**How:**
```python
# After confidence = _compute_confidence(pattern, is_ext)
confidence = apply_detection_adjustment(
    float(confidence), profile, sender_email, pattern.trigger_class
)
confidence = Decimal(str(round(confidence, 3)))
```
**Profile is already loaded** at line 211. No additional query needed.

### 2. Surfacing (`surfacing_runner.py`)
**Where:** Inside the per-commitment loop (line 206), before or after `route()` call
**How:** Load user's profile once per user_id (batch), pass `surfacing_threshold_delta` to `route()` as an optional parameter. The router adjusts the priority score.
**Alternative:** Apply the delta to `priority_score` after `route()` returns. Simpler, same effect for routing decisions.

**Recommended:** Post-route adjustment on `priority_score`. Avoids modifying the router's signature and keeps the adjustment visible in the code.

### 3. Completion (`completion/scorer.py`)
**Where:** In `score_evidence()` after computing `completion` (line 182)
**How:**
```python
completion = apply_completion_adjustment(completion, user_profile)
```
**Note:** `score_evidence()` currently doesn't receive user context. We'll need to add an optional `user_profile` or `threshold_adjustments` parameter. This is a minimal signature change.

---

## API Design

### `POST /api/v1/commitments/{id}/feedback`

Request body:
```json
{
    "action": "dismiss",
    "field_changed": null,
    "old_value": null,
    "new_value": null
}
```

Response: `201 Created` with the created `UserFeedback` record.

Behavior:
1. Validate commitment exists and belongs to user
2. Validate action is one of the allowed values
3. Denormalize `source_type` and `trigger_class` from the commitment's originating candidate
4. Insert `user_feedback` row
5. If action is `dismiss` or `mark_not_commitment`: also transition commitment to `discarded` (if allowed by lifecycle FSM)
6. If action is `confirm`: transition to `confirmed` (if allowed)
7. If action is `mark_delivered`: transition to `delivered` (if allowed)
8. Check if user's feedback count has crossed a recompute threshold (every 10 events) → enqueue `recompute_feedback_thresholds` task
9. Return the feedback record

### `GET /api/v1/user/feedback-stats`

Response:
```json
{
    "total_feedback_count": 45,
    "threshold_adjustments": {
        "surfacing_threshold_delta": 0.05,
        "detection_confidence_delta": -0.03,
        "sender_adjustments": {"alice@example.com": 0.10},
        "pattern_adjustments": {"explicit_self_commitment": 0.02},
        "completion_confidence_delta": 0.0,
        "last_computed_at": "2026-04-02T12:00:00Z",
        "feedback_count": 45
    },
    "feedback_summary": {
        "dismiss_count": 12,
        "confirm_count": 28,
        "correct_count": 5
    }
}
```

---

## Frontend Scope

### CommitmentRow Actions
Add a lightweight action bar to `CommitmentRow.tsx`:

- **Dismiss (X)** — calls `POST /commitments/{id}/feedback` with `action: "dismiss"`
- **Confirm (✓)** — calls with `action: "confirm"`
- **"Not a commitment"** — calls with `action: "mark_not_commitment"`

Implementation approach:
- Add three small icon buttons below the commitment title/context line
- Only show on non-clarification rows (when `hasClarification` is false)
- Use optimistic UI — immediately remove/update the row, roll back on error
- Invalidate the `['surface']` query after mutation

### User Settings (optional)
Add a "Feedback & Learning" section to settings showing:
- Total feedback count
- Current adjustment factors (human-readable)
- "These adjustments are based on your X corrections"

This is low priority — implement if time permits.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| **Feedback spam** — user rapidly dismisses everything, driving thresholds to max | +/- 0.15 cap prevents runaway. 20-event minimum prevents premature adjustment. |
| **Stale adjustments** — user behavior changes but old feedback still influences | Use last-50-items window for ratio computation, not all-time. `last_computed_at` enables staleness detection. |
| **Schema migration on active table** — adding JSONB to `user_commitment_profiles` | JSONB with NULL default is a safe `ALTER TABLE ADD COLUMN` — no table rewrite needed on Postgres. |
| **Denormalization drift** — `source_type`/`trigger_class` on feedback rows could become stale if commitment changes | These are immutable properties of how the commitment was detected. They don't change after creation. |
| **Completion scorer signature change** — adding profile parameter | Optional parameter with `None` default — backward compatible. Existing callers unaffected. |
| **Frontend action bar clutter** — too many buttons on compact rows | Three small icons (X, ✓, ⊘) with no labels. Minimal visual footprint. Could also use a swipe gesture on mobile. |

---

## Test Plan

### Unit Tests (`tests/test_feedback_adapter.py`) — ~12 tests

1. **compute_threshold_adjustments** — basic case with mixed feedback
2. **Dismiss rate > 30%** → surfacing delta = +0.05
3. **Dismiss rate < 30%** → surfacing delta = 0.0
4. **Confirm rate > 80% for sender** → sender boost = +0.10
5. **Pattern dismiss rate > 40%** → pattern reduction = -0.05
6. **Reopen rate > 20%** → completion delta = -0.05
7. **Cap enforcement** — deltas bounded to +/- 0.15
8. **Minimum 20 events guard** — returns all zeros when count < 20
9. **apply_detection_adjustment** — applies delta + sender + pattern correctly
10. **apply_surfacing_adjustment** — adjusts priority score
11. **apply_completion_adjustment** — adjusts completion confidence
12. **Empty feedback** — all functions return neutral/zero

### Integration Tests (`tests/test_feedback_integration.py`) — ~10 tests

1. **POST feedback endpoint** — creates feedback record, returns 201
2. **POST feedback with dismiss** — transitions commitment to discarded
3. **POST feedback with confirm** — transitions commitment to confirmed
4. **POST feedback with mark_not_commitment** — transitions to discarded
5. **POST feedback on nonexistent commitment** — returns 404
6. **POST feedback with invalid action** — returns 422
7. **GET feedback-stats** — returns current adjustments and summary
8. **GET feedback-stats with no feedback** — returns zeros/empty
9. **Recompute threshold task** — Celery task updates profile
10. **Full loop** — 20+ feedback events → recompute → verify pipeline reads adjusted values

**Target: 22+ tests total.**

---

## Open Questions for Trinity

1. **Recompute trigger threshold:** Brief says "on-demand after N feedback events." I'm proposing N=10. Is that the right frequency, or should it be lower (5) for faster adaptation?

2. **Frontend mark_delivered action:** The brief includes `mark_delivered` and `reopen` as feedback actions. Should these appear on the CommitmentRow action bar, or only `dismiss`/`confirm`/`mark_not_commitment`? The delivery actions already exist in `DeliveryActions.tsx`.

3. **Lifecycle side effects:** When a user dismisses a commitment, should we transition it to `discarded`? This is what I'm proposing, but it means the commitment is fully removed from all views. Alternative: transition to `dormant` (recoverable). The brief doesn't specify.

---

## Implementation Order (for Stage 3)

1. Migration: `user_feedback` table + `threshold_adjustments` column
2. ORM: `UserFeedback` model, update `UserCommitmentProfile`
3. Service: `feedback_adapter.py` (compute + apply functions)
4. Unit tests for adapter
5. API: feedback endpoint + stats endpoint
6. Integration tests for API + pipeline
7. Pipeline integration: detector, surfacing, completion
8. Celery task: periodic + on-demand recompute
9. Frontend: action bar on CommitmentRow
10. Verify all tests pass, ruff clean, frontend builds
