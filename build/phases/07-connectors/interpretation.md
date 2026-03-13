# Phase 07 — Source Connectors: Interpretation

**Stage:** STAGE 2 — INTERPRET
**Date:** 2026-03-13

---

## 1. Summary Understanding

Phases 01–06 built a complete intelligence pipeline: schema, detection, clarification, completion detection, and surfacing. But that pipeline is currently starved — `SourceItem` rows only arrive if something calls `POST /source-items` manually. No real data flows through automatically.

Phase 07 closes that gap. It is the ingestion layer — the set of connectors that translate raw payloads from email, Slack, and meeting providers into normalised `SourceItem` rows that immediately feed into the existing pipeline.

**What Phase 07 delivers:**

1. A normalisation layer that converts raw provider payloads into validated `SourceItemCreate` objects for any of the three source types.
2. A Slack connector — an Events API webhook handler that receives `message.channels`, `message.im`, `message.groups`, and `message_changed` events from Slack.
3. An email connector — both an inbound webhook endpoint (for providers such as SendGrid Inbound Parse) and an IMAP polling task (for direct mailbox access without routing rules).
4. A meeting transcript connector — an HTTP endpoint that accepts a structured transcript payload (meeting_id, participants, segments with speaker labels and timestamps) from any upstream recording/transcription tool.
5. Celery tasks for async event processing and IMAP polling.
6. Security: webhook signature verification for Slack, optional signature verification for email webhooks.

**Why this matters:**

Without connectors, Rippled is a pipeline with no input. Phases 01–06 proved the model works end-to-end with manual data. Phase 07 makes it work with real communication — the product thesis can now be tested against actual user activity.

---

## 2. Scope Decision

### What Phase 07 includes

- Normalisation layer (all three source types)
- Email: inbound webhook handler + IMAP polling Celery task
- Slack: Events API webhook handler
- Meeting: transcript HTTP endpoint
- Connector-specific Pydantic schemas for inbound payloads
- Quoted content detection/stripping (email) and is_quoted_content flagging
- Internal vs external participant classification
- Celery tasks for async Slack event processing and IMAP polling
- Webhook signature verification
- Migrations for any new config fields needed

### What Phase 07 explicitly excludes

- Native meeting recorder or meeting bot infrastructure (brief says: use upstream providers)
- Reactions-based Slack inference (brief: out of scope for MVP)
- Calendar as a source (out of scope per all three briefs)
- Attachment content analysis (out of scope for MVP beyond metadata)
- OAuth flows for Slack or email (connectors assume credentials are pre-configured via env/secrets)
- Multi-user workspace scenarios

### Co-hosted vs separate service

**Recommendation: co-hosted in the existing FastAPI app under `app/connectors/`.**

Reasoning:

| Factor | Co-hosted | Separate service |
|---|---|---|
| Railway deployment | One existing service — no new deployment unit | New Railway service, new env, new routing |
| Secrets | Already solved via `.env` / pydantic-settings | Must duplicate or share via environment |
| Internal calls | Normaliser can call DB directly; no HTTP round-trip | Must call internal API — adds latency and auth complexity |
| Failure isolation | Connector failure could affect API | Better isolation, but overkill for one user MVP |
| Developer velocity | One repo, one test run, one deploy | More moving parts, slower iteration |
| IMAP polling | Celery beat task — already running | Needs own process |

For MVP with a single target user, the blast radius is small and the operational overhead of a separate service is not justified. The connectors are logically distinct (in `app/connectors/`) but physically co-located with the FastAPI app.

If usage grows to multi-user scale or connector latency becomes an API concern, extracting to a separate service is straightforward — the interfaces are clean.

---

## 3. Key Findings from Existing Codebase

### What's already there

**`Source` model (`app/models/orm.py:39`):**
- `source_type`: `meeting | slack | email` — the enum is exact (see `SourceType` in `app/models/enums.py:6`)
- `credentials: JSONB` column — exists but currently unused. Perfect for storing per-source secrets (IMAP password, Slack bot token, webhook secret) in encrypted form.
- `provider_account_id` — for Slack workspace ID, email address, meeting account ID
- `metadata_: JSONB` — for arbitrary source configuration

**`SourceItem` model (`app/models/orm.py:54`):**
The schema is already fully normalised for all three source types:
- `external_id` — message_ts for Slack, Message-ID for email, `{meeting_id}` for meetings
- `thread_id` — Slack thread_ts / email thread reference / meeting_id
- `direction` — `inbound | outbound | None` (email and meetings use this)
- `sender_id / sender_name / sender_email` — per-source participant
- `is_external_participant` — for internal/external classification
- `content / content_normalized` — raw vs normalised text
- `has_attachment / attachment_metadata` — email attachments, shared files
- `recipients: JSONB` — list of recipient dicts
- `source_url` — Slack permalink, email message URL, meeting recording URL
- `is_quoted_content: Boolean` — already exists for Phase 05's email suppression logic
- `metadata_: JSONB` — source-native data (Slack channel ID, email headers, meeting segments)

**Ingestion endpoints (`app/api/routes/source_items.py`):**
- `POST /source-items` — single item, deduplication on `(source_id, external_id)`, auto-enqueues `detect_commitments.delay()`
- `POST /source-items/batch` — up to 100 items, per-item result, same enqueue behaviour
- Deduplication returns 409 with `existing_id` — connectors can safely use idempotent ingestion

**Celery infrastructure (`app/tasks.py`):**
Four tasks already running: `detect_commitments`, `run_clarification_batch`, `run_completion_sweep`, `recompute_surfacing`. The Celery beat schedule pattern is established. Adding new periodic tasks is straightforward.

**Config pattern (`app/core/config.py:1`):**
`pydantic_settings.BaseSettings` with `env_file=".env"`. New connector-specific env vars follow this exact pattern.

### What's missing

1. **No inbound webhook routes** — no `/webhooks/` prefix, no Slack event endpoint, no email endpoint, no meeting transcript endpoint.
2. **No connector normalisation code** — nothing that translates Slack event JSON, email payload, or transcript JSON into `SourceItemCreate`.
3. **No IMAP polling logic** — no email polling task.
4. **No webhook signature verification** — no HMAC verification utility.
5. **No quoted content stripping for incoming email** — Phase 05 has suppression patterns for detection, but there's no pre-ingestion stripper that sets `is_quoted_content=True` on email replies.
6. **No participant domain classifier** — nothing that determines internal vs external based on email domain.
7. **`credentials` field on `Source` is unpopulated** — connectors will need a pattern for reading per-source credentials (or use global env vars for MVP).

### Gotchas

1. **Slack 3-second response requirement.** Slack Events API requires a 200 response within 3 seconds. Connector endpoint must ack immediately and dispatch to Celery. It cannot run normalisation synchronously.

2. **Slack URL verification challenge.** On first setup, Slack sends a `challenge` payload to verify the endpoint. The webhook handler must handle this before event processing.

3. **Slack message edits and the dedup constraint.** The existing `(source_id, external_id)` unique constraint on `source_items` means that if we use the Slack message `ts` as `external_id`, an edited message will hit 409. Options: ignore edits (simplest), create a new SourceItem with a modified external_id like `{ts}_edit_{edit_ts}`, or PATCH the existing item (no PATCH endpoint exists). See Open Question Q3.

4. **Email `is_quoted_content` must be set at ingestion time.** Phase 05's `completion/matcher.py` checks `is_quoted_content` before processing. Connectors must strip quoted content from the normalised body and set this flag correctly — this is a correctness requirement, not an optimisation.

5. **Source pre-registration dependency.** The `POST /source-items` endpoint requires a valid `source_id` belonging to the authenticated user. Connectors must know the `source_id` for each source type. This implies the user registers their email, Slack, and meeting sources via `POST /sources` before connectors can ingest. See Open Question Q7.

6. **`user_id` is always the Rippled account owner.** Slack events and email threads involve many participants, but `SourceItem.user_id` should always be the Rippled user whose account owns the source. The connector must look up the owning user from the source record, not from the message sender.

---

## 4. Implementation Plan

### A. Normalisation Layer

**A1. `app/connectors/__init__.py`**
Package init. Exports `normalise_email`, `normalise_slack_event`, `normalise_meeting_transcript` as the public surface.

**A2. `app/connectors/shared/quoted_email_stripper.py`**
Purpose: Given a raw email body (plain text or HTML stripped to plain), return `(body_without_quotes, is_quoted_content: bool)`.
Key decisions:
- Strip lines starting with `>` (standard quote prefix)
- Strip content after common reply dividers (`------ Original Message ------`, `On <date>, <sender> wrote:`, `From:` at start of line in reply context)
- Return `is_quoted_content=True` if any quoted block was found AND the new body is materially shorter than the original (not just whitespace)
- This is a pure function — no DB, no external calls. Fully testable.
- Reuse/complement the `EMAIL_SUPPRESSION_PATTERNS` already in Phase 05 (`app/services/completion/matcher.py` vicinity)

**A3. `app/connectors/shared/participant_classifier.py`**
Purpose: Given sender email and a list of recipient emails, classify each as internal or external.
Strategy: Compare domains against a configurable `INTERNAL_DOMAINS` setting (comma-separated list in `.env`). If sender domain is in `INTERNAL_DOMAINS`, `is_external_participant=False`. Otherwise `True`.
Key decision: For MVP with one user, `INTERNAL_DOMAINS` is a required env var. Returns `bool`.

**A4. `app/connectors/email/normalizer.py`**
Purpose: Translate a raw inbound email payload (dict from SendGrid/Mailgun/IMAP) into a list of `SourceItemCreate` objects.
Inputs:
- `message_id` → `external_id`
- `in_reply_to` / `references` headers → `thread_id` (use top-level `Message-ID` of thread)
- `from_` → `sender_name`, `sender_email`
- `to` / `cc` → `recipients` list
- `direction`: `inbound` (received) or `outbound` (sent, from IMAP Sent folder)
- `subject`, `body_plain`, `body_html` → content (prefer plain text; strip HTML if needed)
- `date` → `occurred_at`
- `attachments` metadata → `has_attachment`, `attachment_metadata`
- Call `quoted_email_stripper` on body → set `content`, `content_normalized`, `is_quoted_content`
- Call `participant_classifier` on sender → set `is_external_participant`
- Raw email headers → `metadata_`

**A5. `app/connectors/slack/normalizer.py`**
Purpose: Translate a Slack `message` event payload into a `SourceItemCreate`.
Inputs:
- `event.ts` → `external_id`
- `event.thread_ts` (or `event.ts` if top-level) → `thread_id`
- `event.user` → `sender_id`; resolve display name from `event.user_profile.display_name` or fallback to `event.user`
- `event.channel` → store in `metadata_`
- `event.text` → `content`
- `event.files` metadata → `has_attachment`, `attachment_metadata`
- `event.permalink` or construct from channel/ts → `source_url`
- All Slack messages are `direction=None` (Slack has no inbound/outbound concept from one user's perspective)
- `is_external_participant=False` for workspace messages (if user is in the same Slack team); `True` for Connect/external channels — use `SLACK_TEAM_ID` env var to classify

**A6. `app/connectors/meeting/normalizer.py`**
Purpose: Translate a transcript payload into a single `SourceItemCreate`.
Strategy: **One SourceItem per meeting**, not per segment.
Reasoning: The `detect_commitments` task is a single AI call per `SourceItem`. Processing 100+ segments as individual items would generate 100+ AI calls per meeting. One item per meeting gives the detector the full transcript context needed to identify commitment patterns across speaker turns. The segments are stored in `metadata_` for traceability.
Content: `content` = full transcript as `"[Speaker]: text\n"` lines (normalised for detection). `content_normalized` = same but stripped of filler words if needed.
Inputs:
- `meeting_id` → `external_id` and `thread_id`
- `started_at` → `occurred_at`
- `participants` → `recipients` list, `sender_name` = meeting organiser if available
- `segments` → serialised into `metadata_["segments"]`
- `meeting_title` → `metadata_["title"]`
- `source_url` → `source_url`
- `direction = None` (meetings have no direction)
- `is_external_participant`: True if any participant is external (based on domain classification)

### B. Email Connector

**B1. `app/connectors/email/schemas.py`**
Pydantic schemas for inbound email payloads. Two variants:
- `SendGridInboundEmail` — SendGrid Inbound Parse format fields
- `RawEmailPayload` — generic normalised format for IMAP-fetched emails
Both validated with strict types. `occurred_at` is always timezone-aware.

**B2. `app/api/routes/webhooks/__init__.py` and `app/api/routes/webhooks/email.py`**
`POST /webhooks/email/inbound` — receives inbound email from SendGrid/Mailgun.
Security: verify optional webhook signature header (`X-Twilio-Email-Event-Webhook-Signature` or equivalent). For MVP, signature verification is a config-flag-enabled feature — if `EMAIL_WEBHOOK_SECRET` is set, verify; otherwise accept (for testing convenience). Log a warning if verification is disabled.
Flow:
1. Parse payload via `SendGridInboundEmail` schema
2. Look up `Source` record for `source_type=email`, `user_id` from header auth
3. Call `normalise_email(payload, source_id)` → list of `SourceItemCreate`
4. For each: call internal `_ingest_source_item(item, user_id, db)` (shared with HTTP endpoint logic)
5. Return `{"accepted": count}` with 200

Note: email webhooks are synchronous (unlike Slack). Email providers generally tolerate a few seconds of processing time.

**B3. `app/connectors/email/imap_poller.py`**
Purpose: Connect to a mailbox via IMAP, fetch unseen messages from INBOX and Sent, normalise, and ingest.
Key decisions:
- Use `imaplib` (stdlib) or `aioimaplib` for async IMAP. For a Celery task (sync), `imaplib` is sufficient.
- Poll INBOX for received mail, Sent folder for outbound (outbound is strong completion evidence per brief)
- Track last poll time via a `Source.metadata_` field (`last_polled_at`) to fetch only new messages
- Batch ingest via `POST /source-items/batch` internal call — or direct DB insert + enqueue

New env vars: `IMAP_HOST`, `IMAP_PORT` (default 993), `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_SSL` (default True), `IMAP_SENT_FOLDER` (default "Sent")

**B4. `app/tasks.py` — add `poll_email_imap` task**
Beat schedule: every 5 minutes. Calls `imap_poller.poll_new_messages(source_id, db)`.

### C. Slack Connector

**C1. `app/connectors/slack/verifier.py`**
Purpose: Verify `X-Slack-Signature` HMAC-SHA256 header against `X-Slack-Request-Timestamp` + raw body.
Slack's signing algorithm is documented and deterministic. This is a pure function:
```python
def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool
```
Returns `False` if timestamp is >5 minutes old (replay attack protection). Raises `401` on failure.

**C2. `app/api/routes/webhooks/slack.py`**
`POST /webhooks/slack/events`
Flow:
1. Read raw body bytes (before FastAPI parses JSON — needed for HMAC verification)
2. Verify `X-Slack-Signature` via `verifier.verify_slack_signature()`
3. If payload contains `"type": "url_verification"` → return `{"challenge": event["challenge"]}` immediately
4. Return `{"ok": true}` immediately (Slack requires <3s response)
5. Dispatch `process_slack_event.delay(payload)` to Celery

No user auth header needed — Slack Events API doesn't support Bearer tokens. The signing secret IS the auth mechanism. The Slack source is looked up by `SLACK_TEAM_ID` env var.

**C3. `app/tasks.py` — add `process_slack_event` task**
Celery task (async worker, not beat schedule):
1. Parse the event payload
2. Filter to supported event types: `message`, `message_changed` (and subtypes: `message_replied`, `file_share`)
3. Skip bot messages (`event.bot_id` present) and our own app's messages
4. Look up `Source` record for `source_type=slack`, `user_id` (resolved from `SLACK_USER_ID` env var for MVP)
5. Call `normalise_slack_event(event, source_id, user_id)` → `SourceItemCreate | None`
6. If `None` (filtered): return
7. Call internal ingest function → `SourceItem` row + enqueue detection

New env vars: `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN` (optional, for user info resolution), `SLACK_TEAM_ID`, `SLACK_USER_ID` (the Rippled user's Slack user ID — for determining relevant message direction)

### D. Meeting Transcript Connector

**D1. `app/connectors/meeting/schemas.py`**
```python
class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    start_seconds: float
    end_seconds: float

class MeetingTranscriptPayload(BaseModel):
    meeting_id: str
    meeting_title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[dict]           # {"name": "...", "email": "..."}
    segments: list[TranscriptSegment]
    source_url: str | None = None
    metadata: dict | None = None
```

**D2. `app/api/routes/webhooks/meetings.py`**
`POST /webhooks/meetings/transcript`
Authentication: standard Bearer token (same `get_current_user_id` dependency used everywhere else). Meeting connectors are first-party callers (our own integration code or a human/script), so Bearer auth is appropriate — no special webhook signing needed.
Flow:
1. Validate payload via `MeetingTranscriptPayload`
2. Look up `Source` record for `source_type=meeting`, `user_id`
3. Call `normalise_meeting_transcript(payload, source_id, user_id)` → `SourceItemCreate`
4. Ingest → `SourceItem` row + enqueue detection
5. Return `SourceItemRead`

Idempotency: `external_id = meeting_id`. Re-submitting the same meeting returns 409 with `existing_id`. Callers should treat 409 as success.

### E. Celery Tasks and Pipeline Wiring

**E1. Router registration (`app/main.py` update)**
Register the new webhook router:
```python
from app.api.routes.webhooks import email, slack, meetings
app.include_router(email.router, prefix="/api/v1")
app.include_router(slack.router, prefix="/api/v1")
app.include_router(meetings.router, prefix="/api/v1")
```

**E2. `app/tasks.py` additions**
- `process_slack_event(payload: dict)` — Celery task, called from Slack webhook handler
- `poll_email_imap()` — Celery beat task, schedule every 300s (5 minutes)

Beat schedule addition:
```python
"email-imap-poll": {
    "task": "app.tasks.poll_email_imap",
    "schedule": 300.0,  # 5 minutes
},
```

**E3. Shared internal ingest utility**
Extract the ingest-and-enqueue logic from `source_items.py` into a shared utility `app/connectors/shared/ingestor.py`:
```python
def ingest_item(item: SourceItemCreate, user_id: str, db: Session) -> SourceItem
```
Both the connector code and the existing HTTP route can call this. This avoids duplicating the dedup/enqueue logic.

### F. Tests

**F1. `tests/connectors/test_email_normalizer.py`**
- Plain text email → correct SourceItemCreate fields
- Email with quoted content → `is_quoted_content=True`, body stripped
- Outbound email (from Sent folder) → `direction="outbound"`
- Email with attachments → `has_attachment=True`, `attachment_metadata` populated
- External sender → `is_external_participant=True`
- Internal sender (same domain as INTERNAL_DOMAINS) → `is_external_participant=False`
- Missing `Date` header → raises validation error
- Email with only quoted content (reply that adds nothing) → content is minimal, `is_quoted_content=True`

**F2. `tests/connectors/test_quoted_stripper.py`**
- Body with `>` quoted lines → stripped
- Body with `On <date>, <sender> wrote:` divider → stripped below divider
- Body with both types → both stripped
- Body with no quotes → unchanged, `is_quoted_content=False`
- Quoted content in middle of new content → only quote block stripped

**F3. `tests/connectors/test_participant_classifier.py`**
- Sender from internal domain → `is_external_participant=False`
- Sender from external domain → `is_external_participant=True`
- Mixed recipients (some internal, some external) → classification per participant

**F4. `tests/connectors/test_slack_normalizer.py`**
- Standard channel message → `SourceItemCreate` with correct fields
- Thread reply → `thread_id` set to parent `ts`
- Top-level message → `thread_id` == `external_id`
- Message with file attachment → `has_attachment=True`
- Bot message → filtered (returns `None`)
- `message_changed` event → new item with `_edit` external_id suffix (or per Q3 decision)

**F5. `tests/connectors/test_slack_verifier.py`**
- Valid signature + recent timestamp → `True`
- Invalid signature → `False`
- Timestamp >5 minutes old → `False` (replay protection)
- Empty signing secret (misconfigured) → raises config error

**F6. `tests/connectors/test_meeting_normalizer.py`**
- Full transcript → single `SourceItemCreate` with correct `content` (speaker-labelled lines)
- Segments stored in `metadata_["segments"]`
- `occurred_at` = `started_at`
- `external_id` = `meeting_id`, `thread_id` = `meeting_id`
- Participants serialised into `recipients`
- External participant detected → `is_external_participant=True`

**F7. `tests/api/test_webhook_slack.py`**
- URL verification challenge → `{"challenge": "..."}` returned
- Valid signed event → 200, Celery task dispatched (mocked)
- Invalid signature → 401
- Valid event, Celery unavailable → 200 (graceful degradation, fire-and-forget)

**F8. `tests/api/test_webhook_email.py`**
- Valid payload, no signature configured → 200, item ingested
- Valid payload, correct signature → 200
- Valid payload, wrong signature (when verification enabled) → 403
- Duplicate message_id → 409 with existing_id

**F9. `tests/api/test_webhook_meetings.py`**
- Valid transcript, authenticated → 201, SourceItemRead returned
- Unauthenticated request → 401
- Duplicate meeting_id → 409 with existing_id
- Missing required fields → 422

### G. Documentation

**G1. `build/phases/07-connectors/decisions.md`**
Record architectural decisions: co-hosting rationale, per-meeting vs per-segment, Slack ack pattern.

**G2. `app/connectors/README.md`**
How to register a new Source for each type, what env vars each connector needs, how to test locally.

**G3. Config additions in `app/core/config.py`**
New optional fields:
```python
# Email connector
imap_host: str = ""
imap_port: int = 993
imap_user: str = ""
imap_password: str = ""
imap_sent_folder: str = "Sent"
email_webhook_secret: str = ""
internal_domains: str = ""   # comma-separated

# Slack connector
slack_signing_secret: str = ""
slack_bot_token: str = ""
slack_team_id: str = ""
slack_user_id: str = ""      # the Rippled user's Slack user ID
```

---

## 5. Data Flow Diagram

```
External providers                          Rippled (FastAPI + Celery)
────────────────────                        ─────────────────────────────────────────────

Email provider (IMAP)  ──poll every 5m──→   Celery beat: poll_email_imap
                                                   │
                                                   │ imaplib: fetch unseen from INBOX + Sent
                                                   │
Email inbound webhook  ──POST──────────→   POST /webhooks/email/inbound
(SendGrid / Mailgun)                               │
                                                   ↓
                                        [email normalizer]
                                        • quoted_email_stripper → is_quoted_content
                                        • participant_classifier → is_external_participant
                                        • parse headers → thread_id, direction, recipients
                                                   │
                                                   ↓

Slack Events API       ──POST──────────→   POST /webhooks/slack/events
                                        • verify X-Slack-Signature
                                        • return 200 immediately
                                        • dispatch Celery: process_slack_event
                                                   │
                                                   ↓ (Celery worker)
                                        [slack normalizer]
                                        • filter bots, unsupported subtypes
                                        • resolve thread_id, sender, attachments
                                                   │
                                                   ↓

Meeting provider       ──POST──────────→   POST /webhooks/meetings/transcript
(Fireflies / Otter /                    • Bearer auth (standard)
 custom script)                         [meeting normalizer]
                                        • segments → one SourceItem per meeting
                                        • full transcript as content
                                        • segments in metadata_
                                                   │
                                                   ↓
                                    ─────────────────────────────
                                    Shared ingestor
                                    • SourceItemCreate validated
                                    • deduplicate on (source_id, external_id)
                                    • INSERT into source_items
                                    • detect_commitments.delay(source_item_id)
                                    ─────────────────────────────
                                                   │
                                                   ↓ (Celery worker)
                                    detect_commitments(source_item_id)
                                    → CommitmentCandidate rows
                                                   │
                                                   ↓ (Celery beat, 5min)
                                    run_clarification_batch
                                    → CommitmentCandidate promoted/discarded
                                    → Commitment rows (lifecycle_state=active)
                                                   │
                                                   ↓ (Celery beat, 10min)
                                    run_completion_sweep
                                    → CommitmentSignal (delivery)
                                    → lifecycle_state transitions
                                                   │
                                                   ↓ (Celery beat, 30min)
                                    recompute_surfacing
                                    → surfaced_as = main / shortlist / clarifications
                                    → SurfacingAudit rows
                                                   │
                                                   ↓
                                    GET /surface/main
                                    GET /surface/shortlist
                                    GET /surface/clarifications
```

---

## 6. Open Questions for Trinity

### Q1: Meeting granularity — one SourceItem per meeting or per speaker turn?

**Question:** Should we create one `SourceItem` per full meeting transcript, or one per speaker turn?

**My recommendation: One per meeting.**

Per-segment would generate 50–200 SourceItems per typical 60-minute meeting, each triggering a separate `detect_commitments` AI call. This is impractical for cost and latency. One SourceItem per meeting passes the full transcript to the detector, which has better cross-turn context anyway.

If finer granularity is later needed (e.g., linking a commitment signal to a specific minute in a meeting), it can be derived from `metadata_["segments"]` rather than stored as separate rows.

**The risk:** A very long meeting (2h+) may produce a very long `content` string. Detection prompts may need to be chunked for long transcripts. This is a Phase 07 build concern, not a schema concern — the schema supports it today.

---

### Q2: Email ingestion path priority — webhook or IMAP?

**Question:** For MVP, should we prioritise the inbound webhook path (SendGrid) or IMAP polling?

**My recommendation: Implement both, with IMAP as the primary path.**

IMAP works with any email provider (Gmail, Outlook, iCloud) without routing rules. The user just provides credentials. This is the most universally applicable path.

Inbound webhooks (SendGrid Inbound Parse) require domain MX record changes or email forwarding setup — higher friction for initial testing, but lower latency and no polling overhead.

For MVP: implement both, default IMAP on (if credentials are set), webhook optional. The normaliser accepts both formats.

If Trinity wants to prioritise one: pick IMAP. It works today, no provider setup needed beyond app password configuration.

---

### Q3: How to handle Slack message edits?

**Question:** Slack sends `message_changed` events when a user edits a message. The original `ts` doesn't change. Our dedup constraint is on `(source_id, external_id)`. If we use `ts` as `external_id`, edits will hit 409.

**Options:**
1. **Ignore edits** — simplest. Only the original message is processed. Misses cases where a commitment phrase was added in an edit.
2. **New SourceItem with modified external_id** — create `{ts}_edit_{edit_ts}` as `external_id`. Creates a second SourceItem for the edited version. Simple, but could create double-detection.
3. **PATCH existing SourceItem** — update the original item's content. Requires a new PATCH endpoint and changes the idempotency guarantee.

**My recommendation: Option 1 (ignore edits) for MVP.**

The brief does note "message edits may change interpretation" — but adds this as a product rule, not a hard MVP requirement. Missing occasional edits is an acceptable MVP trade-off. Implementing edit tracking correctly requires resolving whether the original detection should be invalidated, which is significant complexity. Revisit in a later phase.

---

### Q4: Source pre-registration requirement — auto-create or manual?

**Question:** The ingest endpoint requires a valid `source_id`. Connectors must know the `source_id` for the authenticated user's email/Slack/meeting source. Currently, sources are created manually via `POST /sources`.

**Options:**
1. **Manual pre-registration required** — user calls `POST /sources` for each type. Connectors read `source_id` from env var or config. Simple, explicit.
2. **Auto-create source on first use** — connector does `INSERT OR GET` on Source table, keyed by `(user_id, source_type, provider_account_id)`. No env var needed for source_id.

**My recommendation: Auto-create source on first use (Option 2).**

For a developer/MVP user trying to test the system, requiring a manual API call before running a connector adds friction. Auto-creation with idempotent upsert is safer UX, and the logic is simple (SELECT-or-INSERT on the Sources table). The `provider_account_id` can be set from the IMAP username, Slack team ID, etc.

If Trinity prefers explicit pre-registration, I'll add a `SOURCE_ID_EMAIL`, `SOURCE_ID_SLACK`, `SOURCE_ID_MEETING` env var pattern instead.

---

### Q5: How should `Source.credentials` be used, if at all?

**Question:** The `credentials: JSONB` column on `Source` exists but is unused. For connectors, we need per-source secrets (IMAP password, Slack bot token). Should we:

1. **Store credentials in `Source.credentials` (encrypted or plaintext)** — makes sources self-contained, supports multi-user future
2. **Use global env vars for MVP** — simpler, no encryption concern, works for single user

**My recommendation: Global env vars for MVP.**

Storing credentials in the database — even encrypted — introduces key management complexity (what key? rotated how?). For a single-user MVP, env vars are standard practice and Railway handles them securely. The `credentials` column stays available for future multi-user credential storage.

---

### Q6: Should the Slack connector fetch thread context via API for replies?

**Question:** When Slack sends a `message` event for a thread reply, the event payload includes the reply text and thread_ts, but not the parent message text. For commitment detection, context matters — the reply "I'll handle it" means nothing without the parent message.

**Options:**
1. **Fetch thread context via Slack API** — use `SLACK_BOT_TOKEN` and `conversations.replies` API call to get the full thread. Adds latency and a Slack API dependency.
2. **Trust the existing thread continuity logic** — Phase 05's matcher already uses `thread_id` to link related SourceItems. If the parent message was already ingested, the detector has prior context.
3. **Store parent message content in `metadata_`** — if `event.message` is present in the `message_changed` payload, capture it.

**My recommendation: Option 2 for MVP.** Trust the existing thread linkage. If the parent message was already ingested (which it will be for any active conversation), the detection context is preserved via `thread_id`. Fetching thread context on every reply creates a Slack API rate-limit dependency. Revisit if detection quality is poor on Slack replies.

---

### Q7: Authentication model for the meeting transcript endpoint

**Question:** The meeting endpoint uses standard Bearer auth. But meeting providers (Fireflies, Otter, Zoom) send webhooks with their own signing mechanisms — not Bearer tokens.

**Options:**
1. **Bearer token** — works for first-party callers (scripts, custom integrations), not for provider-native webhooks
2. **Provider-specific signature verification** — like Slack, each provider has its own HMAC scheme
3. **Shared webhook secret via header** — `X-Webhook-Secret` compared against an env var

**My recommendation: Option 3 (shared webhook secret) for MVP.**

A simple `X-Rippled-Webhook-Secret` header check is provider-agnostic. Any meeting provider that supports custom webhook headers can send it. Providers that don't support custom headers can use a first-party script to relay transcripts. The secret is configured via `MEETING_WEBHOOK_SECRET` env var.

If `MEETING_WEBHOOK_SECRET` is unset, fall back to Bearer auth (for script/testing use). This mirrors the email webhook pattern from B2 above.

---

## 7. Confidence & Blockers

**Confidence: High.**

The existing `SourceItem` schema is already normalised for all three source types — no migration work anticipated. The ingestion pipeline is solid. The Celery infrastructure is established. The connectors are primarily translation work: parse external format → produce `SourceItemCreate` → call shared ingestor.

The main technical complexity lives in:
- Slack signature verification (well-documented, deterministic)
- Email quoted content stripping (well-understood problem with established patterns)
- Meeting transcript normalisation (controlled by us — we define the schema)

**Dependencies:**
- Phases 01–06 complete — yes, per git log
- `SourceItem` model supports all needed fields — confirmed
- Celery beat already running — confirmed
- `detect_commitments` already fires on ingest — confirmed

**Potential blockers:**
- **Q4 (source auto-creation)**: If Trinity wants manual registration, connector code is simpler but UX friction is higher. Awaiting decision.
- **Q3 (Slack edits)**: If Trinity wants edit tracking, scope expands. The recommendation is to defer.
- **IMAP credentials for local dev**: Developer needs a real or test mailbox. Can use a Gmail app password or a local mail server for testing. Not a blocker but worth noting.

No architectural surprises. No new tables required (at this stage — may need a `connector_cursors` or `source_poll_state` concept if per-source poll tracking gets complex, but `Source.metadata_` can carry `last_polled_at` for MVP).

---

## 8. Test Strategy

**Approach:** Same pattern as prior phases — pure unit tests using `SimpleNamespace` for duck-typed ORM objects where needed, FastAPI `TestClient` for webhook endpoints, mocked Celery for async dispatch.

**Coverage priorities (in order):**

1. Normaliser correctness — correct field mapping, quoted content handling, external participant detection
2. Webhook security — Slack signature verification, email signature verification (when enabled), replay protection
3. Idempotency — duplicate ingest returns 409 gracefully; connectors handle this without crashing
4. Pipeline hookup — SourceItem is created AND `detect_commitments.delay()` is called
5. Filtering — bot messages filtered, unsupported event types filtered, `is_quoted_content=True` items skipped downstream

**Test file targets:**

| File | Tests | Focus |
|---|---|---|
| `tests/connectors/test_email_normalizer.py` | 8–10 | Field mapping, quoted stripping, direction, attachments |
| `tests/connectors/test_quoted_stripper.py` | 6–8 | Stripping patterns, edge cases, false positives |
| `tests/connectors/test_participant_classifier.py` | 4–5 | Domain matching, mixed recipients |
| `tests/connectors/test_slack_normalizer.py` | 6–8 | Event types, thread_id, bot filter, attachment |
| `tests/connectors/test_slack_verifier.py` | 5–6 | Valid, invalid, expired, empty secret |
| `tests/connectors/test_meeting_normalizer.py` | 5–6 | Full transcript, segments in metadata, participants |
| `tests/api/test_webhook_slack.py` | 5–6 | Challenge, valid event, invalid sig, Celery ack |
| `tests/api/test_webhook_email.py` | 4–5 | Ingest, dedup, signature optional/required |
| `tests/api/test_webhook_meetings.py` | 4–5 | Auth, ingest, dedup, validation |

**Target total: 47–53 new tests**

All normaliser tests are pure functions — no DB, no Celery, no network. Webhook tests use `TestClient` with mocked DB and mocked `detect_commitments.delay`. IMAP poller tests mock `imaplib.IMAP4_SSL`.

The no-regression bar from prior phases:
```bash
pytest tests/services/ -q  # all prior phase tests must remain green
ruff check app/             # no new lint violations
```

---

*Interpretation written: 2026-03-13*
