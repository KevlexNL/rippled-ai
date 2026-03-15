# C6 Investigation Findings

> Written during STAGE 2 — INTERPRET, 2026-03-15.
> Do not modify during BUILD.

---

## Issue #2 — Calendar events not appearing as signals

### Pipeline trace

`GoogleCalendarConnector.sync(user_id)` in `app/connectors/google_calendar.py`:
- Fetches events from Google Calendar API (30-day window, singleEvents=True)
- Calls `_upsert_event()` for each raw event
- Creates/updates `Event` rows with: `title`, `description`, `starts_at`, `ends_at`, `attendees`, `location`, `status`, `is_recurring`, `recurrence_rule`
- **Does NOT set `source_id` on the Event row** — the `source_id` column is nullable and left null

The `Event` ORM model (`app/models/orm.py`):
- Has `source_id` (nullable FK to sources.id) — not populated by the calendar sync
- **Has NO `user_id` column** — events are not user-scoped in the DB schema
- Used by `DeadlineEventLinker` and `NudgeService` to link with existing commitments

`app/services/surfacing_runner.py` (`run_surfacing_sweep`):
- Calls `DeadlineEventLinker.run()` — links existing Commitments to Events via `CommitmentEventLink` (relationship=`delivery_at`)
- Uses `_build_proximity_map()` to calculate hours until delivery events
- Passes `proximity_hours` to `route()` for priority scoring
- **No step that reads Event.description and runs commitment detection**

`app/models/orm.py` — `CommitmentCandidate`:
- `originating_item_id` → FK to `source_items.id` (NOT events)
- No Event-sourced detection path exists anywhere in the codebase

**GAP CONFIRMED**: Calendar events are exclusively used as deadline proxies for existing commitments (via `CommitmentEventLink`). Event descriptions are never fed into commitment detection. No SourceItem is ever created from an Event.

### Secondary gap: Event table is not user-scoped

`GET /api/v1/events` (`app/api/routes/events.py`):
- Receives `user_id` from auth dependency but does NOT filter by user_id
- Returns ALL events across ALL users (pre-existing bug from C3)
- `Event` table has no `user_id` column — filtering by user requires a JOIN via `CommitmentEventLink` (which requires a pre-existing commitment link) or via `source_id` (which isn't populated)

**Result**: Even surfacing events in the UI directly requires a DB migration to add `user_id` to the `events` table AND a connector fix to populate it on sync.

---

## Issue #7 — Multiple sources of same type

### ORM constraint check (`app/models/orm.py` — `Source`)

```python
class Source(Base):
    __tablename__ = "sources"
    id         # primary key
    user_id    # indexed, FK to users.id
    source_type
    provider_account_id
    ...
```
**No `UniqueConstraint` on `(user_id, source_type)`** in the ORM model. The DB schema does not enforce one-source-per-type.

### Setup endpoint behavior (`app/api/routes/sources.py`)

`POST /sources/setup/email`:
- Queries `SELECT Source WHERE user_id=? AND source_type='email'`
- If found → updates in place (upsert)
- If not found → creates new
- **Result**: Single email source per user, enforced at app layer only. Connecting a second email inbox OVERWRITES the first.

`POST /sources/setup/slack`:
- Queries `SELECT Source WHERE user_id=? AND source_type='slack'`
- Same upsert pattern
- **Result**: Single Slack workspace per user, enforced at app layer only. Connecting a second workspace OVERWRITES the first.

`POST /sources/setup/meeting`:
- Queries `SELECT Source WHERE user_id=? AND source_type='meeting' AND provider_account_id=?platform`
- **Result**: One row per platform per user (fireflies, otter, readai, custom are separate rows). Multiple meeting platforms ARE supported.

### Conclusion

| Source Type | Multiple Supported | Enforcement |
|-------------|-------------------|-------------|
| email       | NO                | App layer upsert (overwrites) |
| slack       | NO                | App layer upsert (overwrites) |
| meeting     | YES (per platform)| App layer upsert per platform |
| calendar    | N/A (OAuth tokens in UserSettings, no Source row) | — |

The UI should show "one connected — Reconnect" for email and Slack, not "Add another".

---

## Issue #10 — Slack ingestion pipeline

### Connector architecture

Slack uses the **Events API (webhook-driven)**, NOT polling. There is NO Celery beat task for Slack.

**Full flow** (when correctly configured):
1. Slack POSTs event to `POST /api/v1/webhooks/slack/events` (`app/api/routes/webhooks/slack.py`)
2. Handler verifies HMAC-SHA256 signature using per-source `signing_secret` (from Source.credentials) with fallback to global `SLACK_SIGNING_SECRET` env var
3. Acks immediately → dispatches `process_slack_event.delay(payload)` (Celery task, `app/tasks.py`)
4. `process_slack_event` task:
   - Looks up `Source` by `team_id` from payload
   - Calls `normalise_slack_event()` → `SourceItemCreate`
   - Calls `ingest_item()` → creates `SourceItem` row + **enqueues `detect_commitments.delay(source_item.id)`**
5. `detect_commitments` runs `run_detection()` → creates `CommitmentCandidate` rows
6. Detection pipeline proceeds normally

**Detection IS enqueued** — `ingestor.py:90` confirms `_enqueue_detection(source_item.id)` is called after every successful Slack ingest.

### Filtered message types (`app/connectors/slack/normalizer.py`)

Normalizer accepts:
- `type='message'` only (rejects `message_changed`)
- Subtypes: `None`, `file_share`, `message_replied`
- Rejects: bot messages, `bot_id` set, `subtype='bot_message'`

### Root cause of #10: setup/configuration gap

The webhook URL for Slack Event Subscriptions must be configured in the Slack API dashboard. The onboarding screen (step 2) tells users to configure Event Subscriptions but **never shows them the webhook URL**. Users don't know what URL to put in.

The webhook URL is: `{API_BASE}/api/v1/webhooks/slack/events`

Additionally: the Slack bot must be invited to channels to receive channel messages (`/invite @Rippled`). Without this, only DMs arrive. This connects to issue #5.

There is no polling fallback — if Event Subscriptions aren't configured, zero Slack messages arrive.

---

## Issue #6 — Disconnect sources

### Endpoint existence

`DELETE /api/v1/sources/{source_id}` EXISTS in `app/api/routes/sources.py`:

```python
@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id, user_id, db):
    source = ...
    if not source:
        raise HTTPException(status_code=404, ...)
    source.is_active = False
    source.updated_at = datetime.now(timezone.utc)
    # no await db.flush() — but get_db auto-commits, so this is fine
```

The endpoint sets `is_active=False` (soft-delete). `get_db` in `app/db/deps.py` does `await session.commit()` on success, so the change IS persisted even without explicit flush.

**Cascade behavior**: No DB cascade triggered (hard delete would cascade SourceItems, but soft-delete leaves all data intact). Appropriate — stopping ingestion without destroying history.

**Separate path for Google Calendar**: Disconnect goes through `DELETE /api/v1/integrations/google/disconnect` (revokes OAuth tokens + clears UserSettings). Google Calendar does NOT have a Source row — it uses UserSettings for tokens.

### Frontend state

`IntegrationsSettingsScreen.tsx` currently shows:
- Google Calendar: connected/disconnect UI (works via integrations API) ✓
- Daily Digest: email toggle + address ✓
- **Slack**: NOT shown at all ✗
- **Email (IMAP)**: NOT shown at all ✗
- **Meetings (webhooks)**: NOT shown at all ✗

The screen does NOT call `GET /api/v1/sources`. The `list_sources` endpoint exists but has a default `limit=5` and does not filter by `is_active`.

---

## Other issues — findings during intake

### #1 — Homepage empty state bug

`Dashboard.tsx` queries only `surface/main`, `surface/shortlist`, `surface/clarifications`. When all three return empty arrays, `allCommitments.length === 0` shows the single empty state ("You're clear / Connect a source →"). There is NO distinction between:
- 0 sources connected + 0 commitments
- ≥1 source connected + 0 commitments surfaced yet

Dashboard does not call `GET /api/v1/sources` at all.

`list_sources` (`GET /api/v1/sources`) exists, does not filter by `is_active`, default `limit=5`.

### #3 — No refetch interval

`useQueries` in Dashboard.tsx has no `refetchInterval`. All three surface queries are static (one-time on mount).

### #4 — Webhook optional secret (meetings)

Meeting webhook handler (`_verify_meeting_auth`): if `settings.meeting_webhook_secret` is NOT configured globally, it falls back to X-User-ID auth (no secret verification). If it IS configured, the header is required.

**Gap**: The setup endpoint (`POST /sources/setup/meeting`) creates a per-source `webhook_secret` stored in `Source.credentials`. But the webhook handler NEVER looks up the per-source secret — it only checks the global env var. These two mechanisms are disconnected.

For Read.ai (which doesn't support secrets): if the global `MEETING_WEBHOOK_SECRET` is configured, Read.ai requests will fail because the header is required when global secret is set.

### #9 — No stats endpoint

`GET /api/v1/stats` does not exist. SourceItems exist grouped by source_type per user. Stats require COUNT queries on `source_items` WHERE `user_id=?` GROUP BY `source_type`.

### #5 / #11 — Copy gaps

Confirmed in OnboardingScreen.tsx:
- Step 2 (Slack): Shows setup instructions but no mention of `/invite @Rippled` after connection
- Step 1 (Email): No explanation of what access is requested, no "reads only, never sends" copy

No webhook URL is shown during Slack setup (step 4 of onboarding only shows meeting webhook URLs).
