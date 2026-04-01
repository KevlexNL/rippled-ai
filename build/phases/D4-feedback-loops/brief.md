# Phase D4 — User Feedback Loops for Adaptive Thresholds

**Phase:** D4-feedback-loops
**Date:** 2026-04-01
**Status:** QUEUED
**Brief References:** Brief 2 (Product Principles — Principle 19), Brief 4 (Source Model), Brief 10 (Completion Detection)

---

## Goal

Enable the system to learn from user corrections and feedback to improve detection accuracy, surfacing relevance, and completion inference over time. Principle 19 states: "user corrections improve behavior" and "thresholds can tighten over time." Currently, when a user dismisses a false positive, confirms a commitment, or corrects an owner/deadline, that signal is logged in `audit_log` but not fed back into the scoring and detection pipeline. This phase closes that loop: user feedback adjusts per-user confidence thresholds, sender weights, and pattern effectiveness scores so Rippled becomes more accurate for each user over time.

---

## Scope (what's included)

- **Feedback event capture:** Structured recording of user feedback actions (dismiss, confirm, correct_owner, correct_deadline, correct_description, mark_not_commitment, mark_delivered, reopen)
- **New `user_feedback` table:** Stores each feedback event with commitment_id, action type, field changed, old/new values, and timestamp
- **Threshold adaptation service:** `app/services/feedback_adapter.py` that periodically recomputes per-user adjustments based on accumulated feedback
- **Per-user threshold overrides on `user_commitment_profiles`:** New JSONB column `threshold_adjustments` storing computed overrides (e.g., raise surfacing threshold if user frequently dismisses, lower detection threshold for senders they frequently confirm)
- **Integration with detection pipeline:** Detection confidence modifiers based on user's historical accept/reject ratio for similar patterns
- **Integration with surfacing pipeline:** Surfacing threshold adjustments based on dismiss rate
- **Integration with completion pipeline:** Completion confidence adjustments based on user's confirm/reopen patterns
- **API endpoints:** `POST /api/v1/commitments/{id}/feedback` for explicit feedback, `GET /api/v1/user/feedback-stats` for transparency (how many corrections, current adjustment factors)
- **Frontend feedback UI:** Lightweight dismiss/confirm/correct actions on commitment cards

---

## Out of Scope

- Real-time ML model retraining (this is threshold/weight adjustment, not model fine-tuning)
- Cross-user learning (each user's feedback affects only their own thresholds)
- Automated threshold adjustment without minimum feedback volume (require at least 20 feedback events before adjusting)
- Feedback on clarifications (only commitment-level feedback in this phase)

---

## Technical Approach

**Database:**
New `user_feedback` table:
```
id: UUID PK
user_id: FK -> users.id
commitment_id: FK -> commitments.id (nullable for general feedback)
action: TEXT ('dismiss' | 'confirm' | 'correct_owner' | 'correct_deadline' | 'correct_description' | 'mark_not_commitment' | 'mark_delivered' | 'reopen')
field_changed: TEXT (nullable)
old_value: TEXT (nullable)
new_value: TEXT (nullable)
source_type: TEXT (nullable — source type of the commitment for pattern tracking)
trigger_class: TEXT (nullable — detection pattern that created this commitment)
created_at: TIMESTAMPTZ
```

New column on `user_commitment_profiles`:
```
threshold_adjustments: JSONB
```
Schema:
```json
{
  "surfacing_threshold_delta": 0.05,
  "detection_confidence_delta": -0.03,
  "sender_adjustments": {"alice@example.com": 0.10},
  "pattern_adjustments": {"explicit_self_commitment": 0.02},
  "completion_confidence_delta": 0.0,
  "last_computed_at": "2026-04-01T12:00:00Z",
  "feedback_count": 45
}
```

**Adaptation service:**
`app/services/feedback_adapter.py`:
- `compute_threshold_adjustments(user_id, db) -> dict` — queries `user_feedback`, computes adjustment deltas
- Dismiss rate > 30% over last 50 items → raise surfacing threshold by 0.05
- Confirm rate > 80% for a sender → boost that sender's detection confidence by 0.10
- Pattern-specific: if a trigger_class has > 40% dismiss rate → reduce its confidence by 0.05
- Caps: adjustments bounded to +/- 0.15 to prevent runaway drift
- Runs as a Celery periodic task (daily) or on-demand after N feedback events

**Pipeline integration:**
- `detection/detector.py`: Apply `detection_confidence_delta` + `sender_adjustments` + `pattern_adjustments` to `compute_confidence()`
- `surfacing_runner.py`: Apply `surfacing_threshold_delta` to surfacing threshold check
- `completion/scorer.py`: Apply `completion_confidence_delta` to completion scoring

**API:**
- `POST /api/v1/commitments/{id}/feedback` — records feedback event, triggers recompute if threshold reached
- `GET /api/v1/user/feedback-stats` — returns current adjustment factors and feedback counts for transparency

**Frontend:**
- Add dismiss (X), confirm (checkmark), and "not a commitment" actions to commitment cards on Main and Shortlist
- Show feedback stats in user settings (optional, for transparency)

---

## Success Criteria

- [ ] User feedback events are captured and stored with full context (source type, trigger class)
- [ ] After 20+ feedback events, threshold adjustments are computed and applied
- [ ] A user who frequently dismisses false positives sees fewer low-confidence items surfaced
- [ ] A user who frequently confirms commitments from a specific sender sees those score higher
- [ ] Adjustment deltas are bounded (+/- 0.15) to prevent overcorrection
- [ ] Feedback stats endpoint shows current adjustments transparently
- [ ] Frontend allows dismiss/confirm/correct actions on commitment cards
- [ ] Existing detection/surfacing/completion tests pass with zero adjustments (no behavioral change without feedback)
- [ ] Tests cover: adjustment computation, boundary capping, sender-specific boost, pattern-specific reduction, minimum feedback threshold

---

## Files Likely Affected

- `app/models/orm.py` — new `UserFeedback` model, `UserCommitmentProfile` new column
- `app/services/feedback_adapter.py` — new adaptation service
- `app/services/detection/detector.py` — apply per-user confidence adjustments
- `app/services/surfacing_runner.py` — apply surfacing threshold adjustments
- `app/services/completion/scorer.py` — apply completion confidence adjustments
- `app/api/routes/commitments.py` or new `feedback.py` — feedback endpoint
- `app/api/routes/user_settings.py` — feedback stats endpoint
- `app/tasks.py` — periodic recomputation task
- `alembic/versions/` — new migration
- `frontend/src/` — feedback actions on commitment cards
- `tests/` — new test files for feedback adapter and integration

---

## Dependencies

- D1 and D2 should go first (they establish the user-configurable settings pattern)
- Entity extraction and detection pipeline must be stable (they are — Cycle D fixed these)
- `UserCommitmentProfile` model exists from entity extraction work

---

## Estimated Effort

2-3 days. The feedback capture is straightforward, but the adaptation logic requires careful threshold computation, boundary capping, and integration across three pipelines (detection, surfacing, completion). Testing the feedback-to-adjustment loop end-to-end is the main complexity.

---

## Brief References

**Brief 2 — Product Principles, Principle 19:**
> "user corrections improve behavior" / "thresholds can tighten over time" / "the product should support learning and tuning without making early trust sacrifices"

This is the primary driver. The system should "age gracefully from uncertainty to usefulness."

**Brief 4 — Source Model (Open Questions):**
> "channel-specific trust tuning based on user feedback" / "source weighting personalization by user/team"

**Brief 10 — Completion Detection (Open Questions):**
> "per-user completion sensitivity settings by commitment class"

All three briefs identify user feedback as a natural extension for improving system accuracy over time.
