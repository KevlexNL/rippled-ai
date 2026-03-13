# Phase 07 — Source Connectors

**Parent vision:** [Rippled - 7. MVP Scope Brief.md](../../briefs/Rippled%20-%207.%20MVP%20Scope%20Brief.md) requirement #1: *"at least one working ingestion path for each of the three source families"*

**Objective:** Deliver ingestion layer for email, Slack, and meeting transcripts. Convert raw provider payloads into normalised `SourceItem` rows that feed into the existing detection → clarification → completion → surfacing pipeline.

---

## What Ships in Phase 07

### 1. Normalisation Layer
- `SourceItem`-aware payload parser for each source type (email, Slack, meeting)
- Pydantic schemas for inbound payloads
- Conversion to validated `SourceItemCreate` objects
- Deduplication strategy per source type

### 2. Email Connector
- **Inbound webhook** (e.g., SendGrid Inbound Parse): HTTP endpoint receiving raw email payload
- **IMAP polling task**: Celery beat job polling IMAP mailbox (optional for MVP, required for multi-user scale)
- Quoted content detection & suppression (email threading)
- Internal vs external participant classification
- Attachment metadata extraction (no content analysis)
- Signature verification for webhook (SendGrid-compatible)

### 3. Slack Connector
- **Events API webhook handler**: Receives `message.channels`, `message.im`, `message.groups`, `message_changed` from Slack
- Thread awareness (reply_to_message_ts)
- Internal vs external classification (workspace members vs outside users)
- Reaction tracking (metadata only, not signal extraction)
- Signature verification per Slack specifications

### 4. Meeting Transcript Connector
- HTTP endpoint accepting structured transcript payload
- Schema: `meeting_id`, `provider_account_id`, `participants[]`, `segments[]` (with speaker, timestamp, text)
- No recording bot — assumes upstream tool (Otter, Fireflies, etc.) handles transcription
- Speaker/participant normalization

### 5. Integration
- All connectors register with existing `POST /source-items` endpoint (batch or single)
- Celery tasks for async processing (Slack events, IMAP polling)
- Beat schedule configuration (IMAP: every 5 min; Slack: immediate via webhook)

### 6. Security
- Webhook signature verification (Slack, email)
- Credentials stored in `Source.credentials` (JSONB, encryption at rest via DB)
- No OAuth flows (assume pre-configured via `.env` / secrets)

---

## Constraints & Exclusions

- **No OAuth:** Connectors assume credentials are pre-configured
- **No multi-workspace Slack:** Single workspace per Source record
- **No attachment content analysis** (metadata only)
- **No calendar as source** (out of scope)
- **No reactions-based inference** (Slack reactions → signals, out of MVP scope)
- **No multi-user:** Build for single test user
- **No attachment body parsing** (metadata only)

---

## Success Criteria

1. ✅ Email webhook receives payload, parses, creates SourceItem
2. ✅ IMAP polling task successfully fetches emails and creates SourceItems (can be basic/polling-based)
3. ✅ Slack webhook receives event, creates SourceItem with thread awareness
4. ✅ Meeting endpoint accepts transcript, creates SourceItem
5. ✅ Each source type deduplicates on `(source_id, external_id)`
6. ✅ Normalisation preserves all required SourceItem fields (sender, thread, direction, etc.)
7. ✅ Signature verification works for Slack and email webhook
8. ✅ All tests pass; ruff clean
9. ✅ No regressions in earlier phases (detection, clarification, completion, surfacing still work)

---

## Technical Notes

### Where it lives
- `app/connectors/` — new package
- `app/connectors/normalizer.py` — shared logic
- `app/connectors/email.py` — email normalization + webhook handler
- `app/connectors/slack.py` — Slack normalization + webhook handler
- `app/connectors/meeting.py` — meeting normalization + endpoint handler
- `app/api/routes/connectors.py` — webhook + endpoint routes
- `app/tasks.py` — Celery tasks (extend existing)
- `migrations/` — if needed for Source config

### What already exists
- `Source` model with `credentials`, `provider_account_id`, `metadata_` fields
- `SourceItem` model fully normalised for all three types
- `POST /source-items` endpoint (will wire connectors → here)
- Celery setup and beat schedule

### Dependencies
- `email-validator` (email parsing)
- `slackclient` or `slack-sdk` (if needed; can parse webhook JSON)
- `python-imap` or stdlib `imaplib` (IMAP polling)
- `hmac` + `hashlib` (signature verification — stdlib)

---

## Owner

**Trinity** orchestrates. **Claude Code** implements.

Build phase (A3): no context windows, no interrupts, just build.

---

## Reference

- Current SourceItem schema: `app/models/orm.py:54`
- Source model: `app/models/orm.py:39`
- SourceItemCreate: `app/models/schemas.py`
- Existing ingestion endpoint: `app/api/routes/source_items.py`
- Phase 06 output: surfacing pipeline ready to receive normalized data
