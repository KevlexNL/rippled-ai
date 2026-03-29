# WO-RIPPLED-SLACK-THREAD-ENRICHMENT

**Status:** PENDING
**Priority:** High
**Owner:** Trinity
**Created:** 2026-03-29
**Scope:** Rippled codebase — Slack connector enrichment

---

## Objective

Ensure that `NormalizedSignal` objects produced by the Slack connector contain full thread context, so the LLM detection pipeline can correctly interpret replies, updates, and follow-ups in relation to their parent messages — enabling accurate commitment lifecycle tracking across Slack threads.

---

## Context

Currently the Slack connector ingests individual messages without reliably attaching thread context. A reply like "done, sent it over" means nothing without the parent message it's replying to. The detection pipeline needs the full thread to correctly:
- Match completion signals to existing commitments
- Understand delegated tasks from thread replies
- Avoid creating duplicate commitments from thread replies

---

## Research Phase (Required First)

Before implementing, Trinity must:
1. Review current Slack connector at `app/connectors/slack/` — understand how messages are currently fetched and normalized
2. Check `NormalizedSignal` schema (`app/connectors/shared/normalized_signal.py`) — confirm `prior_context_text`, `source_thread_id`, and `thread_position` fields are available
3. Review Slack API: `conversations.replies` endpoint for fetching thread history
4. Document findings in a brief comment block at the top of the implementation

---

## Phases

### Phase 1 — Thread Fetching
- When a Slack message has a `thread_ts` (i.e. it's a reply or a parent with replies), fetch the full thread via `conversations.replies`
- Cache thread fetches to avoid redundant API calls within the same ingestion run
- Store thread messages as ordered list (oldest → newest)

### Phase 2 — NormalizedSignal Enrichment
- Populate `prior_context_text` with the thread history above the current message (formatted as: `[speaker]: message`)
- Set `source_thread_id` = `thread_ts`
- Set `thread_position` = index of current message within the thread (0-based)
- Set `source_message_id` = `ts` of the current message

### Phase 3 — Parent Message Linkage
- If the current message is a reply: attach the parent message as the first entry in `prior_context_text`
- If the current message is a parent with replies: include reply count in `metadata` for context scoring

### Phase 4 — Tests
- Unit test: thread fetching with mocked Slack API responses
- Unit test: `NormalizedSignal` enrichment with thread context
- Integration test: end-to-end ingestion of a Slack thread with a completion signal

---

## Success Criteria

- [ ] Slack replies include parent message in `prior_context_text`
- [ ] `source_thread_id` and `thread_position` populated for all threaded messages
- [ ] No duplicate `NormalizedSignal` objects created for thread fetches
- [ ] Existing Slack connector tests still pass
- [ ] At least 3 new unit tests added

---

## Files to Create/Modify

- `app/connectors/slack/thread_enricher.py` — new thread fetching + enrichment service
- `app/connectors/slack/slack_connector.py` — integrate thread enricher
- `tests/connectors/test_slack_thread_enrichment.py` — new tests

---

## Dependencies

- `WO-RIPPLED-SLACK-CONNECTOR-BUILD` (completed)
- `WO-RIPPLED-NORMALIZED-SIGNAL-CONTRACT` (completed)

---

## Notify When Done

Mero + Kevin via Rippled Telegram group
