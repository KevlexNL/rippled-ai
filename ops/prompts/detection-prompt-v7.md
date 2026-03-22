# Detection Prompt — ongoing-v9 / seed-v8

**Version:** ongoing-v9 (model detection), seed-v8 (seed detector)
**Date:** 2026-03-22
**Author:** Trinity
**Change from v6:** Added speech_act classification field (WO-RIPPLED-SPEECH-ACT-CLASSIFICATION)

---

## What Changed from v6

- Added `speech_act` field to both detection prompts (model detection ongoing-v9, seed detector seed-v8)
- Added speech act classification guidance section with 9 taxonomy values:
  - `request` — asking someone else to do something
  - `self_commitment` — speaker commits to doing something themselves
  - `acceptance` — speaker accepts ownership of a prior request
  - `status_update` — progress report with no new obligation
  - `completion` — signals delivery or done
  - `cancellation` — withdrawing a prior commitment
  - `decline` — refusing a request
  - `reassignment` — transferring ownership
  - `informational` — no commitment content at all
- `speech_act` field added to JSON output schema for both prompts
- Surfacing router updated: `status_update`, `informational`, `completion`, `cancellation`, `decline` speech acts are never surfaced (handled by other subsystems)
- Existing `CommitmentType` (send, review, deliver...) unchanged — it describes the deliverable, not the speaker act. Both fields coexist.

---

## Why

The system previously classified *what* the deliverable is (CommitmentType) but not *what the speaker is doing*. This caused a request ("can you send me the report?") and a self-commitment ("I'll send you the report") to produce identical commitment objects. Speech act classification fixes this, enabling:
- Requests without acceptance to be surfaced as "watching" instead of "mine"
- Status updates and informational content to be filtered from surfacing
- Completion signals to be routed to the completion detection service
- Cancellations to trigger lifecycle transitions

---

## Schema

### Model detection (ongoing-v9)

```json
{
  "is_commitment": true,
  "speech_act": "self_commitment",
  "confidence": 0.9,
  "explanation": "Speaker commits to sending report",
  "suggested_owner": "Alice",
  "suggested_deadline": "Friday",
  "deliverable": "report",
  "counterparty": "Bob",
  "user_relationship": "mine",
  "structure_complete": true
}
```

### Seed detector (seed-v8)

```json
{
  "commitments": [
    {
      "trigger_phrase": "I'll send the report by Friday",
      "who_committed": "Alice",
      "directed_at": "Bob",
      "urgency": "medium",
      "commitment_type": "send",
      "speech_act": "self_commitment",
      "title": "Send the report",
      "is_external": false,
      "confidence": 0.9
    }
  ]
}
```
