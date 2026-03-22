# Data Model

Core tables and their relationships in Rippled's PostgreSQL database.

---

## Entity Relationships

```mermaid
erDiagram
    sources ||--o{ source_items : contains
    source_items ||--o{ commitment_signals : generates
    commitment_signals }o--|| commitments : links_to
    commitments ||--o{ lifecycle_transitions : tracks
    commitments }o--o| user_identity_profiles : resolved_via
    source_items ||--o{ detection_audit : logged_in
    users ||--o{ sources : owns
    users ||--o{ commitments : owns
    users ||--o{ user_identity_profiles : has

    sources {
        uuid id
        string source_type
        string provider_account_id
        jsonb credentials
        bool is_active
    }

    source_items {
        uuid id
        string source_type
        string content
        string content_normalized
        string sender_name
        string sender_email
        timestamp occurred_at
        timestamp seed_processed_at
    }

    commitments {
        uuid id
        string title
        string commitment_text
        string commitment_type
        string speech_act
        string resolved_owner
        string suggested_owner
        string counterparty_name
        string user_relationship
        string lifecycle_state
        bool structure_complete
        bool is_surfaced
        float confidence_for_surfacing
        timestamp resolved_deadline
    }

    user_identity_profiles {
        uuid id
        string identity_type
        string identity_value
        bool confirmed
    }
```

---

## Key Tables

### `source_items`
Raw ingested content from all sources. One row per email, Slack message, or meeting transcript. The source of truth — never modified after creation.

### `commitments`
Extracted commitment objects. Created by the detection pipeline. Updated by lifecycle events and user actions.

### `commitment_signals`
The join table between `source_items` and `commitments`. Tracks which source items contributed evidence to which commitment, and what role each signal played (origin, clarification, delivery, closure).

### `detection_audit`
Every LLM detection call logged with: raw prompt, raw response, parsed result, tokens, cost, duration, prompt version. Essential for debugging and eval.

### `user_identity_profiles`
Maps a user's known names and email addresses to their `user_id`. Powers owner resolution — when the LLM extracts "Kevin" as the owner, this table resolves it to a user UUID.

### `lifecycle_transitions`
Immutable log of every state change on a commitment, with timestamp and trigger reason.

---

## Lifecycle State Enum

```
proposed → needs_clarification | active | discarded
active / confirmed → in_progress | delivered | dormant | discarded
in_progress → delivered | canceled | dormant
delivered → completed | closed | active (reopened)
completed → closed
canceled → closed
dormant → active | discarded
closed → active (reopened)
```

See [Commitment Lifecycle](lifecycle.md) for the full state machine.
