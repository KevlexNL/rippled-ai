# Phase C5 — User UI Expansion: Interpretation

**Written by:** Claude Code
**Date:** 2026-03-14
**Stage:** STAGE 2 — INTERPRET

---

## What This Phase Does and Why

Phases C1–C3 built temporal scoring, event links, delivery states, counterparty weighting, pre-event nudges, and post-event resolution. Phase C4 built the admin UI. None of the C1–C3 intelligence is visible to the actual user yet.

C5 wires the existing backend data into the existing frontend with surgical additions. No new detection, scoring, or pipeline logic. The user gets:

1. A context line on every commitment card explaining *why* it's surfaced (event proximity, deadline urgency, delivery status)
2. A delivery state badge on cards when meaningful
3. One-tap delivery actions on the commitment detail view
4. Post-event review prompts on the detail view
5. Inline clarification answering without navigating away
6. A Settings screen with Google Calendar connect and digest toggle
7. A Calendar step in the onboarding wizard
8. Better empty state copy in three views

The backend gets three lightweight additions: `GET /user/settings`, `PATCH /user/settings`, and `state='pending'` handling in `PATCH /delivery-state`. Plus `linked_events` gets added to the commitments list response.

---

## Critical Pre-Build Gaps Found During Intake

These are not listed in the WO but are **blockers** discovered by reading the code:

### Gap 1: C3 fields missing from `CommitmentRead` Pydantic schema
`app/models/schemas.py` → `CommitmentRead` does NOT include `delivery_state`, `counterparty_type`, `counterparty_email`, or `post_event_reviewed`. These fields exist in `orm.py` (`Commitment` model) but were never added to the Pydantic schema. All surface and commitment endpoints use `CommitmentRead.model_validate(row)` — these fields are currently silently dropped.

**Action required in BUILD**: Add the four C3 fields to `CommitmentRead` in `schemas.py` before any frontend work.

### Gap 2: C3 fields missing from TypeScript `CommitmentRead` type
`frontend/src/types/index.ts` → `CommitmentRead` interface also does NOT include `delivery_state`, `counterparty_type`, `counterparty_email`, or `post_event_reviewed`.

**Action required in BUILD**: Add these four fields to the TypeScript type.

### Gap 3: No clarification API route exists
The WO says "Add inline answer support" calling `POST /api/v1/clarifications/{id}/respond`. This endpoint **does not exist**. There is no `app/api/routes/clarifications.py` file. The `Clarification` ORM model exists with `suggested_values` and `suggested_clarification_prompt` fields, but there are zero API routes for it.

**Action required in BUILD**: Create `app/api/routes/clarifications.py` with the respond endpoint and register it in `main.py`. See endpoint shape in New Backend Endpoints section.

### Gap 4: `UserSettings` has no `digest_to_email` field
`app/models/orm.py` → `UserSettings` has `digest_enabled`, `digest_time`, `last_digest_sent_at`, Google OAuth fields. It does NOT have `digest_to_email`. That setting lives in `config.py` as an environment variable.

**Action required in BUILD**: Add `digest_to_email` column to `UserSettings` ORM model + Alembic migration. The `GET /user/settings` response should expose this field. The `PATCH /user/settings` should update it on the DB row, not on the environment.

---

## Inventory: Existing Frontend Components That Will Be Modified

### `frontend/src/types/index.ts` (line 9–55, `CommitmentRead` interface)
**Change**: Add four C3 fields from ORM model, plus new `linked_events` field.
```typescript
// Add to CommitmentRead:
delivery_state: string | null           // 'draft_sent' | 'acknowledged' | 'rescheduled' | 'partial' | 'delivered' | 'closed_no_delivery'
counterparty_type: string | null        // 'external_client' | 'internal_manager' | 'internal_peer' | 'self'
counterparty_email: string | null
post_event_reviewed: boolean
linked_events: LinkedEventRead[] | null  // NEW nested type, see below
```
New type to add:
```typescript
export interface LinkedEventRead {
  event_id: string
  title: string
  starts_at: string
  ends_at: string | null
  relationship: string   // 'delivery_at' | 'prep_at' | 'review_at'
  is_past: boolean       // computed: starts_at < now
}
```

### `frontend/src/api/commitments.ts`
**Changes**:
- Add `patchDeliveryState(id: string, state: string): Promise<CommitmentRead>` → `PATCH /api/v1/commitments/${id}/delivery-state`
- No changes to `getCommitments` — the `?limit` default of 5 may need increasing for dashboard use; verify in READ-THROUGH

### `frontend/src/components/CommitmentRow.tsx`
**Changes**: This is the most impacted component.
1. **Context line** (priority logic, 8 cases) — replaces the existing `getSubRow` sub-row. The context line uses new fields (`delivery_state`, `linked_events`, `resolved_deadline`, `counterparty_type`). The existing `getSubRow` shows timing/ownership ambiguity OR delivered state. With C5, the context line has 8 cases with a clear priority order.
   - **Design decision**: Keep `getSubRow` for `needs_clarification` state (the ambiguity display) but replace it for all other cases with the new context line logic. OR: fold the clarification prompt handling entirely into the inline clarification UI (Deliverable 5) and use context line only for the 8 non-clarification cases.
   - **Recommended**: For `lifecycle_state === 'needs_clarification'` with an open clarification, show the inline clarification prompt (Deliverable 5) instead of the context line. For all other cards, show the context line. The existing `getSubRow` ambiguity display is replaced entirely.
2. **Delivery state badge** — pill aligned right on the context line row.
3. **Inline clarification prompt** — when `lifecycle_state === 'needs_clarification'` with open clarification data (passed as prop), replaces context line with question + answer buttons.

**Prop change**: `CommitmentRow` currently takes `{ commitment, onClick, showReasoning }`. Must add optional `openClarification?: ClarificationSummary` prop to support inline answering.

### `frontend/src/screens/CommitmentDetail.tsx`
**Changes**:
1. **Post-event review banner** — at top of screen (above title), shown when `post_event_reviewed === false` AND `linked_events` has a past event. Uses inline state to track dismissed.
2. **Delivery action row** — below existing content, above the bottom bar. Contextual buttons based on `delivery_state` and `lifecycle_state`. Uses `patchDeliveryState`.
3. **Inline `linked_events` display** — optionally show the nearest linked event as a context line in the detail view (a nice-to-have, not required by WO).
4. **Bottom bar modification** — currently shows "Go back" + "Approve" (when proposed). Must also show delivery action buttons when `lifecycle_state` is `active` or `needs_clarification` and `delivery_state` is not `delivered` or `closed_no_delivery`. This competes with the existing bottom bar. **Recommended**: Move delivery actions to an inline section in the scroll view (not the bottom bar), keeping the fixed bottom bar for navigation only.

### `frontend/src/screens/Dashboard.tsx`
**Changes**:
1. **Surface query `limit` increase** — `getSurface('*')` endpoints currently use FastAPI defaults (`limit=10`). Commitments API `getCommitments` defaults to 5. No change needed here since Dashboard calls `getSurface`, not `getCommitments`.
2. **Empty state copy** — update the existing empty state (`sourceTypes.length === 0`) copy. Note: the current empty state shows when there are no source groups at all ("Rippled has no signals yet"). The WO's new copy "You're clear. No commitments need your attention right now." is for when commitments exist but none are surfaced. These are two different states. The current check `sourceTypes.length === 0` fires when there are no commitments across all three surfaces. This is close to "nothing surfaced" but technically it's "no commitments at all." **Recommended**: Add a secondary empty state when `allCommitments.length === 0` (surfaces return empty arrays) vs. `sources.length === 0` (no sources connected).
3. **Settings navigation** — The WO says "gear icon or Settings tab" accessible from main nav. The `BottomBar` has four buttons: Overview, Quick revert, Talk it through (disabled), Start session (disabled). **Recommended**: Replace one of the disabled BottomBar buttons with a Settings link, or add a gear icon to the Dashboard header. The `AccountSettingsScreen` and `SourcesSettingsScreen` exist but there's no way to reach them from the Dashboard currently (only via direct URL). A settings gear in the header is the least disruptive.

### `frontend/src/screens/OnboardingScreen.tsx`
**Changes**:
1. Insert new step between current step 3 (Meetings) and step 4 (Done). This means:
   - Renumber: current step 4 (Done) becomes step 5
   - Add step 4 as Calendar step
   - Update all `setStep(4)` calls in Meetings step to `setStep(4)` (already correct, no change) but add the `step === 4` Calendar block before the existing Done block
   - Update step counter labels: "Step 3 of 3" becomes "Step 3 of 4", and Calendar is "Step 4 of 4"
2. Calendar step checks `GET /integrations/google/status` to auto-advance if already connected
3. OAuth flow: "Connect Google Calendar" button triggers navigation to `/api/v1/integrations/google/auth` as a full page redirect (see Open Questions for OAuth redirect handling)

### `frontend/src/screens/settings/SourcesSettingsScreen.tsx` or new settings screen
**Decision needed**: The WO says add a Settings screen accessible from main navigation. Existing settings are split across `/settings/sources` and `/settings/account`. The WO's new settings content (Calendar connect + digest toggle) belongs at `/settings/integrations` (a new file). **Recommended**: Create `frontend/src/screens/settings/IntegrationsSettingsScreen.tsx` as a new route at `/settings/integrations`, and add a link to it from the Dashboard header gear icon.

---

## New Frontend Components

### `frontend/src/components/ContextLine.tsx` (new)
Pure display component. Props: `commitment: CommitmentRead, now: Date`. Returns the context line string and delivery badge based on the 8-case priority logic. Exported as a component with the line text and an optional badge pill. Called from `CommitmentRow`.

### `frontend/src/components/DeliveryBadge.tsx` (new)
Small pill component. Props: `state: string`. Returns the appropriate styled pill for `draft_sent`, `acknowledged`, `partial`, `rescheduled`. Returns `null` for null, `delivered`, `closed_no_delivery`.

### `frontend/src/components/DeliveryActions.tsx` (new)
The delivery action row. Props: `commitment: CommitmentRead, onUpdate: () => void`. Renders contextual buttons based on `delivery_state`. Calls `patchDeliveryState`. Calls `onUpdate()` (which invalidates the query) after a successful PATCH.

### `frontend/src/components/PostEventBanner.tsx` (new)
The inline banner shown at top of CommitmentDetail. Props: `commitment: CommitmentRead, eventTitle: string, onDismiss: () => void`. Three buttons: Yes done / Sent a draft / Not yet. Calls `patchDeliveryState`. One-shot — dismissed via local state, never reappears in this session.

### `frontend/src/screens/settings/IntegrationsSettingsScreen.tsx` (new)
Settings screen at `/settings/integrations`. Contains Google Calendar section and Digest section.

### `frontend/src/api/userSettings.ts` (new)
API functions: `getUserSettings()` → `GET /api/v1/user/settings`, `patchUserSettings(body)` → `PATCH /api/v1/user/settings`.

### `frontend/src/api/clarifications.ts` (new)
API function: `respondToClarification(id: string, answer: string)` → `POST /api/v1/clarifications/${id}/respond`.

---

## Context Line Priority Logic — Mapped to API Response Fields

All 8 cases map to fields available in `CommitmentRead` after the C5 changes:

| Priority | Condition | Display | API fields used |
|----------|-----------|---------|-----------------|
| 1 | `linked_events` has a `delivery_at` event with `starts_at` within 25h from now | `"[counterparty_type label] · [event.title] in [N]h"` | `linked_events[0].starts_at`, `linked_events[0].title`, `counterparty_type` |
| 2 | `linked_events` has a `delivery_at` event with `starts_at` within 72h from now | `"[event.title] in [N] days"` | `linked_events[0].starts_at`, `linked_events[0].title` |
| 3 | `delivery_state === 'acknowledged'` | `"Acknowledged · waiting on you"` | `delivery_state` |
| 4 | `delivery_state === 'draft_sent'` | `"Draft sent · pending final"` | `delivery_state` |
| 5 | `resolved_deadline !== null` AND `resolved_deadline` is in the past | `"Overdue · [N] days"` | `resolved_deadline` |
| 6 | `resolved_deadline !== null` AND within 3 days | `"Due in [N] days"` | `resolved_deadline` |
| 7 | `counterparty_type === 'external_client'` | `"External commitment"` | `counterparty_type` |
| 8 | none of above apply | no context line shown | — |

**`counterparty_type` label mapping** for case 1: `external_client` → "Client", `internal_manager` → "Manager", `internal_peer` → "Colleague", `self` → "" (don't show prefix for self).

**The `linked_events` field returned by the list endpoint** contains only the nearest `delivery_at` event (single event). This is sufficient for cases 1 and 2. For post-event detection (the banner), the detail view fetches the full commitment including `linked_events`, and checks `is_past`.

---

## Delivery Action Button States — Mapped to API Calls

All calls go to `PATCH /api/v1/commitments/{id}/delivery-state` with `{state: "..."}`.

| Current state | Button 1 | Button 2 | Button 3 |
|---------------|----------|----------|----------|
| null (no delivery_state) | "Sent a draft" → `state='draft_sent'` | "Done" → `state='delivered'` + `lifecycle_state='delivered'` via separate PATCH | "Not mine" → `lifecycle_state='dismissed'` via `PATCH /commitments/{id}` |
| `draft_sent` | "Sent final" → `state='delivered'` + `lifecycle_state='delivered'` | "Still in progress" → dismiss UI only (no API call) | — |
| `acknowledged` | "Done" → `state='delivered'` + `lifecycle_state='delivered'` | "Pushed back" → `state='rescheduled'` | — |

**Note on "Done" transitions**: Setting `delivery_state='delivered'` should also set `lifecycle_state='delivered'`. The `PATCH /delivery-state` endpoint currently only sets `delivery_state`. The frontend must make a second call: `PATCH /commitments/{id}` with `{lifecycle_state: 'delivered'}`. The `VALID_TRANSITIONS` guard allows `active → delivered`. **Recommended**: Extend `PATCH /delivery-state` to also set `lifecycle_state='delivered'` when `state='delivered'` is passed, avoiding two round-trips.

**Note on "Not mine"**: `lifecycle_state='dismissed'` is not in `VALID_TRANSITIONS`. The current valid transitions from `active` are `['needs_clarification', 'delivered', 'closed', 'discarded']`. "Not mine" should map to `'discarded'`, not `'dismissed'` (which isn't a valid state). Flag this to Trinity.

---

## How `linked_events` Gets Added Without N+1 Queries

**Recommended approach: batch JOIN query at the list endpoint level.**

**Option A — JOIN in list query (recommended)**:

Modify `GET /surface/*` endpoints in `app/api/routes/surface.py` to perform a single additional query:

```python
# After fetching commitments list:
commitment_ids = [c.id for c in commitments]
link_result = await db.execute(
    select(CommitmentEventLink, Event)
    .join(Event, Event.id == CommitmentEventLink.event_id)
    .where(
        CommitmentEventLink.commitment_id.in_(commitment_ids),
        CommitmentEventLink.relationship == "delivery_at",
        Event.status != "cancelled",
    )
    .order_by(Event.starts_at.asc())
)
# Build dict: commitment_id → nearest Event
event_map: dict[str, Event] = {}
for link, event in link_result:
    if link.commitment_id not in event_map:  # first = soonest due to ORDER BY
        event_map[link.commitment_id] = event

# Attach to each CommitmentRead response
```

This is **two queries, not N+1**: one for commitments, one for all their events. The result is built in Python, not SQL.

**Option B — Extend `CommitmentRead` with `linked_events`** as a computed field by modifying `_to_schema()` and passing the event map through. This keeps the schema accurate.

**Recommended implementation**: Create a new `LinkedEventRead` Pydantic schema. Add `linked_events: list[LinkedEventRead] | None = None` to `CommitmentRead` in `schemas.py`. Modify the `surface.py` list endpoints to do the secondary query and inject the linked events. Do the same for `GET /commitments` list endpoint in `commitments.py` (for the detail view loading path).

**Important**: The single-commitment `GET /commitments/{id}` endpoint should also include `linked_events` since `CommitmentDetail` uses it for the post-event banner. Use the same secondary query pattern.

---

## Settings Screen and Onboarding Integration

### Settings Screen (`/settings/integrations`)

New route in `App.tsx`:
```tsx
<Route path="/settings/integrations" element={<AuthGuard><IntegrationsSettingsScreen /></AuthGuard>} />
```

Access from Dashboard: add gear icon `⚙` button to the Dashboard header (right side of `<h1>` row), linked to `/settings/integrations`.

The `IntegrationsSettingsScreen` structure:
```
← Back                    "Integrations"

GOOGLE CALENDAR
─────────────────────────────────────
[Connected ✓]  |  "Disconnect" button
Last sync: [date from google_token_expiry]
  OR
"Connect Google Calendar" button

DAILY DIGEST
─────────────────────────────────────
Toggle: "Daily digest email" [on/off]
  If on: "Digest email" [editable input]

```

The Google status display uses `GET /api/v1/integrations/google/status` → `{connected: bool, expiry: datetime}`. "Last sync" is approximated from `expiry` (not ideal but the only available timestamp without adding a `last_synced_at` column; recommend noting this limitation).

The digest email field uses `GET /api/v1/user/settings` to load current `digest_to_email` and `digest_enabled`, and `PATCH /api/v1/user/settings` to update.

### Onboarding Calendar Step (step 4 of 4)

Insert new step 4 block in `OnboardingScreen.tsx` between the Meetings block and Done block:

```
step === 4:
  "Step 4 of 4"
  "Connect your calendar"
  Body text from WO

  If google_status.connected:
    Green checkmark "Calendar connected" → auto-advance to step 5 after 1.5s (useEffect + setTimeout)
  Else:
    "Connect Google Calendar" button → window.location.href = API_BASE + '/api/v1/integrations/google/auth'
    "Skip for now" link → setStep(5)
```

Step numbering update: all existing step label strings "Step 1 of 3", "Step 2 of 3", "Step 3 of 3" become "Step 1 of 4", "Step 2 of 4", "Step 3 of 4". And the Done step becomes step 5 (update the Done check from `step === 4` conditions to `step >= 5`).

Loads Google status via `useQuery(['google-status'], getGoogleStatus)` — `GET /api/v1/integrations/google/status`.

---

## New Backend Endpoints

### `app/api/routes/user_settings.py` (new file)

**`GET /api/v1/user/settings`**
```
Auth: x-user-id header (standard)
Response 200:
{
  "digest_enabled": bool,
  "digest_to_email": string | null,
  "google_connected": bool   // convenience field: true if google_refresh_token is not null
}
```
Creates `UserSettings` row with defaults if not exists (same pattern as `_get_or_create_user_settings` in `integrations.py`).

**`PATCH /api/v1/user/settings`**
```
Request body:
{
  "digest_enabled": bool | null,      // omit to leave unchanged
  "digest_to_email": string | null    // omit to leave unchanged
}
Response 200: same shape as GET
```

Register in `app/main.py`:
```python
from app.api.routes import user_settings as user_settings_routes
app.include_router(user_settings_routes.router, prefix=settings.api_prefix, tags=["user-settings"])
```

### `app/api/routes/commitments.py` (extend)

**`PATCH /commitments/{id}/delivery-state`** — current implementation rejects `state='pending'` with 422. Add handling:

```python
_VALID_DELIVERY_STATES = frozenset({
    "draft_sent", "acknowledged", "rescheduled", "partial",
    "delivered", "closed_no_delivery",
})
_PENDING_STATE = "pending"  # special: sets post_event_reviewed=true without changing delivery_state

@router.patch("/{commitment_id}/delivery-state", response_model=CommitmentRead)
async def patch_delivery_state(...):
    if body.state == _PENDING_STATE:
        # Special: just mark post_event_reviewed=true, don't change delivery_state
        commitment.post_event_reviewed = True
        commitment.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(commitment)
        return _commitment_to_schema(commitment)

    if body.state not in _VALID_DELIVERY_STATES:
        raise HTTPException(status_code=422, ...)

    # existing logic
    commitment.delivery_state = body.state
    ...
```

Also extend to set `lifecycle_state='delivered'` when `state='delivered'` (see delivery action notes above).

### `app/api/routes/clarifications.py` (new file)

**`GET /api/v1/clarifications?commitment_id={id}`**
```
Auth: x-user-id header
Response 200: list[ClarificationRead]
ClarificationRead:
{
  "id": str,
  "commitment_id": str,
  "suggested_clarification_prompt": str | null,
  "suggested_values": dict,   // JSONB, contains answer options
  "resolved_at": str | null
}
```
Returns open (unresolved) clarifications for the given commitment.

**`POST /api/v1/clarifications/{id}/respond`**
```
Request body:
{
  "answer": str
}
Response 200:
{
  "id": str,
  "resolved_at": str
}
Side effects:
  - Sets clarification.resolved_at = now()
  - Sets commitment.lifecycle_state = 'active' (transition from 'needs_clarification')
  - Writes LifecycleTransition row with trigger_reason='clarification_answered'
```

Register in `app/main.py`.

### `app/models/orm.py` — add `digest_to_email` to `UserSettings`

```python
class UserSettings(Base):
    # existing fields...
    digest_to_email: Mapped[str | None] = mapped_column(Text, nullable=True)  # NEW
```

Migration: `alembic revision --autogenerate -m "add_digest_to_email_to_user_settings_c5"`

### `app/models/schemas.py` — add C3 fields to `CommitmentRead`

```python
class CommitmentRead(_Base):
    # after existing surfacing fields:
    # Phase C3 fields
    delivery_state: str | None = None
    counterparty_type: str | None = None
    counterparty_email: str | None = None
    post_event_reviewed: bool = False
    # Phase C5 — linked events (injected at query time, not from ORM)
    linked_events: list["LinkedEventRead"] | None = None
```

New schema:
```python
class LinkedEventRead(_Base):
    event_id: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    relationship: str
```

---

## Open Questions with Recommended Answers

### OQ1: `GET /commitments` list — JOIN or separate batch query for linked events?

**Options**:
- A) SQLAlchemy `selectinload` / eager load via relationship (requires adding `relationship()` to ORM)
- B) Separate batch query in Python after fetching commitments: one query for all event links of the returned commitment IDs
- C) Subquery in the main query (complex SQL, hard to maintain)

**Recommendation: Option B — separate batch query.**

Reason: The ORM models don't currently use SQLAlchemy relationships (no `relationship()` calls in `orm.py`). Adding them for one use case is overengineering. A separate batch query for `N` commitments returns all their linked events in one round trip. In Python, we `group_by(commitment_id)` and take the soonest event per commitment. This is:
- O(1) queries regardless of list size
- No ORM relationship changes required
- Consistent with the existing "raw select → schema" pattern

Apply this to both `surface.py` list endpoints and `commitments.py` list endpoint. Single-commitment `GET /commitments/{id}` also gets the same treatment (the batch query with a single ID is trivially efficient).

The `CommitmentRead` schema gets a `linked_events: list[LinkedEventRead] | None` field. The `_to_schema()` helper in each route is replaced by a factory function that takes an optional pre-built event map:

```python
def _build_commitment_read(row: Commitment, event_map: dict[str, list[Event]] | None = None) -> CommitmentRead:
    schema = CommitmentRead.model_validate(row)
    if event_map and row.id in event_map:
        schema.linked_events = [LinkedEventRead.model_validate({
            "event_id": e.id, "title": e.title, "starts_at": e.starts_at,
            "ends_at": e.ends_at, "relationship": link.relationship
        }) for e, link in event_map[row.id]]
    return schema
```

### OQ2: OAuth redirect back into the SPA without losing state

**Problem**: `GET /integrations/google/auth` redirects to Google's OAuth consent page. Google then redirects to `GET /integrations/google/callback` (a backend URL). The current callback returns JSON `{"status": "connected"}` — the user is stranded at a backend URL, seeing raw JSON, with no way back into the SPA.

**Options**:
- A) Callback redirects to a frontend URL with query params: `RedirectResponse(url=f"/settings/integrations?calendar=connected")`
- B) Frontend opens OAuth in a popup window, callback page posts a message to the parent window
- C) Frontend opens OAuth URL in same tab, callback redirects back to a specific frontend route

**Recommendation: Option A — redirect from callback to SPA route.**

Modify `google_callback` to return `RedirectResponse(url="/settings/integrations?calendar=connected")` on success and `RedirectResponse(url="/settings/integrations?calendar=error")` on failure.

In `IntegrationsSettingsScreen.tsx`, read `useSearchParams()` on mount:
- If `?calendar=connected`: invalidate `google-status` query, show success toast/banner
- If `?calendar=error`: show error message

For the onboarding step: same OAuth redirect, but the `google_oauth_redirect_uri` setting points to the callback. After success, redirect to `/onboarding?calendar=connected`. The onboarding wizard reads this param on mount and advances past the calendar step.

**However**: The `google_oauth_redirect_uri` is a registered redirect URI in Google Cloud Console. Changing what the callback returns (`/settings/integrations` vs `/onboarding`) requires knowing the entry point. **Simpler approach**: always redirect to `/settings/integrations?calendar=connected`, and in the onboarding step, after the user clicks "Connect Google Calendar", store the current step in `localStorage` under `rippled_oauth_return_step`. The `IntegrationsSettingsScreen` (loaded after OAuth) checks localStorage, sees `rippled_oauth_return_step = 4`, redirects back to `/onboarding?step=4&calendar=connected`. The onboarding screen reads this param and auto-advances.

**Even simpler (recommended for MVP)**: In the onboarding calendar step, don't do full OAuth redirect. Instead show the user an explanation and a button that opens `/settings/integrations` (new tab). After connecting there, they return to onboarding and click "I connected it" or "Skip". The onboarding step just checks `GET /integrations/google/status` on mount. This eliminates the cross-page state problem entirely.

For the Settings screen OAuth flow, Option A (redirect back to `/settings/integrations?calendar=connected`) is clean and sufficient.

### OQ3: Inline clarification answering — integration with existing clarification fetch logic

**Problem**: There is no existing clarification fetch logic in the frontend. There's no `GET /api/v1/clarifications` endpoint, no TypeScript types for clarifications, and no existing inline clarification display. The WO says "The existing clarification flow requires navigating to a separate Clarifications view" but no such view exists in the frontend routes — there's no `/clarifications` screen.

Looking at the existing code: `Dashboard.tsx` calls `getSurface('clarifications')` which returns `CommitmentRead[]` with `lifecycle_state='needs_clarification'`. These commitments appear in `SourceGroup` cards alongside regular commitments, grouped by `context_type`. The "clarifications view" the WO refers to appears to be the `Review` screen at `/source/:sourceType` which shows all commitments for a source type (including clarification ones). There's no dedicated answer-a-clarification flow at all.

**What needs to be built from scratch**:
1. `GET /api/v1/clarifications?commitment_id={id}` endpoint (see New Backend Endpoints)
2. `POST /api/v1/clarifications/{id}/respond` endpoint
3. Frontend: for each clarification commitment in the Dashboard cards, fetch its open clarification
4. Display inline: question text + up to 3 answer buttons

**The fetch strategy**: The Dashboard already makes 3 parallel `getSurface` queries. Adding a batch `GET /clarifications` query for all clarification commitment IDs would be clean but requires a new bulk endpoint. Simpler: for commitments with `lifecycle_state === 'needs_clarification'`, trigger individual `GET /clarifications?commitment_id={id}` queries via React Query (one per clarification commitment). Since there are typically ≤10 clarification commitments surfaced at once, this is O(10) queries — acceptable.

**Recommended implementation**:
- In `CommitmentRow`, if `lifecycle_state === 'needs_clarification'`, trigger a `useQuery(['clarification', commitment.id], () => getClarifications(commitment.id))`. If a clarification exists with a prompt and suggested values, show the inline prompt. If no clarification data (edge case: commitment is `needs_clarification` but no open clarification row), show the standard context line.

**Complication**: `CommitmentRow` is a pure display component. Making it fetch data via `useQuery` adds a data-fetching concern to a display component. Alternative: fetch all clarifications in `Dashboard.tsx` for clarification commitments, pass as props down to `CommitmentRow`. This is cleaner. Use `useQueries` in Dashboard to batch-fetch.

**Recommended**: Add clarification pre-fetch in `Dashboard.tsx` using `useQueries` for all commitments with `lifecycle_state === 'needs_clarification'`. Build a `clarificationMap: Record<commitment_id, ClarificationRead>`. Pass to `SourceGroup` → `CommitmentRow` as an optional prop.

---

## Risk Flags

### Risk 1: `CommitmentRead` schema gap is a silent bug — HIGH

The C3 fields (`delivery_state`, `counterparty_type`, `post_event_reviewed`) are in the ORM but not the Pydantic schema. If this phase adds frontend UI that reads these fields but the backend still drops them from responses, everything will silently show `null` / defaults. The fix (Gap 1) MUST happen before any frontend work — otherwise context lines and delivery badges will never show.

**Mitigation**: Fix both `schemas.py` and `types/index.ts` in the first commit of the BUILD phase, before any component work.

### Risk 2: No clarification API route — MEDIUM

The inline clarification feature depends on two non-existent API endpoints. These must be built during the BUILD phase. The `Clarification` ORM model's `suggested_values` field is JSONB with no defined schema — its structure needs investigation before building the frontend. **Risk**: `suggested_values` may store values in an unexpected format.

**Mitigation**: During BUILD, inspect actual `suggested_values` rows in the DB (via admin UI or direct query) to understand the format. The respond endpoint should accept `{answer: str}` regardless of how suggested values are stored.

### Risk 3: Dashboard groups by context_type, not by surface destination — LOW but confusing

The WO says "add context line to commitment cards on Dashboard/main view and Shortlist." But the Dashboard currently shows commitments from ALL three surfaces (`main`, `shortlist`, `clarifications`) grouped by `context_type` (meeting/slack/email), not by surface. A single source group card shows commitments that mix main, shortlist, and clarification destinations without visual distinction. The context line logic is per-commitment (no surface-destination awareness needed) so this doesn't block the feature. But a `main`-surface commitment and a `shortlist`-surface commitment can appear side-by-side in the same group card without differentiation.

**Mitigation**: No change needed for C5. Note it as a future UX cleanup.

### Risk 4: `lifecycle_state='dismissed'` does not exist — HIGH

The delivery action "Not mine" button in the WO maps to `lifecycle_state='dismissed'`. This lifecycle state is NOT in the `_lifecycle_state` PostgreSQL ENUM (`proposed`, `needs_clarification`, `active`, `delivered`, `closed`, `discarded`). Using it would throw a DB error. Map "Not mine" to `'discarded'` instead.

**Mitigation**: During BUILD, use `lifecycle_state='discarded'` in the "Not mine" action. Verify `VALID_TRANSITIONS` allows `active → discarded` (it does: `"active": ["needs_clarification", "delivered", "closed", "discarded"]`).

### Risk 5: `BottomBar` component needs Settings navigation — LOW

Currently `BottomBar` has "Talk it through" and "Start session" as permanently disabled buttons. Adding a Settings link requires either (a) modifying `BottomBar` to accept a new prop, or (b) adding a separate settings link to the Dashboard header. Modifying `BottomBar` is more disruptive (it's used in multiple screens). Recommend adding gear icon to Dashboard header only.

### Risk 6: OAuth state loss during onboarding — MEDIUM

See OQ2. The multi-page OAuth redirect during onboarding is the most complex UX flow. If not handled carefully, users will finish OAuth but land on settings instead of onboarding, or the onboarding wizard won't know the calendar step is complete.

**Mitigation**: Use the simplified approach (OQ2) — in onboarding, show a link to open settings in a new tab, then re-check calendar status. Avoids cross-page state entirely.

### Risk 7: `delivery_state='delivered'` needs lifecycle_state sync — MEDIUM

When a user taps "Done" in the delivery action row, we need BOTH `delivery_state='delivered'` AND `lifecycle_state='delivered'`. Currently two separate PATCH calls are needed. If the first succeeds and the second fails, the commitment is in an inconsistent state. Recommend extending `PATCH /delivery-state` to atomically set `lifecycle_state='delivered'` when `state='delivered'`.

### Risk 8: `limit` in surface endpoints may be too low — LOW

`GET /surface/main` returns at most 10 commitments. With context lines, all 10 are shown in the same grouped view. This limit is fine for C5. Note for future scaling.

---

## Estimated Test Count and Breakdown

Per WO: backend-only tests, minimum 15. No frontend tests required.

### Unit Tests

| Test class | Count | Coverage |
|------------|-------|----------|
| `TestUserSettingsGet` | 3 | creates defaults if not exists, returns existing row, `google_connected` field reflects token presence |
| `TestUserSettingsPatch` | 4 | updates `digest_enabled` true→false, updates `digest_to_email`, partial update (omit field → unchanged), invalid body → 422 |
| `TestDeliveryStatePending` | 3 | `state='pending'` sets `post_event_reviewed=true`, does NOT change `delivery_state`, still returns full `CommitmentRead` |
| `TestDeliveryStateDelivered` | 2 | `state='delivered'` sets `delivery_state` AND `lifecycle_state='delivered'` atomically |
| `TestLinkedEventsInListResponse` | 4 | `GET /surface/main` includes `linked_events` for commitments with links, `linked_events=[]` for commitments without links, only `delivery_at` relationship returned, cancelled events excluded |
| `TestClarificationRespond` | 3 | `POST /clarifications/{id}/respond` sets resolved_at, transitions commitment to `active`, writes LifecycleTransition |
| `TestClarificationGet` | 2 | returns open clarifications for commitment_id, returns empty if all resolved |

**Unit subtotal: 21**

### Integration Tests

| Test class | Count | Coverage |
|------------|-------|----------|
| `TestUserSettingsRoundTrip` | 2 | GET → PATCH → GET confirms update persisted; create-if-not-exists on first GET |
| `TestDeliveryStatePendingIntegration` | 1 | PATCH state=pending → commitment.post_event_reviewed = True in DB |
| `TestLinkedEventsIntegration` | 2 | surface list with linked events: correct event attached; surface list no events: null linked_events |
| `TestClarificationRespondIntegration` | 2 | full flow: create commitment → create clarification → respond → verify state transitions |
| `TestC3FieldsInSurfaceResponse` | 2 | surface main endpoint returns delivery_state and counterparty_type fields (tests Gap 1 fix) |

**Integration subtotal: 9**

### **Total: 30 new tests** (exceeds 15-test minimum)

Note: if the clarification endpoints are counted separately as a major addition (which they are, being fully new routes), the test count should target 20-25 unit tests to cover edge cases adequately. Recommend adding:
- 2 more tests for clarification edge cases (`commitment not found → 404`, `clarification already resolved → 409`)
- 2 more tests for `linked_events` ordering (nearest event first, multiple events per commitment)

**Revised total with additions: ~34 new tests**

---

## Files to Create or Modify

| File | Action | Notes |
|------|--------|-------|
| `app/models/schemas.py` | MODIFY | Add C3 fields + `linked_events` to `CommitmentRead`; add `LinkedEventRead` schema |
| `app/models/orm.py` | MODIFY | Add `digest_to_email` to `UserSettings` |
| `app/api/routes/surface.py` | MODIFY | Add secondary event link batch query; inject into response |
| `app/api/routes/commitments.py` | MODIFY | Add `pending` state handling; add `lifecycle_state='delivered'` sync; add event link batch query to list/detail |
| `app/api/routes/user_settings.py` | NEW | GET + PATCH user settings |
| `app/api/routes/clarifications.py` | NEW | GET + POST respond |
| `app/main.py` | MODIFY | Register user_settings and clarifications routers |
| `migrations/versions/XXX_add_digest_to_email_c5.py` | NEW | Alembic migration |
| `frontend/src/types/index.ts` | MODIFY | Add C3 fields + LinkedEventRead to CommitmentRead |
| `frontend/src/api/commitments.ts` | MODIFY | Add `patchDeliveryState` function |
| `frontend/src/api/userSettings.ts` | NEW | GET + PATCH user settings |
| `frontend/src/api/clarifications.ts` | NEW | GET + respond functions |
| `frontend/src/components/CommitmentRow.tsx` | MODIFY | Context line + delivery badge + inline clarification prompt |
| `frontend/src/components/ContextLine.tsx` | NEW | Context line display component |
| `frontend/src/components/DeliveryBadge.tsx` | NEW | Delivery state pill |
| `frontend/src/components/DeliveryActions.tsx` | NEW | Delivery action row |
| `frontend/src/components/PostEventBanner.tsx` | NEW | Post-event review banner |
| `frontend/src/screens/CommitmentDetail.tsx` | MODIFY | Post-event banner + delivery actions |
| `frontend/src/screens/Dashboard.tsx` | MODIFY | Empty state copy + gear icon + clarification pre-fetch |
| `frontend/src/screens/OnboardingScreen.tsx` | MODIFY | Add calendar step (step 4 of 4), renumber Done step |
| `frontend/src/screens/settings/IntegrationsSettingsScreen.tsx` | NEW | Google Calendar + digest settings |
| `frontend/src/App.tsx` | MODIFY | Add `/settings/integrations` route |
| `tests/test_c5_user_settings.py` | NEW | User settings unit + integration tests |
| `tests/test_c5_delivery_state.py` | NEW | Delivery state pending + delivered sync tests |
| `tests/test_c5_linked_events.py` | NEW | Linked events in list response tests |
| `tests/test_c5_clarifications.py` | NEW | Clarification get + respond tests |

---

## Summary

Phase C5 is more complex than the WO implies, primarily due to **four gaps** not visible until reading the code:

1. C3 fields were added to the ORM but never propagated to the Pydantic schema or TypeScript types
2. The `UserSettings` table has no `digest_to_email` column (it's an env var)
3. No clarification API routes exist despite the feature being needed
4. The `delivery_state='pending'` special case and the `lifecycle_state` sync when delivering both require careful backend changes

The frontend work itself is surgical — `CommitmentRow`, `CommitmentDetail`, `OnboardingScreen`, and one new settings screen. The biggest design decisions are:
- OAuth redirect handling (recommend simplified tab-open approach for onboarding)
- Clarification data fetching (recommend Dashboard-level pre-fetch via `useQueries`)
- `linked_events` query (batch query, not N+1, not ORM relationships)

All existing tests should continue to pass. The four schema fixes are backward-compatible (adding nullable fields).
