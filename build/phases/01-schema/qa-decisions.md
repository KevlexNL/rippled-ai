# Phase 01 — Kevin Q&A Decisions

**Date:** 2026-03-09
**Status:** Approved — incorporate into implementation

---

## Q1 — Candidate ↔ Commitment Cardinality

**Decision: N:M (both directions)**

A single candidate can spawn multiple commitments (one email with two topics → two commitments).
Multiple candidates can merge into one commitment.

**Schema impact:** Replace `commitment_candidates.commitment_id` nullable FK with a dedicated join table `candidate_commitments`:

```
candidate_commitments
  id              UUID PK
  candidate_id    UUID NOT NULL → commitment_candidates.id ON DELETE CASCADE
  commitment_id   UUID NOT NULL → commitments.id ON DELETE CASCADE
  created_at      TIMESTAMPTZ NOT NULL default now()
  UNIQUE (candidate_id, commitment_id)
```

The `commitment_id` FK on `commitment_candidates` itself is REMOVED. The `was_promoted` boolean on candidates remains — set true when any `candidate_commitments` row is created for this candidate.

---

## Q2 — Vague Time Phrase Storage

**Decision: Single column on commitment is sufficient**

Vague phrases (e.g. "soon", "later") are derived from raw content and the ingestion timeline. The JSONB `deadline_candidates` array preserves all raw per-detection phrases. The commitment-level `vague_time_phrase` column holds the most operative vague phrase for UI display.

**No schema change.** Implementation note: surfacing logic should prefer the raw phrase from `deadline_candidates` array when rendering clarification prompts — do not over-interpret or normalize vague phrases.

---

## Q3 — `context_type` Classification

**Decision: Strict binary — `internal` or `external` only**

A "big promise" represents the overall delivery — it can be classified as external even if intermediate steps (signals) involve internal communication. `mixed` is not needed.

**Schema change:** Update CHECK constraint on `commitments.context_type` to `IN ('internal', 'external')` only. Remove `'mixed'`.

---

## Q4 — `commitment_type`: TEXT vs ENUM

**Decision: ENUM with base set + `other` fallback**

Base values (from Brief §2.3):
`send`, `review`, `follow_up`, `deliver`, `investigate`, `introduce`, `coordinate`, `update`, `delegate`, `schedule`, `confirm`, `other`

Rules:
- Detection model outputs one of the above; unknown/edge-case types use `other`
- New types added via migration only after review of real usage data
- A review cron is scheduled for ~2026-03-30 to query all commitments where `commitment_type = 'other'` and surface patterns to Kevin

**Code comment required (in `app/models/enums.py` alongside the enum):**
```python
# REVIEW SCHEDULED: ~2026-03-30
# Query commitments where commitment_type = 'other' and review what real usage
# patterns have emerged. Promote frequent patterns to dedicated enum values via migration.
# See: build/phases/01-schema/qa-decisions.md Q4
```

---

## Q5 — Field-Level Version History

**Decision: Lifecycle transition log is sufficient for MVP**

Full field-level snapshots (what changed in each field on each update) are not required now. If needed later, can be inferred or backfilled from current state + transition log.

---

## Q6 — `discarded` State

**Decision: Confirmed — terminal soft-delete**

Discarded commitments remain in DB as `lifecycle_state = 'discarded'`. Not surfaced to user. Not physically deleted. Transition to any other state from `discarded` is blocked (terminal). Re-detection creates a new candidate.

---

## Q7 — Observation Window Calculation

**Decision: Wall-clock for MVP**

`observe_until` stores a plain `TIMESTAMPTZ`. Working-hours calculation (weekends, timezone, holidays) is deferred. MVP approximation: treat stated working-hour windows as equivalent calendar hours during a working day.

---

## Code Review Fixes — Approved (2026-03-09)

All fixes below are approved. Apply in one pass.

### Blocker 1 — `originating_item_id` nullability

**Decision: Option A — keep SET NULL + nullable**

`originating_item_id` is nullable at DB level (SET NULL on source_item delete). However, application layer MUST enforce that this field is provided on insert — it should never be null on creation, only null as a result of a source_item being deleted later. Add an application-level guard in the create endpoint/service.

Rationale: Matches "never erase history" principle. Candidate records preserved with null origin if source_item is deleted.

### Blocker 2 — DATABASE_URL guard in env.py

Fix: Add guard so missing DATABASE_URL raises a clear error rather than failing silently.

### Warning — CheckConstraint naming

Fix: Ensure all check constraints follow `ck_<table>_<constraint_name>` naming convention before Phase 02 to prevent spurious rename migrations from Alembic autogenerate.

### Warning — Pydantic schema gaps

Fix all:
- Add `CommitmentCandidateRead` and `CommitmentCandidateCreate` schemas
- Fix `metadata_` naming leak (internals should not surface in response schemas)
- Remove unused imports
- Add missing fields identified in review

### Warning — `resolved_by_signal_id` naming confusion

Fix: Rename column `commitment_ambiguities.resolved_by_signal_id` → `resolved_by_item_id` (it points to `source_items.id`, not `commitment_signals.id`).
