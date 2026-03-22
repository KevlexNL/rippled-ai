# Phase 02 — API Scaffold: Interpretation

**Phase:** 02-api-scaffold
**Date:** 2026-03-22 (retroactive documentation of as-built state)
**Status:** Implementation complete — this interpretation documents what was built

---

## Context

This WO was written when the project had Phase 01 (schema) complete and empty route stubs. The project has since progressed through phases 03–05, connectors, frontend, admin, and multiple fix cycles. The API scaffold described here is fully implemented and in production.

This interpretation documents the as-built architecture against the 7 points required by the WO, noting where the implementation evolved beyond the original plan.

---

## 1. Route Map

All routes are prefixed with `/api/v1` (from `settings.api_prefix`).

### Core Routes (WO Scope)

#### Sources — `app/api/routes/sources.py`

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| POST | `/sources` | `SourceCreate` | `SourceRead` | Register a new source connection |
| GET | `/sources` | query: `limit`, `offset` | `list[SourceRead]` | List user's sources |
| GET | `/sources/{source_id}` | — | `SourceRead` | Retrieve single source |
| PATCH | `/sources/{source_id}` | `SourceUpdate` | `SourceRead` | Update display name, active status, metadata |
| DELETE | `/sources/{source_id}` | — | `204` | Soft-delete (sets `is_active = false`) |

**Added beyond WO scope** (connector onboarding):

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/sources/setup/email` | Email IMAP setup with connection test |
| POST | `/sources/setup/slack` | Slack bot token setup with auth.test validation |
| POST | `/sources/setup/meeting` | Meeting webhook setup with secret generation |
| POST | `/sources/test/email` | Test IMAP connection without persisting |
| POST | `/sources/test/slack` | Validate Slack bot token |
| GET | `/sources/onboarding-status` | Check if user has any active sources |
| POST | `/sources/{source_id}/regenerate-secret` | Regenerate meeting webhook secret |

#### Source Items (Ingestion) — `app/api/routes/source_items.py`

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| POST | `/source-items` | `SourceItemCreate` | `SourceItemRead` | Ingest single item; triggers async detection |
| POST | `/source-items/batch` | `list[SourceItemCreate]` (max 100) | `207` with per-item results | Batch ingest with partial success |
| GET | `/source-items/{item_id}` | — | `SourceItemRead` | Retrieve single item (audit) |

#### Commitments — `app/api/routes/commitments.py`

| Method | Path | Request Schema | Response Schema | Purpose |
|--------|------|---------------|-----------------|---------|
| GET | `/commitments` | query: `lifecycle_state`, `priority_class`, `relationship`, `limit`, `offset` | `list[CommitmentRead]` | List with filters |
| POST | `/commitments` | `CommitmentCreate` | `CommitmentRead` | Create commitment |
| GET | `/commitments/{id}` | — | `CommitmentRead` | Single commitment with linked events |
| PATCH | `/commitments/{id}` | `CommitmentUpdate` | `CommitmentRead` | Update fields; enforces lifecycle transitions |
| DELETE | `/commitments/{id}` | — | `204` | Transition to `discarded` (not hard delete) |

**Added beyond WO scope:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/commitments/{id}/skip` | Skip from review queue without lifecycle change |
| PATCH | `/commitments/{id}/delivery-state` | Update delivery state (Phase C3) |
| GET | `/commitments/{id}/events` | List linked calendar events |
| POST | `/commitments/{id}/events` | Link commitment to calendar event |

**Sub-resources (signals + ambiguities):**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/commitments/{id}/signals` | List enriched signals (with source text) |
| POST | `/commitments/{id}/signals` | Link source item as signal |
| GET | `/commitments/{id}/ambiguities` | List ambiguities |
| POST | `/commitments/{id}/ambiguities` | Create ambiguity record |
| PATCH | `/commitments/{id}/ambiguities/{aid}` | Resolve ambiguity |

#### Surfacing — `app/api/routes/surface.py`

| Method | Path | Response Schema | Purpose |
|--------|------|-----------------|---------|
| GET | `/surface/main` | `list[CommitmentRead]` | Big promises — `surfaced_as = 'main'`, `user_relationship = 'mine'` |
| GET | `/surface/shortlist` | `list[CommitmentRead]` | Small commitments — `surfaced_as = 'shortlist'`, mine + contributing |
| GET | `/surface/clarifications` | `list[CommitmentRead]` | Items needing human input |
| GET | `/surface/best-next-moves` | `BestNextMovesResponse` | Grouped top-5 actions (quick wins, blockers, needs focus) |
| GET | `/surface/internal` | `list[CommitmentRead]` | Unsurfaced active items (debug/admin) |

#### Candidates — `app/api/routes/candidates.py`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/candidates` | List detection candidates (debug/audit) |
| GET | `/candidates/{id}` | Retrieve single candidate |

### Routes Added Beyond WO Scope

The following route modules were added in later phases but are registered in `app/main.py`:

| Module | Prefix | Purpose |
|--------|--------|---------|
| `contexts.py` | `/contexts` | Commitment context grouping |
| `webhooks/email.py` | `/webhooks/email` | Inbound email webhook |
| `webhooks/slack.py` | `/webhooks/slack` | Slack event webhook |
| `webhooks/meetings.py` | `/webhooks/meeting` | Meeting transcript webhook |
| `digest.py` | `/digest` | Daily digest generation/preview |
| `events.py` | `/events` | Calendar event CRUD |
| `integrations.py` | `/integrations` | OAuth flows (Slack, Google Calendar) |
| `admin.py` | `/admin` | Admin API (pipeline re-runs, stats) |
| `admin_review.py` | `/admin/review` | Admin review queue |
| `user_settings.py` | `/user-settings` | User preference management |
| `clarifications.py` | `/clarifications` | Clarification queue endpoints |
| `stats.py` | `/stats` | Dashboard statistics |
| `identity.py` | `/identity` | Contact identity resolution |
| `report.py` | `/report` | Report generation |

---

## 2. DB Session Layer

### As-Built Architecture

The DB layer is split across three files:

**`app/db/engine.py` — Async engine (FastAPI routes)**
- `create_async_engine` with `postgresql+asyncpg://` driver
- `pool_size=10`, `max_overflow=20`
- `statement_cache_size=0` in connect_args for Supabase/PgBouncer compatibility
- `echo=True` in development
- Exports `AsyncSessionLocal` (async_sessionmaker)

**`app/db/deps.py` — FastAPI dependency**
- `get_db()` async generator yields `AsyncSession`
- Auto-commits on success, rolls back on exception
- Used via `Depends(get_db)` in every route handler

**`app/db/session.py` — Sync engine (Celery workers)**
- Separate sync engine via `create_engine` with `postgresql://` driver
- `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`
- `get_sync_session()` context manager for Celery tasks
- Needed because Celery workers run synchronously

**`app/db/client.py` — Supabase REST client (legacy)**
- Still exists for any Supabase-specific operations
- All data access uses SQLAlchemy; this is effectively retired for CRUD

### Key Decision
The original interpretation proposed async-only. The implementation added a sync session layer when Celery was introduced (detection pipeline runs in background workers). This dual-engine approach is clean: routes use async, workers use sync, both hit the same Postgres.

---

## 3. App Structure

### As-Built Layout

```
app/
├── api/
│   └── routes/
│       ├── __init__.py
│       ├── sources.py              # Source CRUD + setup/onboarding
│       ├── source_items.py         # Ingestion endpoint
│       ├── commitments.py          # Commitment CRUD + signals + ambiguities + delivery
│       ├── surface.py              # Main / Shortlist / Clarifications / Best-next-moves
│       ├── candidates.py           # Candidate debug/audit
│       ├── contexts.py             # Commitment contexts
│       ├── clarifications.py       # Clarification queue
│       ├── digest.py               # Daily digest
│       ├── events.py               # Calendar events
│       ├── integrations.py         # OAuth flows
│       ├── admin.py                # Admin operations
│       ├── admin_review.py         # Admin review queue
│       ├── user_settings.py        # User preferences
│       ├── stats.py                # Dashboard stats
│       ├── identity.py             # Contact identity
│       ├── report.py               # Reporting
│       └── webhooks/
│           ├── email.py            # Inbound email webhook
│           ├── slack.py            # Slack event webhook
│           └── meetings.py         # Meeting transcript webhook
├── connectors/
│   └── shared/
│       └── credentials_utils.py    # Encrypt/decrypt source credentials
├── core/
│   ├── config.py                   # Pydantic Settings (env vars)
│   └── dependencies.py             # get_current_user_id, get_user_id_for_redirect
├── db/
│   ├── client.py                   # Supabase REST client (legacy)
│   ├── engine.py                   # Async SQLAlchemy engine
│   ├── deps.py                     # get_db FastAPI dependency
│   └── session.py                  # Sync session for Celery
├── models/
│   ├── base.py                     # DeclarativeBase
│   ├── enums.py                    # 10+ enum types
│   ├── schemas.py                  # Pydantic v2 request/response schemas
│   ├── orm.py                      # SQLAlchemy ORM model registry
│   ├── commitment.py               # Commitment ORM model
│   ├── commitment_candidate.py     # CommitmentCandidate ORM model
│   ├── commitment_signal.py        # CommitmentSignal ORM model
│   ├── commitment_ambiguity.py     # CommitmentAmbiguity ORM model
│   ├── source.py                   # Source ORM model
│   ├── source_item.py              # SourceItem ORM model
│   ├── user.py                     # User ORM model
│   ├── lifecycle_transition.py     # LifecycleTransition ORM model
│   └── ...                         # Additional models (normalized_signal, etc.)
├── services/                       # Business logic layer (detection, surfacing, etc.)
└── main.py                         # FastAPI app + router registration + CORS + static serving
```

### Router Registration

All routers registered in `app/main.py` via `app.include_router()` with `prefix=settings.api_prefix` and appropriate tags. Routes are organized by domain concern, not by HTTP method.

### Key Structural Decision
ORM models are split into individual files per entity (not a single `orm.py`). `app/models/orm.py` serves as a registry that re-exports all models for convenient imports.

---

## 4. User Isolation Approach

### Mechanism: `X-User-ID` Header

**`app/core/dependencies.py`** provides two dependencies:

1. **`get_current_user_id()`** — Extracts `X-User-ID` header (required). Returns 400 if missing.
2. **`get_user_id_for_redirect()`** — Accepts either `user_id` query param or `X-User-ID` header. Used for OAuth callback flows where browser navigations can't carry custom headers.

### Enforcement Pattern

Every route handler that accesses user data:
1. Declares `user_id: str = Depends(get_current_user_id)`
2. Adds `WHERE user_id = :user_id` to every query
3. Validates ownership of related resources (e.g., source_items validates source belongs to user)

### Cross-Resource Validation

- `POST /source-items` validates `source_id` belongs to user before inserting
- `POST /commitments/{id}/signals` validates commitment belongs to user
- `PATCH /commitments/{id}/ambiguities/{aid}` validates both commitment and ambiguity ownership

### Auto-Provisioning

`sources.py` includes `_ensure_user_exists()` which upserts a user row on first API call using `ON CONFLICT DO NOTHING`. This handles the gap between Supabase auth creating `auth.users` and our app's `users` table needing a corresponding row.

### Limitations (documented, accepted for MVP)
- No JWT validation — anyone with a valid user UUID can impersonate
- No rate limiting
- Replace with Supabase Auth + JWT in a future auth phase

---

## 5. Ingestion Route(s)

### POST /source-items — Single Item Ingestion

**Request:** `SourceItemCreate` with `X-User-ID` header

The `SourceItemCreate` schema handles all three source types through a common structure:

| Field | Meeting | Slack | Email |
|-------|---------|-------|-------|
| `source_type` | `"meeting"` | `"slack"` | `"email"` |
| `external_id` | transcript segment ID | message ts | message-id |
| `thread_id` | meeting ID | thread ts | email thread-id |
| `direction` | — | — | `inbound` / `outbound` |
| `sender_name` | speaker label | Slack display name | From header |
| `sender_email` | — | — | From email |
| `is_external_participant` | inferred | — | domain-based |
| `content` | transcript text | message text | email body |
| `has_attachment` | — | file metadata | attachment presence |
| `occurred_at` | segment timestamp | message ts | Date header |
| `metadata_` | meeting metadata | channel info | headers/recipients |
| `is_quoted_content` | — | — | `true` for quoted text |

**Handler flow:**
1. Validate source ownership → 404 if source doesn't belong to user
2. Build `SourceItem` ORM object with `ingested_at = now()`
3. Flush to DB → catch `IntegrityError` on `(source_id, external_id)` unique constraint → return `409 Conflict` with existing item ID
4. Fire-and-forget: enqueue `detect_commitments(source_item_id)` Celery task (silently skips if broker unavailable)
5. Return `SourceItemRead` with `201`

### POST /source-items/batch — Batch Ingestion

- Accepts `list[SourceItemCreate]` (max 100, returns 422 if exceeded)
- Uses `db.begin_nested()` (savepoints) per item for partial success
- Returns `207 Multi-Status` with per-item results: `{status: 201|404|409, id?, error?, external_id}`
- Each successful item triggers detection independently

### Webhook Ingestion (added in later phases)

The WO described source-items as the only ingestion path. In practice, three webhook routes were added:

- `POST /webhooks/email/events` — Receives email payloads, normalizes to SourceItem + triggers detection
- `POST /webhooks/slack/events` — Receives Slack events (message, thread_reply), validates signature, normalizes + triggers detection
- `POST /webhooks/meeting/events` — Receives meeting transcripts, validates webhook secret, normalizes + triggers detection

These webhooks perform the same core flow as POST /source-items but include provider-specific validation (HMAC signatures, webhook secrets) and normalization logic.

---

## 6. Surfacing Routes

### Design Evolution

The original interpretation proposed filtering on `priority_class` + `is_surfaced` + `observe_until`. The as-built implementation uses a dedicated `surfaced_as` column set by the Phase 06 surfacing pipeline, plus `priority_score` for ordering.

### GET /surface/main — Big Promises

```
WHERE user_id = :user_id
  AND surfaced_as = 'main'
  AND lifecycle_state IN ('active', 'needs_clarification', 'proposed')
  AND skipped_at IS NULL
  AND structure_complete = true
  AND user_relationship IN ('mine')
ORDER BY priority_score DESC NULLS LAST, created_at DESC
LIMIT 10
```

**Key filters:**
- `surfaced_as = 'main'` — set by surfacing pipeline based on scoring
- `structure_complete = true` — ensures commitment has been through structural classification
- `user_relationship = 'mine'` — Main only shows commitments owned by user
- `skipped_at IS NULL` — respects user's skip actions

### GET /surface/shortlist — Small Commitments

Same pattern but:
- `surfaced_as = 'shortlist'`
- `user_relationship IN ('mine', 'contributing')` — includes commitments user contributes to

### GET /surface/clarifications — Needs Human Input

- `surfaced_as = 'clarifications'`
- No `structure_complete` or `user_relationship` filter — any unclear item surfaces here
- Ordered by `priority_score DESC, state_changed_at ASC` (oldest ambiguity first)

### GET /surface/best-next-moves — Grouped Actions

Returns up to 5 items in three groups:
1. **Quick wins** — low-effort commitment types (confirm, send, update, follow_up) or shortlist items with confidence >= 0.65
2. **Likely blockers** — overdue items with external counterparty
3. **Needs focus** — remaining surfaced items by priority

### GET /surface/internal — Debug View

Returns unsurfaced active commitments (`surfaced_as IS NULL`). Admin/debug only.

### Enrichment

All surfacing endpoints batch-fetch and inject:
- **Linked calendar events** (delivery_at relationships)
- **Origin source metadata** (sender name, email, occurred_at from the first origin signal)

---

## 7. Questions / Ambiguities

All original open questions from the initial interpretation have been resolved through implementation:

| Question | Resolution |
|----------|-----------|
| Soft vs hard delete for sources | **Soft delete** — `is_active = false` (implemented) |
| Batch partial success | **Partial success** — `207 Multi-Status` with per-item results (implemented) |
| ORM vs raw SQL | **ORM models** — individual files per entity, registry in `orm.py` (implemented) |
| `is_surfaced` flag ownership | **Replaced** — `surfaced_as` column set by Phase 06 surfacing pipeline; `is_surfaced` retained as secondary flag |
| Lifecycle transition validation | **Enforced** — `VALID_TRANSITIONS` dict in commitments.py, returns 400 on invalid (implemented) |
| Pagination | **Implemented** — `limit` (default 5, max 200) + `offset` on all list routes |
| Async driver | **asyncpg** with `statement_cache_size=0` for Supabase/PgBouncer compat (implemented) |

### Remaining Notes

1. **No auth middleware** — `X-User-ID` header is the sole identity mechanism. Accepted for MVP; auth phase planned.
2. **CORS wide open** — `allow_origins=["*"]` in CORS middleware. Acceptable for MVP single-user deployment.
3. **No Celery in this phase** — WO said "synchronous ingestion only" but detection was implemented as Celery fire-and-forget from day one. The route itself is synchronous (returns immediately after DB insert); detection runs async in a worker.
4. **Surfacing evolved significantly** — moved from simple `priority_class` + `is_surfaced` filtering to a full scoring pipeline (`surfaced_as`, `priority_score`, `structure_complete`, `user_relationship`). This was the right call — the brief's Main/Shortlist/Clarifications distinction needed richer routing than simple column filters.

---

## Kevin's Original Decisions (2026-03-10, preserved)

| Q | Decision |
|---|----------|
| Q1 | Soft delete (`is_active = false`) |
| Q2 | Partial success — `207 Multi-Status` |
| Q3 | ORM models in Phase 02 |
| Q4 | `is_surfaced` defaults false; manually PATCH in tests |
| Q5 | Enforce lifecycle transitions (state machine dict, 400) |
| Q6 | 5 items max on user-facing surfaces |
| Q7 | asyncpg — lowest friction |
| Supabase REST | Retired for data access; keep as Postgres host |

## Standing Rule (set 2026-03-10)
**Low-friction default:** When a technical choice can be easily replaced later, always choose the option with least friction for the current stage.
