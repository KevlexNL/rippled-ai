# Phase 01 Schema — Skill Review

**Skills applied:** postgres-best-practices, static-analysis (semgrep, conceptual), insecure-defaults
**Files audited:** `migrations/versions/`, `app/models/orm.py`, `app/models/enums.py`
**Date:** 2026-03-10

---

## Issues Found

### CRITICAL

#### C1 — `sources.credentials` stored in plaintext JSONB

**Location:** `migrations/versions/f18635e47575_phase01_core_schema.py:93`, `app/models/orm.py:49`

```sql
sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
```

**Problem:** OAuth tokens, API keys, and other credentials are stored unencrypted in a plain JSONB column. Anyone with SELECT access to the `sources` table (including read-only DB roles, Supabase studio, logs, backups) can read them.

**Risk:** Credential exfiltration. If a backup leaks or a read-replica is compromised, all user source credentials are exposed.

**Fix options:**
- Use `pgcrypto`'s `pgp_sym_encrypt()` at the DB level to encrypt the JSONB blob
- OR store credentials in a dedicated secrets vault (e.g., Supabase Vault, HashiCorp Vault) and reference them by ID
- At minimum, add a DB-level NOTE making this explicit and ensure the column is excluded from any analytics/read replicas

---

### WARNING

#### W1 — Missing composite indexes for common query patterns

**Location:** `migrations/versions/f18635e47575_phase01_core_schema.py`

The surface queries (Phase 06) and detection queries (Phase 03) will filter on multiple columns simultaneously. Current single-column indexes will force PostgreSQL to choose one and recheck:

| Missing Index | Table | Rationale |
|---|---|---|
| `(user_id, lifecycle_state)` | `commitments` | All surface endpoints filter on both |
| `(user_id, is_surfaced)` | `commitments` | Surface endpoints always scope to user + surfaced |
| `(user_id, occurred_at DESC)` | `source_items` | Ingestion list queries filter by user, order by time |
| `(user_id, was_promoted)` | `commitment_candidates` | Detection pipeline needs these for filtering |

**Fix:** Add these as partial indexes in a follow-up migration:
```sql
CREATE INDEX ix_commitments_user_state ON commitments (user_id, lifecycle_state);
CREATE INDEX ix_commitments_user_surfaced ON commitments (user_id, is_surfaced) WHERE is_surfaced = true;
CREATE INDEX ix_source_items_user_occurred ON source_items (user_id, occurred_at DESC);
CREATE INDEX ix_candidates_promoted ON commitment_candidates (user_id, was_promoted) WHERE was_promoted = true;
```

#### W2 — ORM models use `String` for all enum columns

**Location:** `app/models/orm.py` (pervasive)

```python
# Migration correctly creates PostgreSQL enum types
lifecycle_state_enum = postgresql.ENUM('proposed', 'needs_clarification', 'active', ...)

# ORM model ignores them entirely
lifecycle_state: Mapped[str] = mapped_column(String, ...)
```

**Problem:** The ORM won't validate enum values at the SQLAlchemy layer. Invalid strings can be written without Python-level type errors. The DB check still guards you, but errors surface as `asyncpg.PostgresSyntaxError` at flush time rather than at assignment.

**Fix:** Use `SQLAlchemyEnum` mapped to the Python enums, or add validator logic on the model. Lower priority since Pydantic schemas enforce enums at the API boundary, but worth fixing before the codebase grows.

```python
from sqlalchemy import Enum as SAEnum
from app.models.enums import LifecycleState

lifecycle_state: Mapped[str] = mapped_column(
    SAEnum(LifecycleState, name="lifecycle_state"),
    server_default="proposed",
    nullable=False,
    index=True,
)
```

#### W3 — `observation_window_hours` uses unbounded `Numeric`

**Location:** `migrations/versions/f18635e47575_phase01_core_schema.py:176`

```python
sa.Column('observation_window_hours', sa.Numeric(), nullable=True),
```

`Numeric()` with no precision/scale defaults to arbitrary precision in PostgreSQL. For a column representing hours, this is unnecessarily unbounded. A negative or absurdly large value would pass through unchecked.

**Fix:** Constrain to reasonable range:
```sql
observation_window_hours NUMERIC(6, 2) CHECK (observation_window_hours > 0 AND observation_window_hours <= 8760)
```
(8760 = hours in a year)

#### W4 — `updated_at` has no auto-update trigger

**Location:** All tables with `updated_at`

`updated_at` is set to `now()` at insert via `server_default`, but there's no `BEFORE UPDATE` trigger to auto-refresh it. The application code manually sets it in routes, which is fragile — any future code path that updates a row without manually setting `updated_at` will silently leave stale timestamps.

**Fix:** Add a Postgres trigger function in a migration:
```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sources_updated_at
  BEFORE UPDATE ON sources
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- (repeat for commitments, source_items, commitment_candidates)
```

---

### INFO

#### I1 — Unique constraint naming inconsistency in `candidate_commitments`

**Location:** `migrations/versions/23ab33b28525_phase01_qa_fixes.py:77`

```python
sa.UniqueConstraint(
    'candidate_id', 'commitment_id',
    name=op.f('uq_candidate_commitments_candidate_id'),  # ← name implies only candidate_id
),
```

The constraint enforces `(candidate_id, commitment_id)` uniqueness but is named as if it only constrains `candidate_id`. Misleading when reading `\d candidate_commitments` in psql.

**Fix:** Rename to `uq_candidate_commitments_candidate_commitment` in the next migration touching this table.

#### I2 — No Row-Level Security (RLS) policy

The schema relies entirely on application-level `WHERE user_id = :user_id` scoping. This is correct for the current design (API-mediated access only), but if Supabase's PostgREST or direct DB access is ever enabled, all data is unprotected.

No action needed now. Document the assumption: "This schema does not use Postgres RLS. Auth is enforced at the API layer only."

---

## What's Already Good

- **Enum types are properly modeled in PostgreSQL.** Using native PG enum types (not VARCHAR with CHECK) gives type safety at the DB level and enables future use in pg_dump, pg_restore, and tooling.
- **All FKs have explicit `ondelete` behavior** (`CASCADE`, `SET NULL`) — no accidentally orphaned rows.
- **Check constraints on all confidence columns** (`BETWEEN 0 AND 1`) — solid domain enforcement.
- **`gen_random_uuid()` as server default** — UUIDs generated at the DB layer, consistent and collision-safe.
- **`checkfirst=True` on all enum creates** — idempotent migration, safe to re-run.
- **Downgrade path is complete** — all tables and enums dropped in reverse dependency order.
- **`uq_source_items_source_external` unique constraint** — prevents duplicate ingestion of the same external item, correct design.
- **`uq_commitment_signals_commitment_item_role`** — prevents duplicate signal roles per (commitment, source_item) pair.
- **Migration is split correctly** — initial schema + QA fixes as separate revisions, clean history.
