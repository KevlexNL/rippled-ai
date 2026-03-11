# Phase 02 — API Scaffold: Interpretation

**Phase:** 02-api-scaffold
**Date:** 2026-03-10
**Status:** Awaiting Kevin approval before implementation

---

## 1. Route Map

All routes are prefixed with `/api/v1` (from `settings.api_prefix`).

### Sources

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| POST | `/sources` | `SourceCreate` | `SourceRead` | Register a new source connection (meeting calendar, Slack workspace, email account) |
| GET | `/sources` | — | `list[SourceRead]` | List all sources for the current user |
| GET | `/sources/{source_id}` | — | `SourceRead` | Retrieve a single source |
| PATCH | `/sources/{source_id}` | `SourceUpdate` | `SourceRead` | Update display name, active status, or metadata |
| DELETE | `/sources/{source_id}` | — | `204 No Content` | Soft-delete (set `is_active = false`) or hard delete; TBD in open questions |

### Source Items (Ingestion)

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| POST | `/source-items` | `SourceItemCreate` | `SourceItemRead` | Ingest a single meeting/slack/email item; triggers async detection pipeline |
| POST | `/source-items/batch` | `list[SourceItemCreate]` | `list[SourceItemRead]` | Batch ingest up to N items; same pipeline trigger per item |
| GET | `/source-items/{item_id}` | — | `SourceItemRead` | Retrieve a single source item (debugging / audit) |

### Commitments

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/commitments` | query: `lifecycle_state`, `priority_class` | `list[CommitmentRead]` | List commitments with optional filters |
| GET | `/commitments/{commitment_id}` | — | `CommitmentRead` | Retrieve a single commitment with full detail |
| PATCH | `/commitments/{commitment_id}` | `CommitmentUpdate` | `CommitmentRead` | Human confirmation of resolved_owner, resolved_deadline, lifecycle_state; creates lifecycle_transition record |
| DELETE | `/commitments/{commitment_id}` | — | `204 No Content` | Transition to `discarded` state (not hard delete) |

### Commitment Signals

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/commitments/{commitment_id}/signals` | — | `list[CommitmentSignalRead]` | List all signals linked to a commitment (provenance chain) |
| POST | `/commitments/{commitment_id}/signals` | `CommitmentSignalCreate` | `CommitmentSignalRead` | Manually link a source item as a signal (for testing / admin use) |

### Commitment Ambiguities

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/commitments/{commitment_id}/ambiguities` | — | `list[CommitmentAmbiguityRead]` | List ambiguities; used by clarification UI |
| POST | `/commitments/{commitment_id}/ambiguities` | `CommitmentAmbiguityCreate` | `CommitmentAmbiguityRead` | Create an ambiguity record (detection pipeline use) |
| PATCH | `/commitments/{commitment_id}/ambiguities/{ambiguity_id}` | `{is_resolved: bool, resolved_by_item_id?: str}` | `CommitmentAmbiguityRead` | Mark an ambiguity as resolved |

### Surfacing

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/surface/main` | — | `list[CommitmentRead]` | Big promises ready for the Main view |
| GET | `/surface/shortlist` | — | `list[CommitmentRead]` | Small commitments ready for the Shortlist |
| GET | `/surface/clarifications` | — | `list[CommitmentRead]` | Commitments with unresolved ambiguities needing human input |

### Commitment Candidates (internal / debug)

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/candidates` | — | `list[CommitmentCandidateRead]` | List detection candidates (debug/audit; not exposed in UI) |
| GET | `/candidates/{candidate_id}` | — | `CommitmentCandidateRead` | Retrieve single candidate |

### System

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Already exists; no change |

---

## 2. DB Session Layer — Async SQLAlchemy Plan

### Problem with current `client.py`
The existing `app/db/client.py` wraps the Supabase Python client (REST API over HTTP). This is fine for simple CRUD but cannot support:
- Proper transactions across multiple tables
- Efficient async queries with ORM relationships
- Alembic-managed migrations (Alembic uses SQLAlchemy, not Supabase client)

Phase 02 will add a parallel SQLAlchemy async layer. The Supabase client can remain for any Supabase-specific operations (auth, storage) but all data access in routes uses SQLAlchemy.

### Engine setup — `app/db/engine.py` (new file)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings

def _make_async_url(url: str) -> str:
    """Convert postgres:// or postgresql:// to postgresql+asyncpg://"""
    return url.replace("postgresql://", "postgresql+asyncpg://") \
              .replace("postgres://", "postgresql+asyncpg://")

settings = get_settings()
engine = create_async_engine(
    _make_async_url(settings.database_url),
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

### `get_db` dependency — `app/db/deps.py` (new file)

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.engine import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Usage in routes

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.deps import get_db

@router.get("/commitments")
async def list_commitments(db: AsyncSession = Depends(get_db), ...):
    ...
```

### ORM Models
Phase 02 requires SQLAlchemy ORM model classes (`app/models/orm.py`) that mirror the Alembic-managed tables. These use `DeclarativeBase` + `mapped_column`. They are separate from Pydantic schemas. Pydantic schemas are used only at the API boundary (request/response); ORM models are used for DB queries.

### Required new dependency
`asyncpg` must be added to `requirements.txt` (or `pyproject.toml`).

---

## 3. App Structure Plan

```
app/
├── api/
│   └── routes/
│       ├── __init__.py
│       ├── sources.py          # /sources CRUD
│       ├── source_items.py     # /source-items ingestion
│       ├── commitments.py      # /commitments CRUD + signals + ambiguities
│       ├── surface.py          # /surface/main, /surface/shortlist, /surface/clarifications
│       └── candidates.py       # /candidates (debug/audit)
├── core/
│   ├── config.py               # existing
│   └── dependencies.py         # get_current_user_id (X-User-ID header)
├── db/
│   ├── client.py               # existing Supabase client (keep for now)
│   ├── engine.py               # NEW: async engine + session factory
│   └── deps.py                 # NEW: get_db FastAPI dependency
├── models/
│   ├── enums.py                # existing
│   ├── schemas.py              # existing Pydantic schemas
│   └── orm.py                  # NEW: SQLAlchemy ORM models
└── main.py                     # register routers here
```

### Router registration in `main.py`

```python
from app.api.routes import sources, source_items, commitments, surface, candidates

app.include_router(sources.router, prefix=settings.api_prefix, tags=["sources"])
app.include_router(source_items.router, prefix=settings.api_prefix, tags=["ingestion"])
app.include_router(commitments.router, prefix=settings.api_prefix, tags=["commitments"])
app.include_router(surface.router, prefix=settings.api_prefix, tags=["surfacing"])
app.include_router(candidates.router, prefix=settings.api_prefix, tags=["candidates"])
```

---

## 4. User Isolation — X-User-ID Header (MVP)

### Approach
No auth system in Phase 02. User identity is established via a required `X-User-ID` request header. Every route that accesses user data requires this header.

### Dependency — `app/core/dependencies.py`

```python
from fastapi import Header, HTTPException

async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header required")
    return x_user_id
```

### Usage

```python
from app.core.dependencies import get_current_user_id

@router.get("/commitments")
async def list_commitments(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # All queries filter: WHERE user_id = user_id
    ...
```

### Isolation guarantee
Every DB query includes an explicit `WHERE user_id = :user_id` filter. No query ever returns rows from a different user. This is enforced at the route handler level — not via RLS (row-level security is a later concern).

### Notes
- `X-User-ID` must match a row in the `users` table or routes return 404 on first lookup
- Phase 02 does **not** validate that the user exists on every call (too expensive); the commitment/source routes naturally fail with FK violations if the user doesn't exist
- This is explicitly an MVP shortcut — replace with JWT + Supabase Auth in a future phase

---

## 5. Ingestion Route Detail — POST /source-items

### Endpoint
`POST /api/v1/source-items`

### Request
```
Header: X-User-ID: <user_uuid>
Body: SourceItemCreate
```

Key fields in `SourceItemCreate`:
- `source_id` — must belong to the requesting user (validated)
- `source_type` — `meeting | slack | email`
- `external_id` — provider's own ID; used for dedup via unique constraint `uq_source_items_source_external`
- `occurred_at` — timestamp of the original event (required)
- `content` — raw text body
- `thread_id` — groups related items (email thread, Slack thread)
- `direction` — `inbound | outbound | sent | received | internal` (source-type dependent)

### Handler logic (ordered steps)

1. **Validate source ownership** — query `SELECT id FROM sources WHERE id = :source_id AND user_id = :user_id`; 404 if not found
2. **Dedup check** — the DB has a unique constraint on `(source_id, external_id)`; catch `IntegrityError` and return `409 Conflict` with the existing item's ID
3. **Insert `source_items` row** — set `ingested_at = now()`, `user_id` from header
4. **Enqueue detection task** — push `detect_commitments(source_item_id)` to Celery/Redis queue (fire-and-forget; the route does not wait for detection)
5. **Return** `SourceItemRead` with `201 Created`

### Batch variant — POST /source-items/batch
- Accepts `list[SourceItemCreate]` (max 100 items)
- Runs steps 1–4 for each item in a single transaction
- On partial failure (e.g., one dedup conflict): **reject the whole batch** and return `207 Multi-Status` with per-item results
- Open question: whether partial success should be allowed (see §7)

### Silent observation window
After ingestion, the detection pipeline sets `observe_until = now() + observation_window_hours`. Items are not surfaced until `observe_until` has passed. This is enforced in the surfacing queries (§6), not here.

---

## 6. Surfacing Routes — Filter Logic

All surfacing routes require `X-User-ID` header and return only that user's commitments.

### GET /surface/main — Big Promises

Returns commitments that are ready to be surfaced on the Main view.

**Filter logic:**
```sql
WHERE user_id = :user_id
  AND priority_class = 'big_promise'
  AND lifecycle_state IN ('active', 'needs_clarification')
  AND is_surfaced = true
  AND (observe_until IS NULL OR observe_until <= NOW())
```

**Sort:** `resolved_deadline ASC NULLS LAST, created_at DESC`

**Rationale:**
- `big_promise` only — Main is for high-stakes items
- `active` and `needs_clarification` — both are actionable states; `needs_clarification` appears here to prompt resolution, not on a separate screen
- `is_surfaced = true` — detection pipeline sets this once observation window clears and confidence threshold is met
- `observe_until` guard — respects the silent observation window; if the window hasn't closed, the item stays off Main even if `is_surfaced = true`

---

### GET /surface/shortlist — Small Commitments

Returns commitments ready for the Shortlist view.

**Filter logic:**
```sql
WHERE user_id = :user_id
  AND priority_class = 'small_commitment'
  AND lifecycle_state IN ('active', 'needs_clarification')
  AND is_surfaced = true
  AND (observe_until IS NULL OR observe_until <= NOW())
```

**Sort:** `resolved_deadline ASC NULLS LAST, confidence_actionability DESC`

**Rationale:**
- Same surface-readiness conditions as Main, but for `small_commitment` class
- `confidence_actionability` sort puts more actionable items first within same deadline group

---

### GET /surface/clarifications — Needs Human Input

Returns commitments that have unresolved ambiguities, requiring human clarification before they can be properly surfaced.

**Filter logic:**
```sql
WHERE user_id = :user_id
  AND lifecycle_state = 'needs_clarification'
  AND is_surfaced = true
  AND EXISTS (
    SELECT 1 FROM commitment_ambiguities ca
    WHERE ca.commitment_id = commitments.id
      AND ca.is_resolved = false
  )
```

**Sort:** `state_changed_at ASC` (oldest ambiguity first — longest waiting)

**Rationale:**
- `needs_clarification` state is the primary signal
- The `EXISTS` subquery ensures there are actually open ambiguities (defensive — state and ambiguity table should be in sync, but this prevents ghost entries)
- No `priority_class` filter — both big promises and small commitments can need clarification
- `observe_until` is NOT applied here — if a commitment needs clarification, it should be shown regardless of observation window

---

### Response shape for all surfacing routes
All three return `list[CommitmentRead]`. The frontend decides how to render Main vs Shortlist differently. No special surfacing-specific schema.

---

## 7. Open Questions

### Q1: Soft delete vs hard delete for sources
**Issue:** Should `DELETE /sources/{id}` set `is_active = false` (soft) or actually remove the row?
**Impact:** Hard delete cascades to `source_items`, which cascade to `commitment_signals` (SET NULL), which could orphan commitments. Soft delete avoids data loss but makes "clean up" harder.
**Leaning:** Soft delete (set `is_active = false`) for MVP. No cascade risk.

### Q2: Batch ingestion — partial success or all-or-nothing?
**Issue:** On batch POST, if 1 of 50 items is a duplicate, should we return 409 for all or accept the other 49?
**Impact:** All-or-nothing is simpler (single transaction, single rollback). Partial success is friendlier for idempotent connectors that re-send seen items.
**Leaning:** Partial success with `207 Multi-Status` — connector use case is the primary batch caller and idempotency matters.

### Q3: ORM models vs raw SQL for Phase 02
**Issue:** Writing full SQLAlchemy ORM models (`app/models/orm.py`) is comprehensive but adds substantial boilerplate upfront. Alternative: use `text()` raw SQL queries in handlers for Phase 02 and introduce ORM models in Phase 03.
**Impact:** Raw SQL is faster to write but loses type safety and makes relationship loading harder.
**Leaning:** Write ORM models in Phase 02 — the schema is already stable (Phase 01), so the mapping is mechanical. Avoiding ORM now just defers the work and creates inconsistency.

### Q4: `is_surfaced` flag — who sets it?
**Issue:** The surfacing queries filter on `is_surfaced = true`, but Phase 02 has no detection pipeline yet (that's Phase 03). Should `is_surfaced` default to `true` for items created via API in Phase 02 (for testability), or always `false` until detection runs?
**Leaning:** Default `false` in DB schema (already defined that way). In Phase 02 tests, manually PATCH commitments to `is_surfaced = true` to exercise surfacing routes. No special bypass logic needed.

### Q5: Lifecycle state transition validation
**Issue:** `CommitmentUpdate` allows setting `lifecycle_state` freely. Should the API enforce valid transitions (e.g., `discarded → active` is invalid) or trust the caller?
**Impact:** Enforcing transitions requires a state machine map in code.
**Leaning:** Enforce valid transitions in Phase 02. Simple dict lookup: `VALID_TRANSITIONS = {proposed: [active, needs_clarification, discarded], ...}`. Raises `400` on invalid transition.

### Q6: Pagination on list routes
**Issue:** No pagination defined in schemas. Long-term, `/commitments` and surfacing routes need `limit/offset` or cursor pagination.
**Leaning:** Add `limit` (default 50, max 200) and `offset` (default 0) query params to all list routes in Phase 02. Simple and sufficient for MVP scale.

### Q7: asyncpg vs psycopg3 for async driver
**Issue:** `asyncpg` is the standard async PostgreSQL driver for SQLAlchemy. `psycopg3` (psycopg[async]) is newer and supports more features.
**Leaning:** `asyncpg` — more battle-tested with SQLAlchemy async, better documented.

---

## 8. Kevin's Decisions (2026-03-10)

| Q | Decision |
|---|----------|
| Q1 | Soft delete (`is_active = false`) |
| Q2 | Partial success allowed — `207 Multi-Status`. **Post-MVP TODO:** build process to pull partial failures and fix automatically |
| Q3 | Write ORM models in Phase 02 now |
| Q4 | `is_surfaced` defaults `false`; manually PATCH in tests |
| Q5 | Enforce valid lifecycle transitions (state machine dict, 400 on invalid) |
| Q6 | Pagination now. **5 items max** on all user-facing surfaces. Admin/triage layer gets separate deeper pagination later. The rule: be strict on what gets shown and why — don't create another list for users to manage |
| Q7 | `asyncpg` — lower friction for launch; swap to psycopg3 later if needed |
| Supabase REST | Retire `client.py` for data access. Keep Supabase as Postgres host. Connect directly via SQLAlchemy + asyncpg. Supabase's security/infra benefits are in the hosting layer — untouched |

## 9. Standing Rule (set 2026-03-10)
**Low-friction default:** When a technical choice can be easily replaced later, always choose the option with least friction for the current stage. Optimize for launch speed, not future perfection — unless the choice actively blocks the short-to-mid-term vision.
