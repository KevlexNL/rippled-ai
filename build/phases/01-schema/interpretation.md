# Phase 01 — Schema Interpretation

**Phase:** 01-schema
**Date:** 2026-03-09
**Status:** Ready for review — awaiting approval before any implementation

---

## 1. All Entities / Tables (Exhaustive)

---

### 1.1 `users`

Represents the person the system is observing commitments on behalf of. One-user-per-installation scope for MVP.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `email` | `TEXT` | NOT NULL, UNIQUE | |
| `display_name` | `TEXT` | NULLABLE | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### 1.2 `sources`

Represents a connected communication integration (e.g. a specific Slack workspace, a Gmail account, a meeting provider account). One user may connect multiple sources of the same type.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` ON DELETE CASCADE | |
| `source_type` | `source_type` (enum) | NOT NULL | See enum section |
| `provider_account_id` | `TEXT` | NULLABLE | External account ID from provider |
| `display_name` | `TEXT` | NULLABLE | Human-readable label for this connection |
| `is_active` | `BOOLEAN` | NOT NULL, default `true` | |
| `credentials` | `JSONB` | NULLABLE | Encrypted token/refresh data (never logged) |
| `metadata` | `JSONB` | NULLABLE | Provider-specific config (e.g. workspace URL, channel filters) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### 1.3 `source_items`

The smallest directly ingested communication unit: one Slack message, one email message, one meeting transcript segment. Raw input preserved immutably.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `source_id` | `UUID` | NOT NULL, FK → `sources.id` ON DELETE CASCADE | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` ON DELETE CASCADE | Denormalized for query performance |
| `source_type` | `source_type` (enum) | NOT NULL | Copied from parent source for direct queries |
| `external_id` | `TEXT` | NOT NULL | Provider-native message/segment ID |
| `thread_id` | `TEXT` | NULLABLE | Groups items into threads/meetings/email chains |
| `direction` | `TEXT` | NULLABLE | `'inbound'` or `'outbound'` — primarily for email |
| `sender_id` | `TEXT` | NULLABLE | Provider-native sender identifier |
| `sender_name` | `TEXT` | NULLABLE | |
| `sender_email` | `TEXT` | NULLABLE | |
| `is_external_participant` | `BOOLEAN` | NULLABLE | Whether sender is outside user's org |
| `content` | `TEXT` | NULLABLE | Raw text of the item |
| `content_normalized` | `TEXT` | NULLABLE | Cleaned version (quoted email stripped, etc.) |
| `has_attachment` | `BOOLEAN` | NOT NULL, default `false` | |
| `attachment_metadata` | `JSONB` | NULLABLE | File names, types, sizes — not file content |
| `recipients` | `JSONB` | NULLABLE | Array of recipient objects `{id, name, email, is_external}` |
| `source_url` | `TEXT` | NULLABLE | Permalink to original message in provider |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | When the message/segment happened in source |
| `ingested_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | When Rippled received it |
| `metadata` | `JSONB` | NULLABLE | Source-specific fields (e.g. Slack channel ID, meeting title) |
| `is_quoted_content` | `BOOLEAN` | NOT NULL, default `false` | Marks email quoted-text segments for exclusion from extraction |

Unique constraint: `(source_id, external_id)` — prevents re-ingestion of the same item.

---

### 1.4 `commitment_candidates`

Intermediate interpretation object. A provisional detection that a trackable commitment may exist. Not all candidates become commitments.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` ON DELETE CASCADE | |
| `originating_item_id` | `UUID` | NOT NULL, FK → `source_items.id` | The item that first triggered candidate creation |
| `commitment_id` | `UUID` | NULLABLE, FK → `commitments.id` | Set when candidate is promoted to/merged with a commitment |
| `raw_text` | `TEXT` | NULLABLE | The span of text that triggered detection |
| `detection_explanation` | `TEXT` | NULLABLE | Why the system flagged this as a possible commitment |
| `confidence_score` | `NUMERIC(4,3)` | NULLABLE, CHECK >= 0 AND <= 1 | Overall detection confidence |
| `was_promoted` | `BOOLEAN` | NOT NULL, default `false` | |
| `was_discarded` | `BOOLEAN` | NOT NULL, default `false` | |
| `discard_reason` | `TEXT` | NULLABLE | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### 1.5 `commitments`

The primary domain object. A unified, evolving representation of a likely future-oriented work obligation. May accumulate signals from many source items over time.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` ON DELETE CASCADE | |
| **— Identity & Linkage —** | | | |
| `version` | `INTEGER` | NOT NULL, default `1` | Incremented on significant field updates |
| **— Meaning —** | | | |
| `title` | `TEXT` | NOT NULL | Short human-readable label |
| `description` | `TEXT` | NULLABLE | Longer narrative of the commitment |
| `commitment_text` | `TEXT` | NULLABLE | Normalized summary of the original promise |
| `commitment_type` | `TEXT` | NULLABLE | e.g. `'send'`, `'review'`, `'follow_up'`, `'deliver'`, `'investigate'`, `'introduce'`, `'coordinate'`, `'update'`, `'delegate'` — open text for extensibility |
| `priority_class` | `commitment_class` (enum) | NULLABLE | `'big_promise'` or `'small_commitment'` — See enum |
| `context_type` | `TEXT` | NULLABLE | `'external'` or `'internal'` |
| **— Ownership —** | | | |
| `owner_candidates` | `JSONB` | NULLABLE | Array of `{name, source_item_id, confidence}` |
| `resolved_owner` | `TEXT` | NULLABLE | Best current explicit owner — null when unresolved |
| `suggested_owner` | `TEXT` | NULLABLE | AI-proposed owner, distinct from resolved |
| `ownership_ambiguity` | `ownership_ambiguity_type` (enum) | NULLABLE | See enum |
| **— Timing —** | | | |
| `deadline_candidates` | `JSONB` | NULLABLE | Array of `{text, normalized_date, source_item_id, confidence}` |
| `resolved_deadline` | `TIMESTAMPTZ` | NULLABLE | Best current strongly-supported deadline |
| `vague_time_phrase` | `TEXT` | NULLABLE | Raw vague phrase when no normalization is safe (e.g. "soon", "later") |
| `suggested_due_date` | `TIMESTAMPTZ` | NULLABLE | AI-proposed date, distinct from resolved |
| `timing_ambiguity` | `timing_ambiguity_type` (enum) | NULLABLE | See enum |
| **— Deliverable / Next Step —** | | | |
| `deliverable` | `TEXT` | NULLABLE | What the commitment intends to produce or do |
| `target_entity` | `TEXT` | NULLABLE | Who or what the deliverable is directed at |
| `suggested_next_step` | `TEXT` | NULLABLE | AI-proposed likely next step |
| `deliverable_ambiguity` | `deliverable_ambiguity_type` (enum) | NULLABLE | See enum |
| **— Status / Lifecycle —** | | | |
| `lifecycle_state` | `lifecycle_state` (enum) | NOT NULL, default `'proposed'` | See enum |
| `state_changed_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | When lifecycle_state last changed |
| **— Confidence —** | | | |
| `confidence_commitment` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | Is this really a commitment? |
| `confidence_owner` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | How sure about ownership? |
| `confidence_deadline` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | How sure about timing? |
| `confidence_delivery` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | How sure about delivery? |
| `confidence_closure` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | How sure the loop is closed? |
| `confidence_actionability` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | Overall: is this worth surfacing? |
| **— Evidence Explanation —** | | | |
| `commitment_explanation` | `TEXT` | NULLABLE | Why Rippled believes this is a commitment |
| `missing_pieces_explanation` | `TEXT` | NULLABLE | What remains unclear |
| `delivery_explanation` | `TEXT` | NULLABLE | Why delivery may be inferred |
| `closure_explanation` | `TEXT` | NULLABLE | Why closure may be inferred |
| **— Observation Window —** | | | |
| `observe_until` | `TIMESTAMPTZ` | NULLABLE | Do not surface before this time |
| `observation_window_hours` | `NUMERIC` | NULLABLE | Working-hours window applied |
| **— Surfacing —** | | | |
| `is_surfaced` | `BOOLEAN` | NOT NULL, default `false` | Whether currently shown to user |
| `surfaced_at` | `TIMESTAMPTZ` | NULLABLE | When first surfaced |
| **— Timestamps —** | | | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### 1.6 `commitment_signals`

Join table linking source items to commitments with a typed role. A signal is the reified relationship between one source item and one commitment.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `commitment_id` | `UUID` | NOT NULL, FK → `commitments.id` ON DELETE CASCADE | |
| `source_item_id` | `UUID` | NOT NULL, FK → `source_items.id` ON DELETE CASCADE | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | Denormalized for filtering |
| `signal_role` | `signal_role` (enum) | NOT NULL | See enum |
| `confidence` | `NUMERIC(4,3)` | NULLABLE, CHECK 0–1 | How strongly this signal supports its role |
| `interpretation_note` | `TEXT` | NULLABLE | What this signal contributed to the commitment |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

Unique constraint: `(commitment_id, source_item_id, signal_role)` — one item can play one role per commitment.

---

### 1.7 `commitment_ambiguities`

Explicit storage of ambiguity records attached to a commitment. Separate table so multiple independent ambiguities can exist simultaneously.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `commitment_id` | `UUID` | NOT NULL, FK → `commitments.id` ON DELETE CASCADE | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | |
| `ambiguity_type` | `ambiguity_type` (enum) | NOT NULL | See enum — what dimension is ambiguous |
| `description` | `TEXT` | NULLABLE | Human-readable note on this ambiguity |
| `is_resolved` | `BOOLEAN` | NOT NULL, default `false` | |
| `resolved_by_signal_id` | `UUID` | NULLABLE, FK → `source_items.id` | Which signal resolved it, if any |
| `resolved_at` | `TIMESTAMPTZ` | NULLABLE | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### 1.8 `lifecycle_transitions`

Append-only audit log of every state change for a commitment. Preserves full transition history including what evidence drove the change.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, NOT NULL, default `gen_random_uuid()` | |
| `commitment_id` | `UUID` | NOT NULL, FK → `commitments.id` ON DELETE CASCADE | |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | |
| `from_state` | `lifecycle_state` (enum) | NULLABLE | NULL for initial creation |
| `to_state` | `lifecycle_state` (enum) | NOT NULL | |
| `trigger_source_item_id` | `UUID` | NULLABLE, FK → `source_items.id` | Signal that drove the transition |
| `trigger_reason` | `TEXT` | NULLABLE | Explanation of why this transition occurred |
| `confidence_at_transition` | `NUMERIC(4,3)` | NULLABLE | Snapshot of actionability confidence |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

## 2. PostgreSQL Enum Types

### `source_type`
```
meeting
slack
email
```
Open for future extension (calendar, task_system, crm).

---

### `lifecycle_state`
```
proposed
needs_clarification
active
delivered
closed
discarded
```

---

### `signal_role`
```
origin
clarification
progress
delivery
closure
conflict
reopening
```

---

### `ambiguity_type`
Covers all dimensions from Brief 3 §1.5 and §8–9:
```
owner_missing
owner_vague_collective
owner_multiple_candidates
owner_conflicting
timing_missing
timing_vague
timing_conflicting
timing_changed
timing_inferred_weak
deliverable_unclear
target_unclear
status_unclear
commitment_unclear
```

---

### `ownership_ambiguity_type`
Subset focused on the ownership dimension (used directly on `commitments.ownership_ambiguity`):
```
missing
vague_collective
multiple_candidates
conflicting
```

---

### `timing_ambiguity_type`
Subset focused on timing (used on `commitments.timing_ambiguity`):
```
missing
vague
conflicting
changed
inferred_weak
```

---

### `deliverable_ambiguity_type`
Subset focused on deliverable (used on `commitments.deliverable_ambiguity`):
```
unclear
target_unknown
```

---

### `commitment_class`
```
big_promise
small_commitment
```

---

## 3. Relationships and Foreign Keys

```
users
  └── sources                  (user_id → users.id)
        └── source_items        (source_id → sources.id)

users
  └── source_items              (user_id → users.id) [denormalized]

source_items
  └── commitment_candidates     (originating_item_id → source_items.id)

commitments
  ├── commitment_candidates     (commitment_id → commitments.id) [nullable, set on promotion]
  ├── commitment_signals        (commitment_id → commitments.id)
  │     └── source_items        (source_item_id → source_items.id)
  ├── commitment_ambiguities    (commitment_id → commitments.id)
  └── lifecycle_transitions     (commitment_id → commitments.id)

users
  ├── commitments               (user_id → users.id)
  ├── commitment_candidates     (user_id → users.id)
  ├── commitment_signals        (user_id → users.id) [denormalized]
  ├── commitment_ambiguities    (user_id → users.id)
  └── lifecycle_transitions     (user_id → users.id)
```

All foreign keys use `ON DELETE CASCADE` where child records are meaningless without the parent. Exception: `commitment_candidates.commitment_id` is nullable and uses `ON DELETE SET NULL` so discarded candidates do not cascade-delete when a commitment is deleted.

---

## 4. Lifecycle State Machine — Allowed Transitions

From Brief 5:

| From State | To State | Typical Trigger |
|---|---|---|
| _(initial)_ | `proposed` | New candidate promoted, low confidence |
| `proposed` | `active` | Confidence rises, fields sufficiently resolved |
| `proposed` | `needs_clarification` | Meaningful signal exists but key fields remain weak/conflicting |
| `proposed` | `discarded` | False positive, no strengthening signals, weak candidate expires |
| `needs_clarification` | `active` | Ambiguity resolved via new signal or user input |
| `needs_clarification` | `discarded` | Invalidated, merged, or confirmed false positive |
| `active` | `delivered` | Delivery evidence detected (outbound email, "just sent it", etc.) |
| `active` | `closed` | Explicit acknowledgement, loop evidently complete without distinct delivery step |
| `active` | `needs_clarification` | Conflicting or ambiguating signal reduces certainty |
| `delivered` | `closed` | No follow-up after observation window; explicit acceptance; downstream evidence of loop completion |
| `delivered` | `active` | Revision requested, rejection signal, delivery deemed incomplete |
| `closed` | `active` | New linked signal implies obligation is still live |
| `closed` | `delivered` | Evidence-reconstruction only (rare; e.g. processing lag resolves a past delivery event) |
| _any non-discarded_ | `discarded` | Clearly invalidated, confirmed false positive, or merged into stronger commitment by policy |

**Not allowed:**
- `discarded` → any state (discarded is terminal; re-detection would create a new candidate)
- `proposed` → `delivered` (must pass through `active`)
- `proposed` → `closed` (must pass through `active`)
- `needs_clarification` → `delivered` (must pass through `active`)
- `needs_clarification` → `closed` (must pass through `active`)

---

## 5. Design Decisions

### 5.1 UUID Primary Keys
Using `gen_random_uuid()` (UUID v4) for all PKs because:
- Supabase/PostgreSQL supports it natively
- Allows external systems to generate IDs before insertion (useful for idempotent ingestion)
- Avoids sequential ID leakage in API responses
- Distributed-safe if the architecture scales horizontally

### 5.2 JSONB vs Relational for Flexible Fields

**JSONB is used for:**
- `owner_candidates` — array of candidate objects with varying shape; querying into individual candidates is uncommon at MVP; full replacement is the typical update
- `deadline_candidates` — same reasoning; plural candidates with heterogeneous structure
- `attachment_metadata`, `recipients` on `source_items` — high variability by source type; no relational queries needed against individual fields
- `credentials`, `metadata` on `sources` — provider-specific, encrypted, not queried
- `metadata` on `source_items` — source-specific fields (Slack channel, meeting title) that do not need relational constraints

**Relational columns are used for:**
- `resolved_owner`, `resolved_deadline`, `suggested_owner`, `suggested_due_date` — these are the operationally important "current best" values that queries, surfacing logic, and indexes will target
- All enum fields — enforced at the DB level
- All confidence scores — numeric, indexed
- `lifecycle_state` — queried constantly; must be relational

**Rule:** any field that needs to be `WHERE`-filtered, `ORDER BY`-sorted, or indexed gets a dedicated column. Candidates and history go in JSONB.

### 5.3 How Ambiguity Is Stored

Ambiguity is stored three ways, deliberately layered:

1. **Enum columns on `commitments`** (`ownership_ambiguity`, `timing_ambiguity`, `deliverable_ambiguity`) — fast, indexable, single-dimension state. Used by surfacing and prioritization logic.

2. **`commitment_ambiguities` table** — multiple concurrent ambiguities per commitment, each with resolution tracking, the driving signal, and a description. Supports the clarification workflow (Phase 04). One commitment can have `owner_missing` AND `timing_vague` simultaneously as separate rows.

3. **Candidate JSONB arrays** (`owner_candidates`, `deadline_candidates`) — the raw list of competing interpretations before resolution, preserved for auditability.

This separation avoids collapsing ambiguity too early. The enum columns are fast query handles; the ambiguities table is the rich clarification substrate.

### 5.4 Suggested Values vs Resolved Values

The brief is explicit: suggested and resolved must remain distinct.

| Dimension | Resolved column | Suggested column |
|-----------|----------------|------------------|
| Owner | `resolved_owner` | `suggested_owner` |
| Deadline | `resolved_deadline` | `suggested_due_date` |
| Next step | _(no resolved column — deliverable IS the resolved form)_ | `suggested_next_step` |

**Resolved** = supported strongly enough to be the operative current value. May still be null if truly unknown.
**Suggested** = AI-proposed inference useful for UX and clarification, but not asserted as fact. Must never be shown as certain.

This avoids the anti-pattern of letting AI inference pollute the "ground truth" columns. A surfacing rule can say "show suggested_owner if resolved_owner is null" without ever writing a guess into `resolved_owner`.

### 5.5 How Evidence and Signals Link to Commitments

The `commitment_signals` table is the join between `commitments` and `source_items`. Each row is a typed, confidence-scored relationship.

A single `source_item` can be an `origin` for one commitment and a `clarification` for another — the role is per-relationship, not per-item.

The append-only `lifecycle_transitions` table preserves which `source_item` triggered each state change, so the full evidence trail for "why did this go from active → delivered?" is auditable.

`commitment_candidates` links back to `commitments` via `commitment_id` once promoted. This preserves the intermediate detection object even after the commitment is fully formed.

Evidence explanations (`commitment_explanation`, `delivery_explanation`, `closure_explanation`) are prose fields on `commitments` for the most recent interpretive state. Signal-level notes are on `commitment_signals.interpretation_note`.

---

## 6. Questions and Concerns About the Briefs

### Q1: `commitment_candidates` → `commitments` cardinality
The briefs describe candidates being "merged into a stronger commitment record." Does this mean one candidate promotes to exactly one commitment (1:1), or can multiple candidates merge into one commitment (N:1)? The current schema supports N candidates → 1 commitment via `commitment_candidates.commitment_id`. Is there also a need for 1 candidate → N commitments (a single detection spawning two distinct commitments)?

**Impact:** If N candidates → N commitments is a real case, a join table (`candidate_commitments`) replaces the nullable FK. Deferring to Phase 03 (Detection) unless clarification is needed now.

---

### Q2: `vague_time_phrase` — store on commitment or on each candidate?
The brief says vague phrases like "soon" should not be normalized to precise timestamps. Currently modeled as a single `TEXT` column on `commitments` for the latest/most operative vague phrase. But deadline candidates in JSONB preserve all raw phrases per-detection. Is the commitment-level `vague_time_phrase` sufficient, or should there be a dedicated vague-timing record separate from the JSONB array?

**Impact:** Low for MVP — the JSONB array covers it. Raising because the clarification UI (Phase 04) may want to display the exact original phrase.

---

### Q3: `context_type` — `internal`/`external` is binary, but briefs hint at spectrum
The source model distinguishes internal vs external participants but also mentions "internal delivery vs external delivery" as a transitional state. Is `internal`/`external` a binary classification on the commitment, or should it capture something like `'internal_with_external_target'`?

**Impact:** Affects big-promise classification heuristics. Could be left as a text column with three values (`internal`, `external`, `mixed`) rather than a boolean or a 2-value enum. Proposing `TEXT` with a CHECK constraint for now to preserve flexibility.

---

### Q4: `commitment_type` — open text vs enum
Brief §2.3 lists ~11 commitment types but says "the model should support later extension and should not overfit to a fixed closed list too early." This argues for `TEXT` over an enum for `commitment_type`. Confirming this is intentional — an enum would need a migration for each new type, which is friction at this stage.

---

### Q5: Processing/version history
Brief §5.1 mentions "processing/version history" as a field. The `version` integer on `commitments` plus the `lifecycle_transitions` audit log covers state-change history. But if the intent is to preserve full field-level history (e.g. every time `title` changed), that would require a separate `commitment_versions` snapshot table. Is field-level versioning needed for MVP, or is lifecycle transition + signal audit sufficient?

**Impact:** Significant schema addition if required. Proposing to defer snapshot versioning unless it is needed for Phase 04 or 06.

---

### Q6: `discarded` state — terminal or soft-delete?
Brief §5 says discarded commitments should "remain auditable internally" and "generally not surface to the user." The current model treats `discarded` as a terminal lifecycle state (row remains, `lifecycle_state = 'discarded'`), not a physical delete. Confirming this is the right approach — it matches the "never erase history" principle.

---

### Q7: Observation window — working hours vs wall clock
Brief §4 specifies observation windows in "working hours" (e.g. 2 working hours for Slack). The current schema stores `observe_until` as a plain `TIMESTAMPTZ`. Calculating working-hours-based deadlines correctly (accounting for weekends, user timezone, holidays) is non-trivial. For MVP, is a simplified wall-clock approximation acceptable (e.g. 2 working hours ≈ 2 calendar hours during a working day), or should working-hours logic be implemented from the start?

**Impact:** Affects background job logic (Phase not yet defined), not schema. Schema `observe_until` is sufficient regardless of how it is calculated. Raising as an implementation note.

---

*Awaiting approval before creating any migrations, models, or other files.*
