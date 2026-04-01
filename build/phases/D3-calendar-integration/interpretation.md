# Phase D3 — Deeper Calendar Integration: Interpretation

**Phase:** D3-calendar-integration
**Stage:** 2 — INTERPRET
**Date:** 2026-04-01

---

## 1. Goal & Scope Understanding

Calendar events currently sync into the `events` table via `GoogleCalendarConnector` but only feed commitment intelligence through the `DeadlineEventLinker` (Phase C3), which matches commitments **that already have a `resolved_deadline`** to nearby events using attendee+keyword+time scoring.

D3 broadens this: calendar events become a **general evidence source** for commitments, even those without deadlines. Three new link types:

| Link Type | Direction | What It Does |
|-----------|-----------|-------------|
| `deadline_hint` | Event → Commitment | Upcoming event suggests a due date for a commitment that lacks one, or corroborates an existing deadline |
| `completion_hint` | Event → Commitment | Past event matching a commitment's topic/entities = moderate evidence that work progressed or was delivered |
| `context` | Event → Commitment | Upcoming event (within 48h) boosts urgency in priority scoring |

Calendar events still do **not** create new commitments (out of scope). This is calendar-as-evidence, not calendar-as-origin.

---

## 2. Key Design Decision: Extend `CommitmentEventLink` vs. New Table

The brief proposes a new `event_commitment_links` table. However, `commitment_event_links` already exists with:
```
id, commitment_id, event_id, relationship, confidence, created_at
```

The existing `relationship` column currently only holds `"delivery_at"`. The brief's schema adds `link_type` and `metadata` — which maps cleanly to extending the existing table:

**Recommendation: Extend `commitment_event_links`** rather than creating a separate table.
- Add `metadata: JSONB` column (nullable) for matching details
- Expand `relationship` to accept new values: `deadline_hint`, `completion_hint`, `context`
- This avoids a parallel linking table that would fragment event-commitment queries across two tables

The `DeadlineEventLinker`, `NudgeService`, `PostEventResolver`, and `surfacing_runner` all query `CommitmentEventLink` filtering on `relationship == "delivery_at"` — these continue to work unchanged. New code filters on the new relationship values.

**Risk:** If Trinity prefers a separate table for clean separation, the migration is simple either way. But extending is simpler and avoids cross-table JOINs.

---

## 3. Implementation Plan: `calendar_matcher.py`

### 3.1 Module Structure

New file: `app/services/calendar_matcher.py`

```python
class CalendarMatcher:
    """Match calendar events to active commitments by entity/topic overlap."""

    def match(self, events: list[Event], commitments: list[Commitment]) -> list[EventCommitmentLink]:
        ...

    def _score_pair(self, event: Event, commitment: Commitment) -> tuple[str | None, float, dict]:
        """Returns (link_type, confidence, metadata) or (None, 0, {}) if no match."""
        ...

    def _entity_overlap(self, event: Event, commitment: Commitment) -> float:
        ...

    def _topic_overlap(self, event: Event, commitment: Commitment) -> float:
        ...

    def _is_generic_event(self, event: Event) -> bool:
        ...
```

### 3.2 Matching Logic

**Input sources per side:**
- **Event side:** `title`, `description`, `attendees[].name`, `attendees[].email`
- **Commitment side:** `title`, `description`, `target_entity`, `requester_name`, `requester_email`, `beneficiary_name`, `beneficiary_email`, `context_tags`, `commitment_text`

**Scoring dimensions:**

| Dimension | Weight | Method |
|-----------|--------|--------|
| Person entity overlap | 0.40 | Match event attendee names/emails against commitment requester/beneficiary/target_entity |
| Topic keyword overlap | 0.35 | Jaccard similarity on tokenized title+description (reuse `_tokenize` from `event_linker.py`) |
| Deliverable keyword match | 0.25 | Check if commitment deliverable terms appear in event title/description |

**Confidence thresholds:**
- `>= 0.50`: Create link
- `< 0.50`: Skip (avoids false positives)

### 3.3 Link Type Assignment

After scoring, determine link type based on event timing:
- **Event is in the future** AND commitment has no `resolved_deadline` → `deadline_hint`
- **Event is in the future** AND commitment has `resolved_deadline` → `context` (urgency boost only)
- **Event is in the past** (ended before now) → `completion_hint`

### 3.4 Generic Event Filtering

Critical success criterion: must NOT link generic events. Maintain a blocklist:

```python
_GENERIC_TITLES = {
    "standup", "stand-up", "daily standup", "daily stand-up",
    "1:1", "1-on-1", "one on one", "1 on 1",
    "team sync", "team meeting", "weekly sync",
    "all hands", "all-hands", "company meeting",
    "lunch", "break", "focus time", "busy",
    "office hours", "no meetings",
}
```

Events whose normalized title matches a generic pattern get skipped entirely. Additionally, events with very short titles (≤ 2 tokens after stop-word removal) get a confidence penalty of -0.15.

### 3.5 Deduplication

Before creating links, check existing `CommitmentEventLink` rows for the same `(event_id, commitment_id)` pair. Skip if already linked (regardless of relationship type).

---

## 4. Integration with Existing Services

### 4.1 `priority_scorer.py` — Calendar-Aware Urgency Boost

The scorer already has `proximity_spike(proximity_hours)` which gives 0–40 points based on event proximity. Currently this only fires for commitments with `delivery_at` links.

**Change:** After computing the existing proximity_spike, also check for `context` links. If a commitment has a `context` link to an event within 48h, add a smaller urgency boost (0–15 points, scaled by confidence and hours-until-event). This stacks with but is capped below the `delivery_at` proximity spike to avoid double-counting when both link types exist.

Implementation: add a `calendar_context_boost(commitment_id, db)` function or pass context-link proximity as a parameter to `score()`.

**Recommended approach:** Keep `score()` signature stable. Add an optional `context_proximity_hours: float | None = None` parameter. The caller (`surfacing_runner.py`) queries context links and passes the nearest event's hours. This keeps the scorer stateless and testable.

### 4.2 `completion/matcher.py` — Calendar Completion Evidence

The existing matcher works with `SourceItem` objects. Calendar events are `Event` objects, not `SourceItem` — different schema.

**Approach:** Don't force events through `find_matching_commitments()`. Instead, add a parallel function:

```python
def calendar_completion_evidence(
    link: CommitmentEventLink,
    event: Event,
    commitment: Commitment,
) -> CompletionEvidence | None:
```

This converts a `completion_hint` link into a `CompletionEvidence` object with `evidence_strength="moderate"` and `source_type="meeting"`. The completion sweep can then process these alongside source-item evidence.

Alternatively (simpler): the `calendar_matcher.py` itself writes a `CommitmentSignal` with `signal_role="progress"` or `signal_role="delivery"` when creating `completion_hint` links. This uses the existing signal infrastructure. **I recommend this approach** — it's simpler and doesn't require modifying `completion/matcher.py`.

### 4.3 `observation_window.py` — Shorten Window for Imminent Meetings

The brief says "optionally shorten observation window when a related meeting is imminent."

**Approach:** In `observation_window.py`, add:

```python
def adjusted_window_hours(base_hours: float, nearest_event_hours: float | None) -> float:
    """Shorten observation window if a matched event is imminent."""
    if nearest_event_hours is None:
        return base_hours
    if nearest_event_hours <= 4:  # Event within 4 hours
        return min(base_hours, 1.0)  # Cap at 1 hour
    if nearest_event_hours <= 24:  # Event within 24 hours
        return min(base_hours, nearest_event_hours * 0.5)
    return base_hours
```

This is called during commitment creation/promotion when setting `observe_until`. It doesn't retroactively modify existing commitments — only new ones or on re-evaluation.

---

## 5. Migration Plan

Single Alembic migration:

```python
# Add metadata column to existing commitment_event_links table
op.add_column("commitment_event_links",
    sa.Column("metadata", postgresql.JSONB, nullable=True))

# Widen relationship CHECK constraint if one exists (verify first)
# The column is String(20) — "completion_hint" is 15 chars, fits.
# "deadline_hint" is 13 chars, fits. No schema change needed for length.
```

That's it. No new table. The `relationship` column is `String(20)` with no CHECK constraint in the ORM, so new values work immediately.

If Trinity prefers a separate table, the migration creates `event_commitment_links` as specified in the brief.

---

## 6. Celery Task Integration

In `app/tasks.py`, extend `sync_google_calendar()`:

```python
@celery_app.task(name="app.tasks.sync_google_calendar")
def sync_google_calendar() -> dict:
    # ... existing sync logic ...
    result = connector.sync(user_id)

    # NEW: trigger calendar matching after successful sync
    if result.get("status") == "synced":
        match_result = _run_calendar_matching(db, user_id)
        result["matching"] = match_result

    return result
```

The `_run_calendar_matching` helper:
1. Loads active commitments for the user
2. Loads recent/upcoming events (past 7 days + next 30 days)
3. Calls `CalendarMatcher().match(events, commitments)`
4. Persists new links, writes signals for completion_hints
5. Returns counts

---

## 7. API Endpoint

`GET /api/v1/commitments/{commitment_id}/calendar-links`

Returns:
```json
[
  {
    "id": "uuid",
    "event_id": "uuid",
    "event_title": "Pricing review with Sarah",
    "event_starts_at": "2026-04-02T14:00:00Z",
    "link_type": "context",
    "confidence": 0.72,
    "metadata": {"matched_on": ["topic:pricing", "person:Sarah"]}
  }
]
```

Add to existing `app/api/routes/commitments.py` since there's already an events sub-route (`GET /commitments/{id}/events`, `POST /commitments/{id}/events`). The new endpoint returns calendar-matcher links (filtered to `deadline_hint | completion_hint | context`) vs. the existing endpoint which returns `delivery_at` links.

**Alternative:** Merge into the existing `/events` endpoint with a `?link_type=` filter param. Simpler, no new route. **I recommend this approach.**

---

## 8. Questions & Concerns

### Q1: Extend existing table or create new table?
**Recommendation:** Extend `commitment_event_links` with a `metadata` JSONB column. Avoids table fragmentation. New relationship values (`deadline_hint`, `completion_hint`, `context`) coexist with `delivery_at`.
**Risk:** Low — existing queries filter on `relationship == "delivery_at"` and won't see new rows.

### Q2: Should completion_hint links write CommitmentSignals?
**Recommendation:** Yes. Write a signal with `signal_role="progress"` and `confidence` from the match score. This integrates naturally with the existing completion sweep without modifying `completion/matcher.py`.
**Risk:** Very low — signals are additive evidence.

### Q3: How aggressive should the generic event filter be?
**Recommendation:** Start conservative — blocklist common generic titles, penalize short titles, require confidence >= 0.50. Better to under-link than create noise. Can tune later.
**Risk:** Some legitimate events with generic-sounding titles (e.g., "1:1 with Sarah about pricing review") might get filtered. Mitigation: only filter exact/near-exact matches to the blocklist, not substring matches.

### Q4: Should calendar matching run synchronously inside the sync task or as a separate chained task?
**Recommendation:** Synchronously inside the sync task. Calendar sync already runs every 15 minutes and is lightweight. Adding matching (O(events × commitments) with small N for a single user) adds negligible time. A separate task adds complexity without benefit at current scale.

### Q5: Re-matching on every sync — idempotency?
**Concern:** Every 15-minute sync would re-score all event-commitment pairs. Need to handle this cleanly.
**Approach:** Check for existing links before creating duplicates. For confidence updates on existing links: only update if score changed by > 0.05 (avoid churn). For past events that have already generated completion signals: don't re-generate.

---

## 9. Test Plan

### Unit Tests (`tests/test_calendar_matcher.py`)

1. **Entity matching**
   - Event with attendee matching commitment's requester → high person overlap score
   - Event with attendee matching commitment's beneficiary → high person overlap score
   - No person overlap → 0 on person dimension

2. **Topic overlap**
   - Event title "Pricing review Q2" + commitment title "Review Q2 pricing proposal" → high Jaccard
   - Unrelated titles → low Jaccard, no link

3. **Confidence scoring**
   - High person + high topic overlap → confidence > 0.70
   - Only moderate topic overlap → confidence ~0.40, below threshold, no link
   - Person match + topic match → above threshold

4. **Generic event filtering**
   - "Team standup" → filtered, no links
   - "1:1" → filtered
   - "1:1 with Sarah about pricing" → NOT filtered (has substantive content)
   - "Focus time" → filtered

5. **Link type assignment**
   - Future event + commitment without deadline → `deadline_hint`
   - Future event + commitment with deadline → `context`
   - Past event → `completion_hint`

6. **Deduplication**
   - Same (event_id, commitment_id) pair already linked → skip
   - Different relationship type for same pair → skip (one link per pair)

### Integration Tests (`tests/test_calendar_matcher_integration.py`)

7. **Priority scorer boost**
   - Commitment with `context` link to event in 12h → urgency boost applied
   - Commitment with `context` link to event in 72h → no boost
   - Commitment with both `delivery_at` and `context` links → no double-counting

8. **Completion signal creation**
   - `completion_hint` link created → CommitmentSignal written with `signal_role="progress"`
   - Re-run matching → no duplicate signal

9. **Observation window shortening**
   - Commitment with matched event in 3h → window capped at 1h
   - Commitment with no matched events → default window unchanged

10. **End-to-end: sync triggers matching**
    - Mock calendar sync returning new events → matching runs → links created
    - Sync with no new events → matching runs but creates no new links

11. **Regression: existing flows unaffected**
    - `DeadlineEventLinker` still creates `delivery_at` links independently
    - `NudgeService` still queries only `delivery_at` links
    - Users without commitments → sync completes without errors

### Edge Cases

12. Event with NULL description → matching uses title only
13. Commitment with NULL context_tags → matching uses title/description only
14. Cancelled event → excluded from matching
15. Recurring event → each instance treated independently (via `external_id`)

---

## 10. File Change Summary

| File | Change |
|------|--------|
| `app/models/orm.py` | Add `metadata` JSONB column to `CommitmentEventLink` |
| `app/services/calendar_matcher.py` | **New** — matching service |
| `app/services/priority_scorer.py` | Add `context_proximity_hours` param to `score()` |
| `app/services/observation_window.py` | Add `adjusted_window_hours()` |
| `app/services/surfacing_runner.py` | Query context links, pass proximity to scorer |
| `app/connectors/google_calendar.py` | No changes (sync API unchanged) |
| `app/tasks.py` | Add matching call after sync in `sync_google_calendar()` |
| `app/api/routes/commitments.py` | Add `link_type` filter to existing events endpoint |
| `alembic/versions/` | Migration adding `metadata` column |
| `tests/test_calendar_matcher.py` | **New** — unit + integration tests |
