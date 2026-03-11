# Phase 01 — Schema Implementation Decisions

**Phase:** 01-schema  
**Date:** 2026-03-09  
**Status:** Complete — ready for Kevin review & approval before Phase 02

---

## 1. Technical Choices & Rationale

### 1.1 UUID Primary Keys
Chose `gen_random_uuid()` (UUID v4, native PostgreSQL):
- Distributed ID generation without central DB coordination
- Allows external systems (import, API clients) to generate IDs idempotently before insertion
- Prevents sequential ID leakage in API responses
- Supabase/PostgreSQL fully support it

### 1.2 Naming Conventions
Applied Alembic standard naming convention for constraint names:
- `pk_<table>` for primary keys
- `fk_<table>_<column>_<foreign_table>` for foreign keys
- `uq_<table>_<column>` for unique constraints
- `ck_<table>_<constraint_name>` for check constraints
- `ix_<column_label>` for indexes

Benefit: Alembic generates stable, reproducible migration names across sessions.

### 1.3 JSONB vs Relational Storage
**JSONB used for:**
- `owner_candidates`, `deadline_candidates` — plural candidates with varying structure; querying individual candidates is rare; full replacement is typical update pattern
- `attachment_metadata`, `recipients` — high variability by source type; no relational queries expected
- `credentials`, `metadata` on sources — provider-specific; encrypted; not queried relationally

**Relational columns used for:**
- All enum fields — enforced at DB level
- `resolved_owner`, `resolved_deadline`, `suggested_owner`, `suggested_due_date` — "current best" values; heavily queried, sorted, indexed
- All confidence scores — numeric, indexed
- `lifecycle_state` — queried constantly

Rule applied: any field needing `WHERE`, `ORDER BY`, or indexing → dedicated column.

### 1.4 Suggested vs Resolved Separation
Kept distinct columns as per the brief:
- `resolved_owner` = fact supported strongly enough to be operative current value (may be null if unknown)
- `suggested_owner` = AI-proposed inference for UX; never written to resolved_owner automatically

Prevents conflation of ground truth and inference, preserves audit trail.

### 1.5 Ambiguity Storage — Three-Layer Approach

1. **Enum columns on `commitments`** (`ownership_ambiguity`, `timing_ambiguity`, `deliverable_ambiguity`)
   - Fast, indexable, single dimension
   - Used by surfacing logic, prioritization
   
2. **`commitment_ambiguities` table** (Phase 04 leverage point)
   - Supports multiple concurrent ambiguities per commitment
   - Each with resolution tracking, driving signal, description
   - Rich substrate for clarification workflow
   
3. **Candidate arrays in JSONB** (`owner_candidates`, `deadline_candidates`)
   - Raw competing interpretations preserved for auditability
   - Full history before resolution

This layering avoids premature collapse of ambiguity.

### 1.6 Confidence Scores
All confidence fields use `NUMERIC(4, 3)` with check constraints `BETWEEN 0 AND 1`:
- 4 total digits, 3 decimal places → range 0.000 to 1.000
- Supports 3-decimal precision (e.g., 0.751 for "pretty confident")
- Check constraint enforced at DB level, not just application
- NULL allowed when confidence is unknown/unmeasured

### 1.7 Lifecycle State Machine
Enforced via type safety (PostgreSQL ENUM) and documented in docstrings, not DB constraints:
- Invalid transitions blocked at application layer (Phase 02 API rules)
- DB constraint would require complex triggers; state rules live in code
- Audit trail (`lifecycle_transitions` table) provides full visibility of sequence

### 1.8 Cascade Delete Strategy

**CASCADE on most FKs** (`sources.user_id`, `source_items.source_id`, `commitments.user_id`, `commitment_signals.commitment_id`, etc.):
- Child records meaningless without parent
- Enforces referential integrity cleanly
- No orphaned data

**SET NULL on `commitment_candidates.commitment_id`**:
- Candidate may exist before promotion or after commitment deletion
- Discarded candidates should not cascade-delete commitments
- Preserves detection history

### 1.9 Observation Window
Modeled as simple `TIMESTAMPTZ` column (`observe_until`):
- Wall-clock deadline when commitment should be surfaced
- Working-hours calculation happens at application layer (Phase not yet defined)
- Future: could add `observation_window_hours` (calculated offset) and background job to materialize `observe_until`
- For MVP, simple approach sufficient

### 1.10 Context Type
Used `TEXT` with `CHECK ('internal', 'external', 'mixed')` instead of ENUM:
- More flexible if new types emerge later (no migration friction)
- Easily queryable with `=` and `IN`
- Still enforced at DB level via check constraint

### 1.11 Commitment Type
Used `TEXT` (no enum) per interpretation answer Q4:
- Brief explicitly avoids closing the model too early
- 11+ types listed but architecture should support later extension
- TEXT column allows ad-hoc types without migration
- Indexable if needed later

### 1.12 Foreign Key Index Strategy
**Explicit indexes on all FK columns** (`source_id`, `user_id`, `commitment_id`, etc.):
- Needed for efficient lookup of all items for a user/source/commitment
- Supabase's RLS layer will query heavily on user_id
- Foreign keys don't automatically index in PostgreSQL; must be explicit

### 1.13 Alembic Configuration
- env.py loads `.env` via python-dotenv
- DATABASE_URL parsed, converted `postgres://` → `postgresql://` for SQLAlchemy compatibility
- alembic.ini uses `%(DATABASE_URL)s` interpolation
- target_metadata points to `Base.metadata` for autogenerate support (future migrations)

---

## 2. Schema Completeness Check

### Tables Created
- [x] `users` — 5 columns
- [x] `sources` — 9 columns
- [x] `source_items` — 21 columns
- [x] `commitments` — 42 columns
- [x] `commitment_candidates` — 11 columns
- [x] `commitment_signals` — 8 columns
- [x] `commitment_ambiguities` — 9 columns
- [x] `lifecycle_transitions` — 9 columns

**Total: 8 tables, 112 columns**

### Enum Types Created
- [x] `source_type` (3 values)
- [x] `lifecycle_state` (6 values)
- [x] `signal_role` (7 values)
- [x] `ambiguity_type` (13 values)
- [x] `ownership_ambiguity_type` (4 values)
- [x] `timing_ambiguity_type` (5 values)
- [x] `deliverable_ambiguity_type` (2 values)
- [x] `commitment_class` (2 values)

**Total: 8 enums, 42 values**

### Constraints
- [x] Primary keys on all tables
- [x] Foreign keys with CASCADE/SET NULL as per design
- [x] Unique constraints (`users.email`, `source_items.(source_id, external_id)`, `commitment_signals.(commitment_id, source_item_id, signal_role)`)
- [x] Check constraints on all confidence score fields (0–1 range)
- [x] Check constraints on `context_type` enum values
- [x] Check constraints on `lifecycle_transitions.confidence_at_transition`

### Indexes
- [x] Primary key indexes (automatic)
- [x] Foreign key indexes (explicit, on user_id, source_id, commitment_id, etc.)
- [x] Query optimization indexes (lifecycle_state, is_surfaced, confidence_actionability, thread_id, occurred_at, is_resolved, etc.)

---

## 3. Known Gaps & Design Deferred to Later Phases

| Item | Decision | Reason |
|------|----------|--------|
| RLS (Row-Level Security) | Deferred | Phase 02+ when API routes define access patterns |
| Soft-delete / time-travel queries | Not implemented | Lifecycle_state captures "discarded"; audit log captures history |
| Field-level version history snapshots | Not implemented | lifecycle_transitions + signal audit log sufficient for MVP |
| Working-hours calculation for observation_window | Deferred | Application layer (future phase); wall-clock MVP acceptable |
| Full-text search indexes | Not added | Phase 03+ when detection/search requirements finalized |
| Computed columns | Not used | Denormalization via JSONB; normalization can be added if bottleneck surfaces |
| Partitioning | Not applied | Single-user MVP; partition later if retention/scale demands it |

---

## 4. Migration & Deployment Notes

### Running the Migration
```bash
cd ~/projects/rippled-ai
.venv/bin/alembic upgrade head
```

Assumes:
- `.env` file has `DATABASE_URL` (Supabase connection string)
- psycopg2-binary or equivalent PostgreSQL driver installed
- Network access to Supabase from deployment environment

### Rollback
```bash
.venv/bin/alembic downgrade -1
```

Drops all tables and enum types. Safe for MVP (no production data yet).

### Validation After Migration
```python
from app.models import User, Source, SourceItem, Commitment, CommitmentCandidate, CommitmentSignal, CommitmentAmbiguity, LifecycleTransition
# All imports should succeed, tables should exist in Supabase
```

---

## 5. What's Next (Phase 02)

- Define FastAPI routes for CRUD operations on User, Source, SourceItem, Commitment
- Implement Pydantic validation and response models
- Add RLS policies (Supabase auth layer)
- Set up async SQLAlchemy session management (app/db/session.py)

---

*Decision document complete. Ready for Kevin's review and approval before proceeding to Phase 02.*

---

## 6. Phase 01 Fix Pass — Q&A Decisions Applied (2026-03-09)

All changes in this section implement Kevin-approved decisions from `qa-decisions.md`.
Migration: `23ab33b28525_phase01_qa_fixes.py`

### 6.1 Q1 — Candidate ↔ Commitment N:M join table

**Change:** Removed `commitment_candidates.commitment_id` nullable FK column. Created `candidate_commitments` join table with `candidate_id → commitment_candidates.id CASCADE` and `commitment_id → commitments.id CASCADE`, plus a UNIQUE constraint on `(candidate_id, commitment_id)`.

**Rationale:** One email can yield two commitments (1→N). Multiple detection passes on the same conversation can merge into one commitment (N→1). The old nullable FK modelled only 1:1 promotion; the join table correctly models N:M. The `was_promoted` boolean on candidates remains and should be set `true` whenever any `candidate_commitments` row is created for that candidate.

**Files changed:** `app/models/commitment_candidate.py`, `app/models/commitment.py`, new `app/models/candidate_commitment.py`, `app/models/__init__.py`, `app/models/schemas.py`, `migrations/env.py`.

### 6.2 Q3 — `context_type` CHECK tightened to binary

**Change:** Updated CHECK constraint on `commitments.context_type` from `IN ('internal', 'external', 'mixed')` to `IN ('internal', 'external')`.

**Rationale:** A "big promise" represents the overall delivery and can be classified as external even if intermediate signals involve internal communication. `mixed` creates ambiguity in surfacing logic and is not needed.

**Files changed:** `app/models/commitment.py`, migration above.

### 6.3 Q4 — `commitment_type` converted from TEXT to ENUM

**Change:** Added `CommitmentType` enum in `app/models/enums.py` with values: `send`, `review`, `follow_up`, `deliver`, `investigate`, `introduce`, `coordinate`, `update`, `delegate`, `schedule`, `confirm`, `other`. Updated `commitments.commitment_type` column to use `commitment_type_enum` PostgreSQL type. Added review-scheduled comment in `enums.py` flagging ~2026-03-30 for audit of `other` usage.

**Rationale:** Enum enforces valid values at DB level and makes detection model output explicit. `other` fallback prevents migration churn for edge cases. The review cron ensures `other` doesn't become a permanent catch-all.

**Files changed:** `app/models/enums.py`, `app/models/commitment.py`, `app/models/schemas.py`, migration above.

### 6.4 Fixes confirmed already applied in `5c64f63`

The following were already applied in the prior code-review fix commit and required no further code changes:

- **originating_item_id application guard** (Blocker 1): `CommitmentCandidate.originating_item_id` is nullable at DB level with `SET NULL` on delete; comment in model and `CommitmentCandidateCreate` enforces required field at application layer.
- **DATABASE_URL guard** (Blocker 2): `migrations/env.py` raises `RuntimeError` with descriptive message if `DATABASE_URL` is missing or empty.
- **CheckConstraint naming** (Warning): All `CheckConstraint` names use the suffix convention (`name="confidence"`, `name="conf_commitment"` etc.); `base.py` `MetaData(naming_convention=...)` applies the `ck_<table>_<suffix>` prefix automatically — Alembic autogenerate produces stable names.
- **resolved_by_signal_id → resolved_by_item_id** (Warning): Column was already created with the correct name `resolved_by_item_id` in the Phase 01 migration; model and schema already reflected the rename.

### 6.5 Schema count update

After this fix pass:
- **9 tables** (added `candidate_commitments`)
- **9 enum types** (added `commitment_type_enum`)
- Updated `commitments` to enforce strict binary `context_type` and typed `commitment_type`
