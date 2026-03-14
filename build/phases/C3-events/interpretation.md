# Phase C3 — Event Model + Calendar Integration: Interpretation

**Written by:** Claude Code
**Date:** 2026-03-14
**Stage:** STAGE 2 — INTERPRET

---

## What This Phase Does and Why

Phase C3 is the temporal intelligence upgrade for Rippled. The system currently knows *what* was committed but not *when delivery happens* in calendar terms. A commitment with `resolved_deadline = "Friday"` is just a text-extracted date — there's no connection to the actual meeting where delivery will be assessed, no awareness that the client call was cancelled, and no scoring bump as the event approaches.

C3 introduces three interlocking capabilities:

1. **First-class Event model** — separates points-in-time from obligation targets. A commitment can have multiple linked events (prep meeting + delivery meeting). Events are either *explicit* (synced from Google Calendar) or *implicit* (created from detected deadline phrases).

2. **Temporal scoring intelligence** — the priority scorer currently awards a staleness bonus for overdue commitments, but has no forward-looking temporal awareness. C3 adds proximity spikes as events approach, a counterparty multiplier based on who you're committing to, and delivery state modifiers (acknowledged, draft sent, etc.).

3. **Automated post-event resolution** — when a delivery event passes, the system scans for delivery signals and either confirms resolution or escalates for user review. This closes the loop without requiring the user to manually update every commitment.

The end state: Rippled surfaces the right commitments at the right time, with urgency that reflects real-world context (upcoming client call, cancelled meeting, delivery already acknowledged).

---

## Proposed Implementation

### Architecture Diagram (text)

```
INGESTION LAYER
─────────────────────────────────────────────────────────
Google Calendar API (every 15 min via Celery)
    ↓
GoogleCalendarConnector.sync(user_settings, db)
    ├── Upsert Event rows (event_type='explicit')
    ├── Handle cancellations → set status='cancelled', surface linked commitments
    └── Handle rescheduling → update starts_at, set rescheduled_from

SURFACING SWEEP (every 30 min, extended from existing)
─────────────────────────────────────────────────────────
run_surfacing_sweep(db)  ← existing entry point
    ↓
[NEW] DeadlineEventLinker.run(db)   ← called BEFORE scoring
    ├── For each active commitment with resolved_deadline and no delivery_at link:
    │   ├── Scan Events within ±24h of deadline
    │   │   ├── attendee overlap + keyword match → CommitmentEventLink (confidence ≥ 0.7)
    │   │   └── no match → create implicit Event + CommitmentEventLink
    └── writes commitment.counterparty_type + commitment.counterparty_email
         via CounterpartyExtractor (calls source_item lookup)
    ↓
[MODIFIED] classifier → score(classifier_result, commitment, proximity_hours)
    ├── existing: externality, timing, consequence, burden, confidence, staleness
    ├── NEW: proximity spike (linked delivery_at event approaching)
    ├── NEW: counterparty multiplier (commitment.counterparty_type)
    └── NEW: delivery state modifier (commitment.delivery_state)

PROMOTION PIPELINE (existing, extended)
─────────────────────────────────────────────────────────
run_clarification() → promote_candidate()  ← existing
    ↓
[NEW] CounterpartyExtractor.extract(candidate, source_item, db)
    └── writes commitment.counterparty_type + commitment.counterparty_email
        (called from run_clarification __init__.py after promote_candidate)

NUDGE TASK (every hour via Celery beat)
─────────────────────────────────────────────────────────
NudgeService.run(db)
    └── commitments with delivery_at event in next 25h
        → force surfaced_as='main', update priority_score, log SurfacingAudit

POST-EVENT RESOLVER (every hour at :30 via Celery beat)
─────────────────────────────────────────────────────────
PostEventResolver.run(db)
    └── events ended 0-48h ago with unresolved linked commitments
        → scan SourceItems for delivery signals
        → update delivery_state or escalate to main

API LAYER
─────────────────────────────────────────────────────────
GET  /api/v1/events                         ← new events router
GET  /api/v1/events/{id}
POST /api/v1/events
PATCH /api/v1/events/{id}
GET  /api/v1/integrations/google/auth       ← new integrations router
GET  /api/v1/integrations/google/callback
GET  /api/v1/integrations/google/status
DELETE /api/v1/integrations/google/disconnect
PATCH /api/v1/commitments/{id}/delivery-state   ← extend existing router
GET  /api/v1/commitments/{id}/events
POST /api/v1/commitments/{id}/events
```

---

### Key New Models

**`Event` (new table: `events`)**

```python
class Event(Base):
    __tablename__ = "events"

    id: Mapped[str]                        # UUID PK
    source_id: Mapped[str | None]          # FK → sources.id NULLABLE
    external_id: Mapped[str | None]        # Google Calendar event ID
    title: Mapped[str]                     # TEXT NOT NULL
    description: Mapped[str | None]        # TEXT NULLABLE
    starts_at: Mapped[datetime]            # TIMESTAMPTZ NOT NULL
    ends_at: Mapped[datetime | None]       # TIMESTAMPTZ NULLABLE
    is_recurring: Mapped[bool]             # BOOLEAN DEFAULT false
    recurrence_rule: Mapped[str | None]    # RRULE string (RFC 5545)
    event_type: Mapped[str]                # VARCHAR(20): 'explicit' | 'implicit'
    status: Mapped[str]                    # VARCHAR(20): 'confirmed' | 'cancelled' | 'tentative'
    cancelled_at: Mapped[datetime | None]
    rescheduled_from: Mapped[datetime | None]
    location: Mapped[str | None]
    attendees: Mapped[dict | None]         # JSONB: [{email, name, response_status}]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**`CommitmentEventLink` (new table: `commitment_event_links`)**

```python
class CommitmentEventLink(Base):
    __tablename__ = "commitment_event_links"

    id: Mapped[str]                        # UUID PK
    commitment_id: Mapped[str]             # FK → commitments.id ON DELETE CASCADE
    event_id: Mapped[str]                  # FK → events.id ON DELETE CASCADE
    relationship: Mapped[str]              # VARCHAR(20): 'delivery_at' | 'prep_at' | 'review_at'
    confidence: Mapped[Decimal | None]     # NUMERIC(4,3): 1.0 manual, scored for auto
    created_at: Mapped[datetime]
    # UNIQUE(commitment_id, event_id, relationship)
```

**New columns on `Commitment`:**

```python
delivery_state: Mapped[str | None]         # VARCHAR(30): draft_sent | acknowledged | rescheduled | partial | delivered | closed_no_delivery
counterparty_type: Mapped[str | None]      # VARCHAR(20): external_client | internal_manager | internal_peer | self
counterparty_email: Mapped[str | None]     # TEXT NULLABLE
post_event_reviewed: Mapped[bool]          # BOOLEAN DEFAULT false
```

**New columns on `UserSettings`:**

```python
google_access_token: Mapped[str | None]    # TEXT NULLABLE (Fernet-encrypted)
google_refresh_token: Mapped[str | None]   # TEXT NULLABLE (Fernet-encrypted)
google_token_expiry: Mapped[datetime | None]  # TIMESTAMPTZ NULLABLE
```

**New enum type (PostgreSQL): none required** — `event_type`, `status`, `relationship`, `delivery_state`, `counterparty_type` are all `VARCHAR` columns (not PostgreSQL ENUMs). This avoids the ALTER TYPE complexity and matches the WO spec which uses VARCHAR for these.

**Migration name:** `add_event_model_c3`

---

### Service Flow

#### `GoogleCalendarConnector` (`app/connectors/google_calendar.py`)

```
GoogleCalendarConnector(settings, db)
    .sync(user_id)
        → load UserSettings for user_id
        → if no tokens: return (no-op)
        → if token expired: refresh via google-auth-oauthlib, update UserSettings
        → fetch events: calendar.events().list(timeMin=now, timeMax=now+30d)
        → for each Google event:
            → upsert Event row by external_id
            → if existing status != cancelled and new status = cancelled:
                → _handle_cancellation(event, db)
            → if starts_at changed:
                → set rescheduled_from = old starts_at, update starts_at
        → expand recurring events: store one row per instance
```

#### `DeadlineEventLinker` (`app/services/event_linker.py`)

```
DeadlineEventLinker.run(db, user_id)
    → query: commitments where resolved_deadline IS NOT NULL
              AND lifecycle_state IN active_states
              AND NOT EXISTS (CommitmentEventLink where relationship='delivery_at')
    → for each commitment:
        → scan_window = [resolved_deadline - 24h, resolved_deadline + 24h]
        → candidates = Events where starts_at IN scan_window AND status != 'cancelled'
        → for each candidate:
            → score = _match_score(commitment, event)
            → if score >= 0.7: create CommitmentEventLink (relationship='delivery_at', confidence=score)
        → if no match found:
            → create implicit Event (event_type='implicit', source_id=NULL)
            → create CommitmentEventLink (relationship='delivery_at', confidence=1.0)
```

Match scoring:
- Attendee email overlap with `commitment.counterparty_email`: +0.4
- Keyword overlap (commitment title tokens ∩ event title tokens, Jaccard ≥ 0.3): +0.4
- Time proximity (within 2h vs within 24h): +0.2 / +0.1

#### `CounterpartyExtractor` (`app/services/event_linker.py`, same module)

```
CounterpartyExtractor.extract(commitment, source_item) -> None
    → if source_item is None: return (no counterparty data)
    → sender_email = source_item.sender_email
    → if sender_email == user_email (from User lookup): counterparty_type = 'self'
    → elif is_external_participant(sender_email): counterparty_type = 'external_client'
    → elif sender_email in manager_list (settings.internal_managers, comma-sep): counterparty_type = 'internal_manager'
    → else: counterparty_type = 'internal_peer'
    → write commitment.counterparty_type, commitment.counterparty_email
```

This reuses the existing `participant_classifier.is_external_participant()` function.

#### Modified `score()` in `priority_scorer.py`

The `score()` function currently takes `(classifier_result, commitment)`. To add proximity awareness without giving the scorer a DB dependency, the surfacing pipeline pre-computes `proximity_hours` and passes it in via an extended signature:

```python
def score(
    classifier_result: ClassifierResult,
    commitment,
    proximity_hours: float | None = None,  # NEW: hours until next delivery_at event
) -> int:
```

`surfacing_runner.py` must query for the nearest `delivery_at` event for each commitment before calling `score()`. This is done in a pre-pass: one bulk query for all event links of active commitments, keyed by commitment_id.

Score additions:
```
proximity_spike(proximity_hours):
    proximity_hours >= 72:   return 0
    24 <= hours < 72:        return 10
    1 <= hours < 24:         return 20
    0 <= hours < 1:          return 35
    hours < 0 (post-event):  return 40 (decays: max(0, 40 - (abs_hours/48)*40))

counterparty_multiplier(counterparty_type):
    'external_client':  1.4
    'internal_manager': 1.2
    'internal_peer':    1.0
    'self':             0.8
    None:               1.0

delivery_state_modifier(delivery_state):
    'acknowledged':  -5
    'draft_sent':    -10
    'rescheduled':   -5
    'partial':       -8
    others / None:    0
```

Final formula: `(base_score + proximity_spike + delivery_state_modifier) * counterparty_multiplier`, capped at 100.

#### `NudgeService` (`app/services/nudge.py`)

```
NudgeService.run(db)
    → query: commitments joined to CommitmentEventLink (relationship='delivery_at')
             joined to Event (starts_at BETWEEN now AND now+25h)
             WHERE commitment.delivery_state NOT IN ('delivered', 'closed_no_delivery', 'draft_sent')
             AND commitment.lifecycle_state IN active_states
    → for each:
        → if commitment.surfaced_as != 'main': update to 'main', log SurfacingAudit
        → recompute priority_score via scorer (with fresh proximity_hours)
```

#### `PostEventResolver` (`app/services/post_event_resolver.py`)

```
PostEventResolver.run(db)
    → query: events where ends_at BETWEEN now-48h AND now
             joined to CommitmentEventLink (relationship='delivery_at')
             joined to Commitment WHERE delivery_state NOT IN terminal states
             AND post_event_reviewed = false
    → for each commitment+event pair:
        → scan SourceItems: occurred_at > event.ends_at, same counterparty email, limit 20
        → signal_type = _detect_delivery_signal(source_items, commitment)
        → if signal_type == 'full': commitment.delivery_state = 'delivered'
        → elif signal_type == 'draft': commitment.delivery_state = 'draft_sent'
        → elif signal_type == 'ack': commitment.delivery_state = 'acknowledged'
        → elif time_since_event > 2h AND no_signal:
            → commitment.post_event_reviewed = false  (stays false)
            → force surfaced_as='main' with elevated score, log SurfacingAudit
        → commitment.post_event_reviewed = true (once processed either way)
```

---

### API Routes

#### `app/api/routes/events.py` (new)

```
GET  /events              → list[EventRead] (next 30 days, with linked_commitment_count)
GET  /events/{id}         → EventRead + linked commitments
POST /events              → create implicit Event manually → EventRead (201)
PATCH /events/{id}        → update (reschedule/cancel) → EventRead
```

#### `app/api/routes/integrations.py` (new)

```
GET    /integrations/google/auth          → RedirectResponse to Google OAuth consent
GET    /integrations/google/callback      → handle code exchange, store tokens, return status
GET    /integrations/google/status        → {connected: bool, expiry: datetime | None}
DELETE /integrations/google/disconnect    → revoke + clear tokens from UserSettings
```

#### `app/api/routes/commitments.py` (extended)

```
PATCH /commitments/{id}/delivery-state   → body: {state, note?} → CommitmentRead
GET   /commitments/{id}/events           → list[CommitmentEventLinkRead]
POST  /commitments/{id}/events           → body: {event_id, relationship} → CommitmentEventLinkRead (201)
```

Both new routers are registered in `app/main.py` using the existing pattern.

---

## Integration Points with Existing Components

### `surfacing_runner.py`

Two insertions:

1. **Before the commitment loop:** call `DeadlineEventLinker(db).run(user_id=None)` to ensure all active commitments have event links before scoring. This is a bulk operation — one call per sweep.

2. **Pre-compute event proximity map:** before the per-commitment scoring loop, execute one query:
   ```sql
   SELECT cel.commitment_id, MIN(e.starts_at)
   FROM commitment_event_links cel
   JOIN events e ON e.id = cel.event_id
   WHERE cel.relationship = 'delivery_at'
     AND e.status = 'confirmed'
     AND cel.commitment_id = ANY(:ids)
   GROUP BY cel.commitment_id
   ```
   Build `proximity_map: dict[str, float]` (commitment_id → hours_until_event). Pass to `score()` per commitment.

3. **Pass `proximity_hours` to `score()`** via updated call signature.

### `tasks.py`

Three new tasks added:
- `sync_google_calendar()` — every 15 min cron `"*/15 * * * *"`
- `run_pre_event_nudge()` — every hour cron `"0 * * * *"`
- `run_post_event_resolution()` — every hour at :30 cron `"30 * * * *"`

Follow existing pattern: guard clause checking feature flag, `get_sync_session()`, delegate to service.

### `priority_scorer.py`

`score()` gets a new optional parameter `proximity_hours: float | None = None`. All existing tests pass because the default is `None` (no proximity spike). Existing callers in tests don't need updating.

The `_WEIGHTS` dict comment block is updated to document the three new dimensions.

### `promoter.py` (indirect via `run_clarification`)

`promote_candidate()` itself is NOT modified — doing so would require a DB session to load the source item, which the promoter doesn't currently need. Instead, `run_clarification()` (the `__init__.py` orchestrator) calls `CounterpartyExtractor` after `promote_candidate()` returns, before the session flush. The extractor receives the commitment, the source item (loaded by the clarifier which already has DB access), and writes the two new columns directly.

---

## Open Questions with Recommended Answers

### Q1: OAuth token storage approach

**Issue:** Where and how to store Google OAuth tokens (access_token, refresh_token, expiry) securely.

**Options:**
- (A) New columns on `user_settings` (VARCHAR, Fernet-encrypted at write/read) — WO spec
- (B) Store as a Google Calendar `Source` row with `credentials` JSONB (existing encrypted JSONB pattern)
- (C) Separate `oauth_tokens` table

**Recommendation: Option A with a small refactor of `credentials_utils.py`.**

The WO explicitly calls for columns on `user_settings`. The existing encryption is in `credentials_utils.py` with private `_get_cipher()`. To avoid duplication, expose two new public helpers in that module:

```python
def encrypt_value(value: str) -> str | None: ...
def decrypt_value(value: str) -> str | None: ...
```

These use the same `_get_cipher()` Fernet instance. Call them in `GoogleCalendarConnector` when writing tokens to `user_settings`, and in the OAuth callback endpoint. This avoids creating a Source row for the calendar (which would require extending the `source_type` ENUM) while keeping the encryption pattern consistent.

**Why not Option B:** Creating a Source row would require adding `google_calendar` to the `_source_type` PostgreSQL ENUM. Altering PostgreSQL ENUMs cannot be rolled back within a transaction. The WO says `event.source_id` is nullable — we can store `source_id=NULL` for now and link later if needed. Avoid the ENUM migration risk.

### Q2: How to handle `google_calendar_enabled=False` gracefully

**Issue:** The flag is a killswitch for the connector but should not crash if unconfigured (no OAuth client ID, no tokens).

**Recommendation:** Three-layer guard in `sync_google_calendar()` task:
1. `if not settings.google_calendar_enabled: return {"status": "skipped"}`
2. `if not settings.google_oauth_client_id: return {"status": "skipped", "reason": "oauth not configured"}`
3. Load `user_settings` — `if not user_settings or not user_settings.google_refresh_token: return {"status": "skipped", "reason": "user not authenticated"}`

The OAuth flow endpoints (`/integrations/google/auth` etc.) also check `google_calendar_enabled` at the route level and return `503 Service Unavailable` with a clear message if the feature flag is off. This prevents confusing 500 errors if someone hits the endpoint before the feature is configured.

The `DeadlineEventLinker` and `NudgeService` are **not** gated on `google_calendar_enabled` — they work with both explicit and implicit events, so they run regardless.

### Q3: How CounterpartyExtractor plugs into the promotion pipeline

**Issue:** The WO says "runs as part of the commitment promotion pipeline" but `promoter.py` currently takes `(candidate, db, analysis)` and doesn't receive a SourceItem. Modifying the promoter signature could break existing tests.

**Recommendation:** Call `CounterpartyExtractor` from `run_clarification()` in `app/services/clarification/__init__.py`, **after** `promote_candidate()` returns but **before** `db.flush()`.

```python
# In run_clarification():
commitment = promote_candidate(candidate, db, analysis)

# NEW: enrich counterparty
source_item = None
if candidate.originating_item_id:
    source_item = db.get(SourceItem, candidate.originating_item_id)
CounterpartyExtractor(settings).extract(commitment, source_item, user)
# then db.flush() as before
```

This approach:
- Does not modify `promote_candidate()` or its tests
- Reuses the DB session already open in `run_clarification()`
- Runs exactly once at promotion time (not on every surfacing sweep)
- Falls back gracefully if `originating_item_id` is None

The extractor uses `participant_classifier.is_external_participant()` (already exists) for the `external_client` classification and `settings.internal_domains` for the internal classification.

For `internal_manager` detection: introduce a new config field `internal_managers: str = ""` (comma-separated email list). If sender email is in this list → `internal_manager`. If domain is internal but not in managers list → `internal_peer`. Simple, zero-dependency, no external service needed for MVP.

### Q4: Scorer signature change backward compatibility

**Issue:** The existing 412 tests call `score(classifier_result, commitment)` without `proximity_hours`. Adding a keyword argument breaks nothing, but the surfacing runner's inner loop needs to pre-fetch event data — adding a bulk query to every sweep.

**Recommendation:** Pre-fetch is worth it. The proximity spike is the core value of C3. The bulk query (one JOIN across commitment_event_links + events) is O(n) where n = active commitments, and surfaces are already computed every 30 minutes. Performance is not a concern at current scale.

Use `proximity_hours: float | None = None` default so existing test calls are untouched.

### Q5: Single-user MVP assumption for Google Calendar sync

**Issue:** The `sync_google_calendar` task follows the existing single-user pattern (like `send_daily_digest`). Is this correct?

**Recommendation:** Yes — match the existing digest pattern. The task reads `settings.digest_to_email` to find the user (or we can add `google_calendar_user_email: str = ""` config field that defaults to `digest_to_email` if empty). For MVP, one user is the assumption throughout. The task fetches `UserSettings` for that user and checks for tokens.

This is lower risk than building a multi-user loop that we can't test properly.

---

## Risk Flags

### Risk 1: PostgreSQL ENUM for `source_type` — **AVOID extending**

The existing `_source_type` ENUM (`meeting`, `slack`, `email`) would need a `google_calendar` value if we create a Source row for the calendar connector. Altering PostgreSQL ENUMs:
- Cannot be rolled back within a transaction
- Requires `CREATE TYPE ... AS ENUM` + `ALTER TYPE ... ADD VALUE` or full type replacement
- The existing codebase already hit ENUM issues (see git: "fix(orm): use postgresql.ENUM for all enum-typed columns")

**Mitigation:** Do NOT create a Source row for Google Calendar. `Event.source_id` is nullable — store `NULL`. If a Source row is needed in the future, add `google_calendar` to the enum in a dedicated migration.

### Risk 2: `score()` is used in tests without proximity — **Low risk, handle with default**

48 tests currently call `score()` directly (inferred from 412 total, ~10% scorer tests). Adding `proximity_hours: float | None = None` as an optional parameter preserves all existing call sites. Verified the scorer has no existing proximity logic to conflict with.

### Risk 3: `delivery_state` column naming collision with lifecycle concepts

`Commitment.lifecycle_state` already has `delivered` as a value. Adding `commitment.delivery_state = 'delivered'` (a separate column) creates semantic confusion: a commitment could have `lifecycle_state='active'` and `delivery_state='delivered'` simultaneously, which is contradictory.

**Mitigation:** The `PostEventResolver` and `NudgeService` must treat `delivery_state='delivered'` as a signal to transition `lifecycle_state` to `'delivered'` as well, if not already. Add this transition logic to `PostEventResolver`. Document in code comments that `delivery_state` tracks the *delivery evidence signal* while `lifecycle_state` tracks the *commitment lifecycle state* — they converge but are set by different mechanisms.

### Risk 4: `run_surfacing_sweep` transaction scope with `DeadlineEventLinker`

The linker creates new Event and CommitmentEventLink rows inside the same session as the surfacing sweep. The current sweep calls `db.flush()` only after all commitments are processed. If the linker creates rows mid-sweep, they'll be visible to the scorer in the same transaction but not yet committed — this is fine for the proximity pre-fetch because we want the freshly linked events to be scored immediately.

**Verification needed at build time:** ensure the pre-fetch query runs *after* `DeadlineEventLinker.run()` in the same session scope.

### Risk 5: Google Calendar recurring event expansion

The WO says "store recurrence_rule, one row per instance (expand occurrences)." Expanding recurring events for 30 days ahead from a Google Calendar API response produces potentially many rows (e.g., daily standup = 30 rows). Google's API returns recurring instances already expanded when using `singleEvents=True` in the list query.

**Recommendation:** Use `singleEvents=True` in the Google Calendar API call. This returns one row per occurrence, already expanded. Store the `recurrence_rule` field for reference but do not implement RFC 5545 RRULE parsing server-side. This simplifies the connector considerably.

### Risk 6: `CounterpartyExtractor` and meeting source items

Meeting source items (`source_type='meeting'`) have a different structure — they may have multiple attendees but no clear sender. The extractor's logic (sender = counterparty) doesn't apply cleanly.

**Mitigation:** For meeting source items, use the first non-user attendee in `source_item.recipients` JSONB as the counterparty email. If `recipients` is empty or all internal, fall back to `counterparty_type='internal_peer'`.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/orm.py` | MODIFY — add Event, CommitmentEventLink classes; add 4 new columns to Commitment; add 3 columns to UserSettings |
| `migrations/versions/XXX_add_event_model_c3.py` | NEW — Alembic migration |
| `app/connectors/google_calendar.py` | NEW — GoogleCalendarConnector |
| `app/connectors/shared/credentials_utils.py` | MODIFY — add `encrypt_value()` / `decrypt_value()` public helpers |
| `app/services/event_linker.py` | NEW — DeadlineEventLinker + CounterpartyExtractor |
| `app/services/nudge.py` | NEW — NudgeService |
| `app/services/post_event_resolver.py` | NEW — PostEventResolver |
| `app/services/priority_scorer.py` | MODIFY — add proximity_spike, counterparty_multiplier, delivery_state_modifier |
| `app/services/surfacing_runner.py` | MODIFY — call DeadlineEventLinker, pre-fetch proximity map, pass proximity_hours to score() |
| `app/services/clarification/__init__.py` | MODIFY — call CounterpartyExtractor after promote_candidate() |
| `app/tasks.py` | MODIFY — add sync_google_calendar, run_pre_event_nudge, run_post_event_resolution tasks + beat schedule entries |
| `app/api/routes/events.py` | NEW — events router |
| `app/api/routes/integrations.py` | NEW — Google OAuth endpoints |
| `app/api/routes/commitments.py` | MODIFY — add delivery-state, events sub-routes |
| `app/core/config.py` | MODIFY — add 5 Google Calendar + 1 internal_managers settings fields |
| `app/main.py` | MODIFY — register events and integrations routers |
| `requirements.txt` | MODIFY — add google-api-python-client, google-auth-oauthlib, google-auth-httplib2 |

---

## Estimated Test Count and Breakdown

### Unit tests

| Test class | Tests | What's covered |
|------------|-------|----------------|
| `TestDeadlineEventLinker` | 8 | match on attendees, match on keywords, no-match → synthetic implicit event, confidence threshold boundary (0.69 rejected, 0.70 accepted), ±24h window edge, commitment with existing link skipped, cancelled event excluded, empty commitment set |
| `TestCounterpartyExtractor` | 6 | external_client (different domain), internal_manager (in manager list), internal_peer (same domain, not manager), self (sender = user email), null sender_email, meeting source type (recipients fallback) |
| `TestTimingAwareScorer` | 11 | proximity at T-72+ (0 bonus), T-48 (+10), T-24 (+20), T-1h (+35), T+0 (post-event +40), T+48h (decayed ~0), counterparty ×1.4, ×1.2, ×1.0, ×0.8, delivery state modifiers (acknowledged, draft_sent, rescheduled, partial), combined multiplier + spike |
| `TestNudgeService` | 5 | correct selection (25h window), shortlist → main promotion, already main (no audit row), delivered state skipped, draft_sent skipped |
| `TestPostEventResolver` | 7 | email after event → delivered, email with draft language → draft_sent, recap source item → acknowledged, no signal after 2h → escalate to main, no signal within 2h → hold (post_event_reviewed stays false), >48h boundary excluded, post_event_reviewed=true skipped |
| `TestEventCancellationHandler` | 4 | cancelled event surfaces linked commitment, cancelled with no links (no-op), already delivered commitment not re-surfaced, multiple linked commitments all surfaced |
| **Unit subtotal** | **41** | |

### Integration tests

| Test class | Tests | What's covered |
|------------|-------|----------------|
| `TestGoogleOAuthFlow` | 5 | GET /auth → redirect contains correct scope, GET /callback success stores tokens, GET /callback with bad code → 400, GET /status connected, DELETE /disconnect clears tokens |
| `TestEventsAPI` | 6 | GET /events returns list, GET /events/{id} with linked commitments, POST /events creates implicit event, PATCH /events/{id} reschedule updates rescheduled_from, PATCH /events/{id} cancel, GET /events with no events → empty list |
| `TestCommitmentDeliveryState` | 4 | PATCH /delivery-state valid transition, invalid state value → 422, commitment not found → 404, GET /commitments/{id}/events, POST /commitments/{id}/events manual link |
| `TestFullPipeline` | 4 | sync creates explicit Event, DeadlineEventLinker links commitment to event, nudge fires for T-24h event, post-event resolver escalates unresolved |
| **Integration subtotal** | **19** | |

### **Total: ~60 new tests** (exceeds 50-test minimum with comfortable margin)

---

## Summary

Phase C3 is well-bounded but has meaningful integration surface. The key design decisions are:

1. **Avoid ENUM extension** — store OAuth tokens in `user_settings` columns, keep `Event.source_id` nullable, no `google_calendar` source type needed for MVP.
2. **Keep scorer pure** — pre-compute proximity in `surfacing_runner`, pass as parameter. No DB calls inside `score()`.
3. **CounterpartyExtractor after promotion, not inside** — call from `run_clarification()` orchestrator to avoid promoter signature change.
4. **Use `singleEvents=True`** for Google Calendar API to avoid RRULE parsing complexity.
5. **Delivery state + lifecycle state are parallel** — PostEventResolver converges them by also transitioning lifecycle_state when delivery is confirmed.

No changes to existing detection, clarification, completion, or digest services beyond what is listed. All 412 existing tests should continue to pass.
