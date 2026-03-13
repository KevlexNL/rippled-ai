# Phase 07 — Source Connectors: Completion

**Completed:** 2026-03-13
**Commit:** feat(phase-07): source connectors — email (IMAP + webhook), slack events, meeting transcripts

---

## What Was Built

### Normalisation Layer (`app/connectors/`)

- **`shared/quoted_email_stripper.py`** — Strips `> quoted` lines and reply dividers (Outlook, Gmail) from email bodies. Returns `(stripped_body, is_quoted_content: bool)`.
- **`shared/participant_classifier.py`** — Classifies email addresses as internal/external using `INTERNAL_DOMAINS` env var.
- **`shared/ingestor.py`** — Sync ingest-and-enqueue utility for Celery tasks. Includes `get_or_create_source_sync()` for source upsert and `ingest_item()` with deduplication.
- **`email/schemas.py`** — `SendGridInboundEmail` and `RawEmailPayload` Pydantic schemas.
- **`email/normalizer.py`** — Maps `RawEmailPayload` → `SourceItemCreate`. Handles quoted stripping, participant classification, thread ID extraction from References/In-Reply-To headers.
- **`email/imap_poller.py`** — IMAP4/SSL polling. Fetches unseen from INBOX and Sent, parses RFC822 messages, normalises, and ingests. Tracks last poll implicitly via UNSEEN flag.
- **`slack/verifier.py`** — Slack HMAC-SHA256 signature verification per Slack's documented algorithm. Includes 5-minute replay protection.
- **`slack/normalizer.py`** — Maps Slack event dict → `SourceItemCreate`. Filters bots, `message_changed` events, unsupported subtypes. Parses `ts` as Unix timestamp for `occurred_at`.
- **`meeting/schemas.py`** — `TranscriptSegment` and `MeetingTranscriptPayload` Pydantic schemas.
- **`meeting/normalizer.py`** — One `SourceItemCreate` per meeting. Full transcript as `[Speaker]: text` lines; segments stored in `metadata_["segments"]`.

### Webhook Routes (`app/api/routes/webhooks/`)

- **`email.py`** — `POST /api/v1/webhooks/email/inbound`. Auth: `X-User-ID` + optional `X-Email-Webhook-Secret`. Source auto-created on first use (upsert on `from_email`). 409 on duplicate.
- **`slack.py`** — `POST /api/v1/webhooks/slack/events`. HMAC-SHA256 signature verification (when `SLACK_SIGNING_SECRET` set). URL verification challenge handled. Acks immediately; dispatches `process_slack_event.delay()` to Celery.
- **`meetings.py`** — `POST /api/v1/webhooks/meetings/transcript`. Auth: `X-Rippled-Webhook-Secret` (when `MEETING_WEBHOOK_SECRET` set) or `X-User-ID` fallback. Returns `SourceItemRead` on 201.

### Celery Tasks (`app/tasks.py`)

- **`process_slack_event`** — Normalises Slack event and ingests as SourceItem. Auto-creates Source. Retries up to 3×.
- **`poll_email_imap`** — Beat task every 300s. Calls `poll_new_messages()`. Skips gracefully if IMAP not configured.

---

## Test Count

| File | Tests |
|------|-------|
| `tests/connectors/test_quoted_stripper.py` | 8 |
| `tests/connectors/test_participant_classifier.py` | 5 |
| `tests/connectors/test_email_normalizer.py` | 13 |
| `tests/connectors/test_slack_verifier.py` | 6 |
| `tests/connectors/test_slack_normalizer.py` | 10 |
| `tests/connectors/test_meeting_normalizer.py` | 7 |
| `tests/api/test_webhook_slack.py` | 6 |
| `tests/api/test_webhook_email.py` | 5 |
| `tests/api/test_webhook_meetings.py` | 5 |
| **New total** | **65** |
| Prior passing | 255 |
| **Grand total** | **320** |

All 320 tests pass. No regressions.

---

## New Env Vars Required

| Var | Default | Purpose |
|-----|---------|---------|
| `IMAP_HOST` | `""` | IMAP server hostname |
| `IMAP_PORT` | `993` | IMAP port |
| `IMAP_USER` | `""` | IMAP username / email address |
| `IMAP_PASSWORD` | `""` | IMAP password or app password |
| `IMAP_SSL` | `True` | Use IMAP4_SSL |
| `IMAP_SENT_FOLDER` | `"Sent"` | Folder name for sent mail |
| `EMAIL_WEBHOOK_SECRET` | `""` | Optional HMAC secret for email webhook |
| `INTERNAL_DOMAINS` | `""` | Comma-separated internal email domains |
| `SLACK_SIGNING_SECRET` | `""` | Slack app signing secret for HMAC verification |
| `SLACK_BOT_TOKEN` | `""` | Slack bot token (optional, for future API use) |
| `SLACK_TEAM_ID` | `""` | Slack workspace/team ID |
| `SLACK_USER_ID` | `""` | The Rippled user's Slack user ID (MVP single user) |
| `MEETING_WEBHOOK_SECRET` | `""` | Optional webhook secret for meeting transcript endpoint |

---

## Decisions Made During Implementation

- **Q1 (meeting granularity):** One SourceItem per meeting. Full transcript as content, segments in `metadata_["segments"]`.
- **Q2 (email path):** Both IMAP and inbound webhook implemented. IMAP is the primary path.
- **Q3 (Slack edits):** `message_changed` events ignored for MVP.
- **Q4 (source auto-creation):** Upsert on `(user_id, source_type, provider_account_id)` in all connectors. No manual pre-registration required.
- **Q5 (credentials):** Global env vars only for MVP. `Source.credentials` column unused.
- **Q6 (Slack thread context):** Trust existing thread linkage via `thread_id`. No Slack API fetch.
- **Q7 (meeting auth):** `X-Rippled-Webhook-Secret` header when `MEETING_WEBHOOK_SECRET` is set; falls back to `X-User-ID` header (existing auth pattern).
- **Bug fixed during implementation:** Duplicate `from datetime import timezone` inside `normalise_email()` caused `UnboundLocalError` — removed the inner import, using the module-level one.
- **IMAP user ID for `poll_email_imap`:** Reuses `SLACK_USER_ID` as the single MVP user ID. Should be renamed to a generic `RIPPLED_USER_ID` in a future phase.
