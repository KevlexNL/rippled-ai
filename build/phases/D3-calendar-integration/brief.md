# Phase D3 — Deeper Calendar Integration

**Phase:** D3-calendar-integration
**Date:** 2026-04-01
**Status:** QUEUED
**Brief References:** Brief 4 (Source Model — Open Questions), Brief 7 (MVP Scope), Brief 10 (Completion Detection — Future)

---

## Goal

Extend the existing Google Calendar connector from a basic event sync into a commitment-aware integration. Currently the connector (`app/connectors/google_calendar.py`) syncs events into the local events table but calendar data is not used as commitment intelligence — it doesn't feed detection, clarification, completion, or deadline evidence. This phase makes calendar events a supporting evidence source that strengthens commitment understanding: detecting deadline proximity from upcoming meetings, inferring completion from past meetings, and linking calendar events to existing commitments.

---

## Scope (what's included)

- **Calendar-as-deadline-evidence:** When a calendar event title/description matches an active commitment's topic or entities, use the event time as supporting deadline evidence (suggested due date if none exists, corroboration if one does)
- **Calendar-as-completion-evidence:** Past calendar events that match active commitments can serve as moderate completion evidence (e.g., "Pricing review" meeting occurred → "review pricing" commitment may be progressing/delivered)
- **Calendar-as-context:** Upcoming calendar events provide context for commitment priority — a commitment related to a meeting happening tomorrow should score higher in urgency
- **Event-commitment linking:** New `event_commitment_links` table to track associations between events and commitments with link type (deadline_hint, completion_hint, context)
- **Matching service:** New `app/services/calendar_matcher.py` that runs after calendar sync to find matches between events and active commitments using entity/topic overlap
- **Celery task integration:** Extend the calendar sync task to trigger matching after sync completes
- **API additions:** Endpoint to view calendar-linked evidence for a commitment

---

## Out of Scope

- Calendar as a primary commitment **origin** source (calendar events don't create new commitments)
- Calendar write-back (creating/modifying calendar events based on commitments)
- Non-Google calendar providers (Apple, Outlook) — Google only for now
- Calendar invite attendance as ownership signal
- Timezone-aware working hours calculation from calendar

---

## Technical Approach

**Database:**
New `event_commitment_links` table:
```
id: UUID PK
event_id: FK -> events.id
commitment_id: FK -> commitments.id
link_type: TEXT ('deadline_hint' | 'completion_hint' | 'context')
confidence: DECIMAL
metadata: JSONB (matching details)
created_at: TIMESTAMPTZ
```

**Matching service:**
`app/services/calendar_matcher.py` with:
- `match_events_to_commitments(events, commitments) -> list[EventCommitmentLink]`
- Uses entity overlap (people, topics, deliverables) between event title/description and commitment description/context_tags
- Confidence scoring based on: exact entity match (high), topic keyword overlap (moderate), participant overlap (moderate)
- Runs in the Celery calendar sync task after event upsert

**Integration with existing services:**
- `priority_scorer.py`: boost urgency score when a related calendar event is within 48 hours
- `completion/matcher.py`: accept calendar events as moderate completion evidence
- `observation_window.py`: optionally shorten observation window when a related meeting is imminent

**API:**
- `GET /api/v1/commitments/{id}/calendar-links` — returns linked calendar events with link type and confidence

---

## Success Criteria

- [ ] Calendar events with matching topics/entities are linked to active commitments after sync
- [ ] A commitment with a matching upcoming event gets a deadline hint if no deadline exists
- [ ] A commitment with a matching past event gets moderate completion evidence
- [ ] Priority scorer boosts urgency when a related meeting is within 48 hours
- [ ] Links are visible via API endpoint
- [ ] Matching does not create false links for generic event titles ("Team standup", "1:1")
- [ ] Calendar sync continues to work for users without commitments (no regressions)
- [ ] Tests cover: entity matching, confidence scoring, deadline hint assignment, completion evidence, generic event filtering

---

## Files Likely Affected

- `app/models/orm.py` — new `EventCommitmentLink` model
- `app/connectors/google_calendar.py` — trigger matching after sync
- `app/services/calendar_matcher.py` — new matching service
- `app/services/priority_scorer.py` — calendar-aware urgency boost
- `app/services/completion/matcher.py` — calendar completion evidence
- `app/api/routes/commitments.py` or new `calendar_links.py` — API endpoint
- `app/tasks.py` — extend calendar sync task
- `alembic/versions/` — new migration
- `tests/` — new test files for calendar matching

---

## Dependencies

- Google Calendar connector must be functional (exists from Phase C3)
- Commitments must have entities/context_tags populated (exists from entity extraction fix)
- No dependency on D1 or D2

---

## Estimated Effort

2-3 days. The matching logic requires careful entity overlap scoring to avoid false positives. The calendar connector infrastructure exists, but integrating calendar data into the scoring, completion, and observation pipelines touches multiple services.

---

## Brief References

**Brief 4 — Source Model (Open Questions):**
> "calendar as a source of due/progress/completion evidence" (Section: Open questions for later phases)

**Brief 7 — MVP Scope:**
> "Google Calendar connector exists (early stage)" — listed as ahead-of-MVP, with "deeper integration TBD"

**Brief 10 — Completion Detection (Future):**
> "calendar-based completion evidence" (Section: Open questions / future extension)
> "calendar events" listed under "Future artifact sources" for completion detection

The existing connector syncs events but doesn't feed them into commitment intelligence. This phase bridges that gap.
