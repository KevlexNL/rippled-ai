# C6 QA Fix Cycle — Interpretation

> STAGE 2 — INTERPRET complete. Written 2026-03-15.
> Trinity must review and approve before BUILD begins.

---

## Investigation Findings Summary

### #2 — Calendar signals (PIPELINE GAP — requires migration)

The calendar pipeline is structurally incomplete:
1. `GoogleCalendarConnector.sync()` creates `Event` rows ✓
2. `Event.description` is never fed into commitment detection ✗
3. `Event` table has **no `user_id` column** — events are not user-scoped ✗
4. `GoogleCalendarConnector._upsert_event()` does **not set `source_id`** on the Event row ✗
5. `GET /api/v1/events` doesn't filter by user_id (returns all users' events) ✗

**The fix is larger than the WO implies.** Before calendar events can be surfaced in the UI, two DB-level changes are required:
- Add `user_id` column to `events` table (migration + connector fix to populate it)
- Optionally: populate `source_id` on calendar-synced events

### #6 — Disconnect sources (BACKEND EXISTS, FRONTEND MISSING)

`DELETE /api/v1/sources/{id}` exists and works correctly (soft-delete via `is_active=False`, auto-committed). Google Calendar disconnects via a separate integrations endpoint.

The gap is entirely in the frontend: `IntegrationsSettingsScreen.tsx` doesn't call `GET /api/v1/sources` and shows nothing for Slack, email, or meetings.

### #7 — Multiple sources (NOT SUPPORTED for Slack/email)

The ORM has no uniqueness constraint but the setup endpoints enforce single-source via upsert for email and Slack. Multiple meeting platforms are allowed (one row per platform). The UI should reflect this: "one connected" + "Reconnect" for email/Slack, not "Add another".

### #10 — Slack ingestion (PIPELINE CORRECT, SETUP/CONFIGURATION GAP)

The full pipeline is wired correctly: Events API webhook → Celery → SourceItem → detect_commitments. The root issue is that the onboarding never shows the user the webhook URL to configure in Slack's Event Subscriptions dashboard. Without that URL configured, zero Slack events arrive. Additionally, without `/invite @Rippled` in channels, only DMs are received.

---

## Per-Issue Fix Plans

### #1 — Homepage empty state [FRONTEND, LOW RISK]

**Files changed**: `frontend/src/screens/Dashboard.tsx`, `frontend/src/api/sources.ts` (new or extend)

**Change**:
- Add a `useQuery` for `GET /api/v1/sources?limit=50` in Dashboard.tsx
- Derive `hasConnectedSources = (sources ?? []).some(s => s.is_active)`
- Render three distinct states instead of one:
  - `!hasConnectedSources && allCommitments.length === 0` → "Connect your first source" (current behavior)
  - `hasConnectedSources && allCommitments.length === 0` → "Scanning your sources…" (new state, see #8)
  - `hasConnectedSources && allCommitments.length > 0` → current commitment list (existing)
- Remove the "Connect a source →" link from the "You're clear" state; it should only appear when 0 sources are connected
- The `list_sources` endpoint returns all sources (including inactive); filter `is_active=true` client-side

**Note**: The `list_sources` endpoint default limit is 5. For the sources check, query `?limit=50` to safely cover users with many sources.

---

### #2 — Calendar signals [PIPELINE + BACKEND + MIGRATION, HIGH COMPLEXITY]

**Recommended approach: Option B — surface events directly in UI** (faster, more predictable for MVP)

Option A (run events through detection) requires: Event→SourceItem conversion, pipeline plumbing, and introduces new CommitmentCandidate noise from meeting titles. Deferred to a future phase.

**Files changed**:
- `alembic/versions/` — new migration: add `user_id` column to `events` table
- `app/models/orm.py` — add `user_id: Mapped[str | None]` to `Event`
- `app/connectors/google_calendar.py` — populate `user_id` on Event upsert (requires passing `user_id` to `_upsert_event`)
- `app/api/routes/events.py` — filter `list_events` by `user_id` (currently returns all users' events)
- `frontend/src/api/events.ts` (new) — `GET /api/v1/events`
- `frontend/src/screens/Dashboard.tsx` — render events as a separate "Upcoming" section

**Backend changes**:
1. Migration: `ALTER TABLE events ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE`
2. `Event` ORM: add `user_id` mapped column (nullable for backward compat with existing rows)
3. `GoogleCalendarConnector._upsert_event(raw, db, user_id)` — accept and store `user_id`
4. `GoogleCalendarConnector.sync(user_id)` — pass `user_id` into `_upsert_event`
5. `GET /events` — add `.where(Event.user_id == user_id)` filter (or return empty for null user_id rows)

**Frontend changes**:
- Dashboard: Add `useQuery(['events'])` for `GET /api/v1/events`
- When calendar is connected (`googleStatus.connected`) AND events exist: render a separate "Upcoming" section below the commitment list
- Event card: event title, starts_at (relative time), attendee count
- Keep it visually distinct from commitment cards (lighter style, no action buttons)
- No detection — just display upcoming events as deadline awareness

**Strategic decision required**: The WO says "approach decision during BUILD: if events have structured content, process through detection; if not, surface directly." I recommend direct surfacing (Option B) for MVP. Detection can be added in C7 if Kevin wants it. Trinity must confirm.

---

### #3 — Auto-refresh [FRONTEND, LOW RISK]

**Files changed**: `frontend/src/screens/Dashboard.tsx`

**Change**:
- Add `refetchInterval: 30_000` to all three `useQueries` queries (main, shortlist, clarifications)
- Add `refetchInterval: 30_000` to the sources query added in #1
- Add `staleTime: 25_000` to avoid unnecessary refetches
- Optional: add a subtle "updated N seconds ago" indicator using `dataUpdatedAt` from the query result

---

### #4 — Webhook optional secret (meetings) [BACKEND, MEDIUM RISK]

**Files changed**: `app/api/routes/webhooks/meetings.py`

**Current behavior**:
- If `settings.meeting_webhook_secret` is set globally → require `X-Rippled-Webhook-Secret` header
- If not → require `X-User-ID` only

**Problem**: Global env var and per-source credential are disconnected. Read.ai doesn't send secret headers.

**Fix approach** (per-source, no env var change required):
Change `_verify_meeting_auth` to:
1. Get `user_id` from `X-User-ID` header (required, no change)
2. Look up the user's meeting source from DB (by `user_id + source_type='meeting'`)
3. If source exists and `credentials.webhook_secret` is non-empty → verify `X-Rippled-Webhook-Secret` against it
4. If source has no webhook_secret (or source not found) → skip verification, accept payload
5. Remove dependency on global `settings.meeting_webhook_secret` for per-request verification (keep env var as config, not runtime guard)

**Implementation note**: This requires making `_verify_meeting_auth` async and injecting the DB session. The route handler already has `db: AsyncSession = Depends(get_db)` — pass it in.

**Backward compat**: All existing meeting sources created via setup have a `webhook_secret` in credentials. The change only relaxes verification for sources that don't have one. Read.ai users can reconnect their source via setup (which won't store a secret if omitted — but current setup ALWAYS generates one). The practical fix for Read.ai is: if the provider sends no header and the source has a secret, reject. If the provider sends no header and the source has no secret (new setup path), accept. Kevin may need to recreate the Read.ai source without a secret for full effect.

**Alternative (simpler, lower scope)**: Make global env var optional and document. If `MEETING_WEBHOOK_SECRET` is not set, accept all requests with valid X-User-ID. This is ALREADY the behavior. The actual fix needed: when a user sets up a meeting source with no secret (add a `no_secret` flag to setup UI), store empty credentials, and the webhook handler will skip verification. This is a frontend change to the meeting setup step.

**Decision for Trinity**: Full per-source approach vs. simpler flag-based approach. I recommend the flag-based approach for MVP speed.

---

### #5 — Slack channel invitation instructions [FRONTEND, LOW RISK]

**Files changed**: `frontend/src/screens/OnboardingScreen.tsx`, `frontend/src/screens/settings/IntegrationsSettingsScreen.tsx`

**OnboardingScreen changes** (step 2 — Slack):
- After `slackTestResult?.success` banner, show a "Step 2: Invite to channels" card
- Copy: "To receive signals from a channel, invite the Rippled bot: `/invite @Rippled`"
- Show even before `connectSlack` completes (preparatory instruction)
- After `connectedSources.includes('slack')` — show persistent reminder

**IntegrationsSettingsScreen changes** (after sources list is added for #6):
- For each Slack source, show an info block: "Invite the bot to any channel: `/invite @Rippled`"

**Also add the webhook URL to Slack onboarding** (related to #10):
- In OnboardingScreen step 2 setup instructions, add step 5: "In 'Event Subscriptions', enable events and enter your webhook URL: `{API_BASE}/api/v1/webhooks/slack/events`"
- The `API_BASE` is already available from `import.meta.env.VITE_API_URL`

---

### #6 — Integration management UI [FRONTEND, MEDIUM]

**Files changed**: `frontend/src/screens/settings/IntegrationsSettingsScreen.tsx`, `frontend/src/api/sources.ts` (extend)

**Change**:
- Add `useQuery(['sources'], () => apiGet('/api/v1/sources?limit=50'))` to IntegrationsSettingsScreen
- Group sources by type: Slack | Email | Meetings
- Google Calendar remains separate (handled via integrations API, not sources API)
- For each source row: type icon, display_name or provider_account_id, is_active badge, created_at
- "Disconnect" button → calls `DELETE /api/v1/sources/{id}` → on success, invalidate `['sources']` query
- Show `DELETE` as a soft-delete (sets is_active=False). After disconnect, source still shows but as "Disconnected" with a "Reconnect" option (which goes to onboarding step for that type)
- For Slack: after connected, show the channel invitation instruction (see #5)
- For meetings: show the webhook URL per-source (from `Source.metadata_.platform`)

**Note on Google Calendar**: Calendar doesn't have a Source row. It's managed separately via `GET /integrations/google/status` and `DELETE /integrations/google/disconnect`. Existing UI handles this correctly — no change needed for calendar disconnect.

---

### #7 — Multiple sources clarity [FRONTEND, LOW RISK]

Addressed within #6's implementation. Additional:
- For Slack section: if a source is active, show "1 workspace connected" and "Reconnect" (not "Add another")
- For Email section: same — "1 inbox connected" + "Reconnect"
- For Meetings: show each platform separately (fireflies, otter, readai, custom) with individual disconnect — multiple platforms allowed, show "Connect another platform" link

No backend changes required.

---

### #8 — Processing indicator [FRONTEND, LOW RISK]

Addressed within #1's implementation. The new "scanning" empty state:
- Rendered when `hasConnectedSources && allCommitments.length === 0`
- Copy: "Rippled is scanning your recent messages and meetings. This usually takes a few minutes."
- Sub-copy: "New signals will appear here automatically."
- Style: similar to existing "You're clear" card — gray border, centered, no action button

---

### #9 — Activity stats [BACKEND + FRONTEND, LOW RISK]

**Files changed**: `app/api/routes/` (new `stats.py`), `app/api/router.py` (register), `frontend/src/api/stats.ts` (new), `frontend/src/screens/Dashboard.tsx`

**Backend**: New endpoint `GET /api/v1/stats`

```python
# Returns COUNT(source_items) by source_type for current user
# + commitments_detected = COUNT(commitments) for current user
# + sources_connected = COUNT(sources WHERE is_active=True) for current user
{
    "meetings_analyzed": int,      # source_items WHERE source_type='meeting'
    "messages_processed": int,     # source_items WHERE source_type='slack'
    "emails_captured": int,        # source_items WHERE source_type='email'
    "commitments_detected": int,   # commitments (any lifecycle_state)
    "sources_connected": int       # sources WHERE is_active=True
}
```

Single query with conditional COUNT / CASE WHEN — no joins needed, all from `source_items` + `commitments` + `sources` tables.

**Frontend**: Add `useQuery(['stats'], ...)` to Dashboard.tsx with `refetchInterval: 60_000`. Add a small stats row below the commitment list (or at the bottom of the empty state). Style: small, muted, 5 numbers in a row. Don't display if all zeros.

---

### #10 — Slack ingestion fix [FRONTEND + UX, LOW RISK]

The pipeline is correctly wired — no backend fix needed. The issue is setup configuration.

**Fixes**:
1. Show webhook URL in Slack onboarding step (see #5 — same change)
2. Show bot invite instructions after connecting (see #5 — same change)
3. Add a "Test connection" section in IntegrationsSettingsScreen for Slack sources: "Send a test message to verify signals are flowing" → links to a helper or shows last SourceItem ingested_at timestamp

**Optional backend addition**: Add a field to `SourceRead` schema — `last_active_at: datetime | None` — populated from `MAX(source_items.ingested_at) WHERE source_id=?`. This gives the user visibility into whether their sources are receiving data. This is a nice-to-have and can be a separate mini-endpoint or added to `GET /sources/{id}`.

---

### #11 — Gmail connection copy [FRONTEND, LOW RISK]

**Files changed**: `frontend/src/screens/OnboardingScreen.tsx`

Step 1 (Email setup) — changes:
- Before the form fields, add: "Rippled reads your inbox and sent mail to detect commitments. It only reads — never sends or modifies."
- Add: "For Gmail: create an App Password in your Google account security settings. Use that as your password here."
- Add expandable "What access do we need?" section:
  - "IMAP read access to INBOX and Sent folder"
  - "We do not store the full body of emails — only commitment signals extracted from content"
- The existing IMAP host auto-detection for gmail.com already works (maps to `imap.gmail.com`)

---

## Issues That Require Strategic Decisions (Flag for Trinity)

### A — #2: Calendar signal approach

**The question**: Surface calendar events directly as "upcoming meeting" cards in the UI (Option B, recommended), OR run event descriptions through the detection pipeline (Option A)?

**My recommendation**: Option B. Calendar event titles are rarely commitment language. Show them as an "Upcoming" section — deadline awareness, not commitment detection. Detection from event descriptions can be added in C7.

**If Trinity chooses Option A**, the scope expands significantly: needs a new SourceItem creation path for Event rows, a pipeline trigger after sync (new Celery task or inline in `sync_google_calendar`), and careful handling of recurring events (don't create a SourceItem for every recurring instance).

### B — #4: Meeting webhook secret strategy

**The question**: Implement full per-source webhook secret lookup (change `_verify_meeting_auth` to be async and look up source from DB), OR add a "no secret" flag to the meeting setup flow?

**My recommendation**: Per-source lookup. The source is already in the DB with the webhook_secret credential. Verifying per-source is cleaner and allows different providers to have different security postures. The change is small (make auth function async, look up source by user_id + source_type).

### C — #10: Is the Slack webhook URL correct in prod?

If `VITE_API_URL` in production is `https://rippled.ai`, the Slack Events webhook URL is `https://rippled.ai/api/v1/webhooks/slack/events`. Kevin needs to verify this is what's configured in the Slack app's Event Subscriptions. If the URL is wrong, fixing the onboarding copy won't unblock existing connections — Kevin needs to update the URL in the Slack API dashboard manually.

---

## Backend Changes Required

| Change | File | New or Modify | Scope |
|--------|------|---------------|-------|
| Add `user_id` to events table | `alembic/versions/` (new migration) | New | #2 |
| Add `user_id` to Event ORM model | `app/models/orm.py` | Modify | #2 |
| Populate `user_id` on calendar sync | `app/connectors/google_calendar.py` | Modify | #2 |
| Filter events by user_id | `app/api/routes/events.py` | Modify | #2 |
| Per-source webhook secret lookup | `app/api/routes/webhooks/meetings.py` | Modify | #4 |
| New stats endpoint | `app/api/routes/stats.py` | New | #9 |
| Register stats router | `app/api/router.py` | Modify | #9 |

---

## Frontend Changes Required

| Change | File | Issues |
|--------|------|--------|
| Sources query + 3-state empty state | `Dashboard.tsx` | #1, #8 |
| Add refetchInterval to surface queries | `Dashboard.tsx` | #3 |
| Add stats display | `Dashboard.tsx` | #9 |
| Add Gmail copy + IMAP explanations | `OnboardingScreen.tsx` | #11 |
| Add Slack webhook URL + channel invite instructions | `OnboardingScreen.tsx` | #5, #10 |
| Add sources list with disconnect | `IntegrationsSettingsScreen.tsx` | #6, #7 |
| Add Slack channel invite reminder in settings | `IntegrationsSettingsScreen.tsx` | #5 |
| New API client function for sources | `frontend/src/api/sources.ts` | #1, #6 |
| New API client function for stats | `frontend/src/api/stats.ts` | #9 |
| New API client function for events | `frontend/src/api/events.ts` | #2 |

---

## Open Questions with Recommended Answers

| # | Question | Recommended Answer |
|---|----------|--------------------|
| Q1 | Calendar signals: detect via pipeline or surface directly? | Surface directly (Option B) for MVP |
| Q2 | Meeting webhook secret: per-source lookup or flag-based? | Per-source lookup — small change, cleaner |
| Q3 | Disconnect = soft-delete (is_active=False) or hard delete? | Soft-delete — preserve history. Existing endpoint already does this. |
| Q4 | Stats endpoint: COUNT(source_items) or COUNT(commitments only)? | Both — show full pipeline activity |
| Q5 | Should `list_sources` filter out `is_active=False` sources by default? | No backend change — filter client-side in the UI (simpler, avoids API change) |
| Q6 | Calendar events endpoint — add user_id filter now or via calendar source lookup? | Add user_id to events table (migration). The JOIN approach via source_id is too fragile since source_id isn't populated. |

---

## Risk Flags

| Risk | Severity | Mitigation |
|------|----------|-----------|
| #2 requires DB migration (events.user_id) | Medium | Migration is additive (nullable column), safe to run with live data |
| #2 `_upsert_event` change touches calendar sync critical path | Medium | Existing tests cover sync; add tests for user_id population |
| #4 making `_verify_meeting_auth` async touches security-sensitive webhook path | Medium | Write tests for both verified and unverified flows |
| Slack fixes (#5, #10) require Kevin to update Slack app settings manually | Low | Document in IntegrationsSettingsScreen once webhook URL is shown |
| `list_sources` returns inactive sources — frontend must filter | Low | Client-side filter is straightforward |

---

## Estimated Test Count

| Area | New Tests |
|------|-----------|
| #2 — events.user_id filter (backend) | 3 |
| #2 — calendar connector user_id propagation | 2 |
| #4 — meeting webhook: per-source secret lookup | 4 |
| #4 — webhook accepts when no secret configured | 2 |
| #9 — stats endpoint (counts, empty state, auth) | 4 |
| Frontend: Dashboard 3-state empty state | 3 |
| Frontend: refetchInterval present on queries | 1 |
| **Total new** | ~19 |
| Existing 609 tests must remain green | — |

---

## Recommended Build Order (for Trinity's plan)

1. **Backend first**:
   - Stats endpoint (#9) — standalone, no deps
   - Meeting webhook per-source secret (#4) — standalone
   - Events migration + user_id (#2) — migration before connector change
   - Calendar connector user_id fix + events filter (#2)

2. **Frontend — simple fixes** (no backend deps):
   - OnboardingScreen: Gmail copy (#11), Slack webhook URL + invite (#5, #10)
   - Dashboard: refetchInterval (#3)

3. **Frontend — backend-dependent**:
   - Dashboard: sources query + 3-state empty state (#1, #8)
   - Dashboard: stats display (#9)
   - IntegrationsSettingsScreen: sources list + disconnect (#6, #7)
   - Dashboard: events display (#2 — after backend landed)

4. **Final**:
   - E2E verification
   - Frontend build clean
   - Ruff clean
   - All 609 tests passing
