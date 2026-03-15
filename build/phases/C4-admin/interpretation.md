# Phase C4 — Super Admin UI: Interpretation

**Written by:** Claude Code
**Date:** 2026-03-14
**Stage:** STAGE 2 — INTERPRET

---

## What This Phase Does and Why

Phase C4 builds a dense operator tool served at `/admin` — a separate React SPA with its own build, its own auth mechanism, and its own backend router. This is not a user-facing screen. It is Kevin's and the dev team's window into system internals during testing: raw commitment tables, candidate explorer, surfacing audit trail, pipeline triggers, and test data management.

The prior phases built and battle-tested the entire backend stack (detection, clarification, surfacing, events, calendar, digest, scoring — 538 tests). The stack is now rich enough that operators need purpose-built tooling to inspect and manipulate state without going directly to the database. C4 provides that without touching production user paths.

What makes C4 non-trivial:
- The admin SPA lives at `/admin` in the same FastAPI process that serves the user SPA at `/` — SPA fallback routing has to be precisely ordered or the user frontend will intercept admin requests
- Pipeline trigger endpoints must call synchronous services from an async FastAPI handler without blocking the event loop
- The admin build must be committed pre-built alongside the user frontend (same pattern) and served as static files

---

## Backend Architecture

### Config (`app/core/config.py`)

Two new fields added to `Settings`:

```python
admin_secret_key: str = ""        # if empty → admin API returns 503 Service Unavailable
admin_ui_enabled: bool = True     # killswitch for admin static serving
```

- `admin_secret_key = ""` (empty string) is a deliberate sentinel: an empty key means "not configured". The auth dependency checks for empty first and returns `503`, not `401`. This prevents probing: if the key is not set, the endpoint doesn't reveal it exists at all (no `WWW-Authenticate` header either).
- `lru_cache` on `get_settings()` already exists — these fields slot in cleanly.

### Auth Dependency (`app/api/deps/admin_auth.py`) — NEW FILE

```python
import hmac
from fastapi import Depends, Header, HTTPException
from app.core.config import get_settings

async def verify_admin_key(x_admin_key: str = Header(...)) -> None:
    settings = get_settings()
    if not settings.admin_secret_key:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not hmac.compare_digest(x_admin_key, settings.admin_secret_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
```

- `hmac.compare_digest()` for constant-time comparison — prevents timing attacks
- No import of `app.api.deps.admin_auth` from existing routes — isolated module
- Applied at the router level (not per-endpoint) via `APIRouter(dependencies=[Depends(verify_admin_key)])`

### Router Structure (`app/api/routes/admin.py`) — NEW FILE

All endpoints under `/admin` prefix (registered in `main.py` as `/api/v1/admin`).

Router declaration:
```python
from app.api.deps.admin_auth import verify_admin_key
router = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin_key)])
```

#### Endpoint Shapes

**`GET /admin/health`**
```
Response 200:
{
  "tasks": [
    {
      "name": str,           # "surfacing-sweep" | "google-calendar-sync" | etc.
      "last_run_at": str | null,   # ISO8601 or null if never run
      "status": "ok" | "stale" | "unknown"
    }
  ],
  "counts": {
    "commitments": int,
    "candidates": int,
    "events": int,
    "sources": int,
    "digests_sent": int,
    "surfaced_main": int,
    "surfaced_shortlist": int
  },
  "error_count_24h": int    # candidates with model_classification='error' in last 24h
}
```
Note: Celery does not expose "last run time" in Redis by default. Implementation option: read the `last_sent_at` / `updated_at` proxies from the DB (e.g., latest `DigestLog.sent_at`, latest `SurfacingAudit.created_at`, latest `Event.updated_at` for calendar sync). For MVP this is a good-enough proxy. See Risk Flags below.

**`GET /admin/commitments`**
```
Query params:
  lifecycle_state: str | None
  surfaced_as: str | None          # "main" | "shortlist" | "clarifications"
  delivery_state: str | None
  counterparty_type: str | None
  source_type: str | None          # derived from candidate.source_type
  created_after: datetime | None   # ISO8601
  created_before: datetime | None
  sort: "priority_score" | "created_at" | "resolved_deadline"  # default: priority_score
  limit: int = 50 (max 200)
  offset: int = 0

Response 200:
{
  "items": [AdminCommitmentRow],
  "total": int
}

AdminCommitmentRow:
{
  "id": str,
  "title": str,
  "description": str | null,
  "lifecycle_state": str,
  "surfaced_as": str | null,
  "priority_score": float | null,
  "counterparty_type": str | null,
  "delivery_state": str | null,
  "resolved_deadline": str | null,
  "created_at": str,
  "updated_at": str
}
```

**`GET /admin/commitments/{id}`**
```
Response 200:
{
  "commitment": <all ORM fields as dict>,
  "linked_events": [
    {
      "link_id": str,
      "event_id": str,
      "relationship": str,
      "confidence": float | null,
      "event_title": str,
      "event_starts_at": str,
      "event_status": str
    }
  ],
  "lifecycle_transitions": [
    {
      "id": str,
      "from_state": str | null,
      "to_state": str,
      "trigger_reason": str | null,
      "created_at": str
    }
  ],
  "surfacing_audit": [
    {
      "id": int,
      "old_surfaced_as": str | null,
      "new_surfaced_as": str | null,
      "priority_score": float | null,
      "reason": str | null,
      "created_at": str
    }
  ],
  "source_snippet": str | null,    # first 500 chars of SourceItem.content
  "candidate": {                   # via CandidateCommitment junction table
    "id": str,
    "trigger_class": str | null,
    "model_classification": str | null,
    "model_confidence": float | null,
    "model_explanation": str | null,
    "detection_method": str | null
  } | null
}
```
Source: `SourceItem` is found by loading the candidate's `originating_item_id` via `CandidateCommitment` → `CommitmentCandidate` → `originating_item_id`.

**`GET /admin/candidates`**
```
Query params:
  trigger_class: str | None
  model_classification: str | None    # "commitment" | "not_commitment" | "error" | "ambiguous"
  created_after: datetime | None
  limit: int = 50 (max 200)
  offset: int = 0

Response 200:
{
  "items": [AdminCandidateRow],
  "total": int
}

AdminCandidateRow:
{
  "id": str,
  "raw_text_snippet": str | null,    # first 200 chars
  "trigger_class": str | null,
  "model_classification": str | null,
  "model_confidence": float | null,
  "was_promoted": bool,
  "was_discarded": bool,
  "source_type": str | null,
  "created_at": str
}
```

**`GET /admin/candidates/{id}`**
```
Response 200: full CommitmentCandidate row as dict + context_window JSONB
```

**`GET /admin/surfacing-audit`**
```
Query params:
  commitment_id: str | None
  created_after: datetime | None
  old_surfaced_as: str | None
  new_surfaced_as: str | None
  limit: int = 50 (max 200)
  offset: int = 0

Response 200:
{
  "items": [
    {
      "id": int,
      "commitment_id": str,
      "commitment_title_snippet": str,   # first 80 chars of commitment.title
      "old_surfaced_as": str | null,
      "new_surfaced_as": str | null,
      "priority_score": float | null,
      "reason": str | null,
      "created_at": str
    }
  ],
  "total": int
}
```

**`GET /admin/events`**
```
Query params:
  event_type: str | None    # "explicit" | "implicit"
  status: str | None        # "confirmed" | "cancelled" | "tentative"
  starts_after: datetime | None
  starts_before: datetime | None
  limit: int = 50 (max 200)
  offset: int = 0

Response 200:
{
  "items": [
    {
      "id": str,
      "title": str,
      "event_type": str,
      "status": str,
      "starts_at": str,
      "ends_at": str | null,
      "linked_commitment_count": int
    }
  ],
  "total": int
}
```

**`GET /admin/events/{id}`**
```
Response 200:
{
  "event": <full Event row as dict>,
  "linked_commitments": [
    {
      "commitment_id": str,
      "commitment_title": str,
      "relationship": str,
      "confidence": float | null,
      "lifecycle_state": str,
      "surfaced_as": str | null
    }
  ]
}
```

**`GET /admin/digests`**
```
Query params:
  limit: int = 50 (max 200)
  offset: int = 0

Response 200:
{
  "items": [
    {
      "id": str,
      "sent_at": str,
      "commitment_count": int,
      "delivery_method": str,
      "status": str,
      "error_message": str | null
    }
  ],
  "total": int
}
```

**`GET /admin/digests/{id}`**
```
Response 200: full DigestLog row as dict, including digest_content JSONB
```

**`POST /admin/pipeline/run-surfacing`**
```
Request: {} (no body)
Response 200:
{
  "commitments_scored": int,
  "surfaced_to_main": int,
  "surfaced_to_shortlist": int,
  "duration_ms": int
}
```

**`POST /admin/pipeline/run-linker`**
```
Request: {} (no body)
Response 200:
{
  "linked": int,
  "created_implicit": int,
  "duration_ms": int
}
```

**`POST /admin/pipeline/run-nudge`**
```
Request: {} (no body)
Response 200:
{
  "nudged": int,
  "duration_ms": int
}
```

**`POST /admin/pipeline/run-digest-preview`**
```
Request: {} (no body)
Response 200:
{
  "main": [{"id": str, "title": str, "deadline": str | null}],
  "shortlist": [{"id": str, "title": str, "deadline": str | null}],
  "clarifications": [{"id": str, "title": str}],
  "commitment_count": int,
  "subject": str,
  "duration_ms": int
}
```
Note: builds digest without delivering it — calls `DigestAggregator` and `DigestFormatter` but not `DigestDelivery`.

**`POST /admin/pipeline/run-post-event-resolver`**
```
Request: {} (no body)
Response 200:
{
  "processed": int,
  "escalated": int,
  "duration_ms": int
}
```

**`POST /admin/test/seed-commitment`**
```
Request body:
{
  "description": str,
  "lifecycle_state": str | null,      # default: "active"
  "resolved_deadline": str | null,    # ISO8601 datetime
  "counterparty_type": str | null,
  "source_type": str | null           # "email" | "slack" | "meeting", default: "email"
}

Response 201:
{
  "commitment_id": str,
  "user_id": str,
  "source_id": str,
  "source_item_id": str,
  "candidate_id": str
}
```
Creates full chain: User (if no user for `digest_to_email`) → Source (label = "admin-test-seed") → SourceItem → CommitmentCandidate (was_promoted=True) → Commitment → CandidateCommitment link.

**`DELETE /admin/test/cleanup`**
```
Request body:
{
  "confirm": "delete-test-data"
}

Response 200:
{
  "deleted_commitments": int,
  "deleted_candidates": int,
  "deleted_source_items": int,
  "deleted_sources": int
}
```
Identifies seed rows by `Source.display_name = "admin-test-seed"`. Cascades via FK ON DELETE CASCADE.

**`PATCH /admin/commitments/{id}/state`**
```
Request body:
{
  "lifecycle_state": str | null,
  "delivery_state": str | null,
  "reason": str                  # required
}

Response 200: AdminCommitmentRow (full commitment fields)

Side effect: writes SurfacingAudit row:
  reason = f"admin-override: {reason}"
  old_surfaced_as = commitment.surfaced_as
  new_surfaced_as = commitment.surfaced_as  (unchanged — this is a state override, not surfacing)
  priority_score = commitment.priority_score
```
Note: `lifecycle_state` override bypasses the `VALID_TRANSITIONS` guard that user routes enforce. Admin has full authority to set any state.

---

## Frontend Architecture

### Directory Structure (`frontend-admin/`)

```
frontend-admin/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
└── src/
    ├── main.tsx                   # entry point, sets base "/admin/"
    ├── App.tsx                    # router + auth gate
    ├── index.css                  # Tailwind base
    ├── lib/
    │   ├── apiClient.ts           # axios/fetch wrapper, injects X-Admin-Key header
    │   └── auth.ts                # localStorage key read/write, useAdminKey hook
    ├── api/
    │   ├── health.ts              # GET /admin/health
    │   ├── commitments.ts         # GET /admin/commitments, /admin/commitments/:id, PATCH state
    │   ├── candidates.ts          # GET /admin/candidates, /admin/candidates/:id
    │   ├── surfacing.ts           # GET /admin/surfacing-audit
    │   ├── events.ts              # GET /admin/events, /admin/events/:id
    │   ├── digests.ts             # GET /admin/digests, /admin/digests/:id
    │   └── pipeline.ts            # POST /admin/pipeline/*, /admin/test/*
    ├── components/
    │   ├── Layout.tsx             # top nav with tab links + auth indicator
    │   ├── TabNav.tsx             # tab navigation bar
    │   ├── AuthGate.tsx           # login screen (key input)
    │   ├── StatusBadge.tsx        # colored lifecycle_state / delivery_state badges
    │   ├── Pagination.tsx         # shared limit/offset pagination
    │   ├── JsonViewer.tsx         # pretty-prints JSONB fields
    │   └── ConfirmModal.tsx       # destructive action confirmation dialog
    └── pages/
        ├── HealthPage.tsx
        ├── CommitmentsPage.tsx
        ├── CommitmentDetailPanel.tsx
        ├── CandidatesPage.tsx
        ├── CandidateDetailPanel.tsx
        ├── EventsPage.tsx
        ├── SurfacingPage.tsx
        ├── DigestsPage.tsx
        └── PipelinePage.tsx
```

### Component Tree Per Tab

**Health** (`/admin/`)
```
HealthPage
├── TaskStatusCard × 8 (one per Celery beat task)
│   └── last_run_at, status indicator dot, staleness label
├── CountTileGrid
│   └── CountTile × 7 (commitments, candidates, events, sources, digests, surfaced_main, surfaced_shortlist)
└── ErrorHighlight (error_count_24h with red badge if > 0)
```

**Commitments** (`/admin/commitments`)
```
CommitmentsPage
├── FilterBar
│   ├── lifecycle_state dropdown
│   ├── surfaced_as dropdown
│   ├── delivery_state dropdown
│   ├── counterparty_type dropdown
│   └── date range inputs
├── CommitmentsTable (sortable columns)
│   └── CommitmentRow (click → CommitmentDetailPanel)
├── CommitmentDetailPanel (slide-in, right side)
│   ├── FieldGrid (all commitment fields)
│   ├── LinkedEventsSection
│   ├── LifecycleTimeline (transitions chronologically)
│   ├── SurfacingAuditSection
│   ├── SourceSnippetBox
│   └── StateOverrideForm
└── Pagination
```

**Candidates** (`/admin/candidates`)
```
CandidatesPage
├── FilterBar (trigger_class, model_classification, created_after)
├── CandidatesTable
│   └── CandidateRow (confidence as progress bar, click → CandidateDetailPanel)
├── CandidateDetailPanel
│   ├── FieldGrid (all candidate fields)
│   └── JsonViewer (context_window)
└── Pagination
```

**Events** (`/admin/events`)
```
EventsPage
├── FilterBar (event_type, status, date range)
├── EventsTable
│   └── EventRow (type badge, status badge, linked count)
└── Pagination
```

**Surfacing** (`/admin/surfacing`)
```
SurfacingPage
├── FilterBar (commitment_id input, date range, old/new surfaced_as)
├── AuditTable
│   └── AuditRow (arrows: old→new, reason, priority score)
└── Pagination
```

**Digests** (`/admin/digests`)
```
DigestsPage
├── DigestsTable
│   └── DigestRow (click → DigestDetailPanel)
└── DigestDetailPanel
    └── JsonViewer (digest_content with main/shortlist/clarifications lists)
```

**Pipeline** (`/admin/pipeline`)
```
PipelinePage
├── TriggerSection × 5 (one per pipeline endpoint)
│   ├── TriggerButton (with loading spinner)
│   └── LastResultBox (counts + duration_ms, shown after trigger)
└── TestDataSection
    ├── SeedCommitmentForm
    └── CleanupButton → ConfirmModal
```

### API Key Auth Client-Side

```typescript
// lib/auth.ts
const STORAGE_KEY = "rippled_admin_key"
export const getAdminKey = () => localStorage.getItem(STORAGE_KEY) ?? ""
export const setAdminKey = (key: string) => localStorage.setItem(STORAGE_KEY, key)
export const clearAdminKey = () => localStorage.removeItem(STORAGE_KEY)

// lib/apiClient.ts
const BASE_URL = import.meta.env.VITE_API_URL ?? ""

export async function adminFetch(path: string, options: RequestInit = {}) {
  const key = getAdminKey()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": key,
      ...(options.headers ?? {}),
    },
  })
  if (res.status === 401) throw new Error("invalid_key")
  if (res.status === 503) throw new Error("admin_not_configured")
  if (!res.ok) throw new Error(`http_${res.status}`)
  return res.json()
}
```

`AuthGate.tsx`: renders a centered login form if `getAdminKey()` returns empty string or if any query returns `"invalid_key"`. On submit, stores the entered key and invalidates all queries.

The key indicator in `Layout.tsx` top-right: green dot if last request succeeded, red dot if last response was 401. Uses a lightweight context atom (no Zustand needed).

### Vite Config (`frontend-admin/vite.config.ts`)

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/admin/',         // CRITICAL: all asset paths include /admin/ prefix
  build: {
    outDir: '../api/public-admin',
    emptyOutDir: true,
  },
})
```

`base: '/admin/'` ensures that Vite generates:
- `<script src="/admin/assets/index-HASH.js">`
- `<link href="/admin/assets/index-HASH.css">`

Without this, assets would be served from `/assets/` and collide with the user frontend's assets mount.

### `package.json` (`frontend-admin/package.json`)

Separate `package.json` — same packages as `frontend/package.json` but without `@supabase/supabase-js`. Exact same version pins for React, TanStack Query v5, React Router v6, TailwindCSS 3.x, Vite 5.x.

---

## SPA Fallback Integration with `app/main.py`

This is the highest-complexity change in C4. The current `app/main.py` ends with a catch-all:

```python
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    index = os.path.join(_PUBLIC_DIR, "index.html")
    return FileResponse(index)
```

This route catches **every GET request** that doesn't match an earlier route. FastAPI matches routes in registration order. The admin SPA fallback must be inserted correctly.

**Required order after changes:**

```python
# 1. API routers (registered first — always win over static/SPA)
app.include_router(sources.router, ...)
# ... all existing routers ...
app.include_router(admin_router, prefix=settings.api_prefix, ...)  # NEW

# 2. User static assets
if os.path.isdir(_PUBLIC_DIR):
    app.mount("/assets", StaticFiles(directory=...), name="assets")

# 3. Admin static assets  (NEW)
_ADMIN_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "api", "public-admin")
if os.path.isdir(_ADMIN_PUBLIC_DIR):
    app.mount(
        "/admin/assets",
        StaticFiles(directory=os.path.join(_ADMIN_PUBLIC_DIR, "assets")),
        name="admin-assets",
    )

    # 4. Admin SPA fallback — must come BEFORE the user catch-all (NEW)
    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{full_path:path}", include_in_schema=False)
    async def admin_spa_fallback(full_path: str = "") -> FileResponse:
        index = os.path.join(_ADMIN_PUBLIC_DIR, "index.html")
        return FileResponse(index)

# 5. User SPA fallback — catch-all, last resort (EXISTING, unchanged)
if os.path.isdir(_PUBLIC_DIR):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        index = os.path.join(_PUBLIC_DIR, "index.html")
        return FileResponse(index)
```

**Key insight:** FastAPI route matching is first-match. The admin API routes under `/api/v1/admin/` are registered as an `APIRouter` prefix — they will never hit the SPA fallbacks because `/api/v1/admin/...` doesn't start with `/admin`. The admin SPA fallback `@app.get("/admin/{full_path:path}")` only matches `/admin/*` GET requests, which is exactly what the admin React Router needs for client-side navigation. User frontend routes (e.g., `/review`, `/log`) never start with `/admin` so they correctly fall through to the user catch-all.

**The `api/public-admin/` directory must exist** (even empty) for the mount to succeed. Create it with a `.gitkeep` in the initial commit; the built files are committed on top.

---

## Pipeline Trigger Endpoints: Synchronous Service Calls Without Celery

All five services that pipeline triggers call (`run_surfacing_sweep`, `DeadlineEventLinker`, `NudgeService`, `PostEventResolver`, `DigestAggregator`) are **synchronous** — they take a `Session` (not `AsyncSession`). The admin router is an async FastAPI handler that gets an `AsyncSession` via `get_db`.

**Problem:** Calling synchronous blocking code inside an async FastAPI handler blocks the event loop. With a `run_in_threadpool` approach, we use a sync session factory (`get_sync_session`) inside a thread pool thread — the same pattern the Celery tasks use.

**Recommended approach — `run_in_threadpool` + `get_sync_session`:**

```python
from starlette.concurrency import run_in_threadpool
from app.db.session import get_sync_session

@router.post("/pipeline/run-surfacing")
async def trigger_surfacing():
    import time
    from app.services.surfacing_runner import run_surfacing_sweep

    start = time.monotonic()

    def _run():
        with get_sync_session() as db:
            result = run_surfacing_sweep(db)
        return result

    result = await run_in_threadpool(_run)
    duration_ms = int((time.monotonic() - start) * 1000)

    return {
        "commitments_scored": result["evaluated"],
        "surfaced_to_main": sum(1 for ... ),  # derive from result
        "surfaced_to_shortlist": ...,
        "duration_ms": duration_ms,
    }
```

`run_in_threadpool` is from `starlette.concurrency` (already a transitive dependency of FastAPI). It runs the callable in the default executor (a thread pool), yielding back to the event loop while the sync work runs. This is the idiomatic FastAPI pattern for calling sync-only code.

**What needs adjustment in the services for admin triggers:**

- `run_surfacing_sweep(db)` returns `{evaluated, changed, surfaced, held}` — not a breakdown of main vs shortlist. The admin endpoint needs to query counts AFTER the sweep, or we return the changed count. **Decision: return `{commitments_scored: evaluated, changed: changed, duration_ms: X}` for simplicity.** The WO's requested `surfaced_to_main` / `surfaced_to_shortlist` would require either (a) modifying the service return value to break down by surface destination, or (b) querying the DB post-sweep. Recommended: extend `run_surfacing_sweep` return value to include `surfaced_main` and `surfaced_shortlist` counts — this is additive and doesn't break existing callers.

- `NudgeService.run(db, commitment_event_pairs=...)` requires the commitment-event pairs to be pre-loaded (as the task does). The admin endpoint should replicate the Celery task's query logic inline (or extract it to a shared helper). This is ~15 lines of query code from `tasks.py` — copy it into the admin handler function.

- `PostEventResolver.run(db, commitment_event_pairs=..., source_item_map=...)` — same: replicate the query logic from the Celery task.

- `DeadlineEventLinker.run(db, user_id=None, commitments=..., events=..., existing_link_ids=...)` — same query pattern.

**One adjustment that IS needed:** `DeadlineEventLinker.run()` currently takes `user_id` as a parameter and passes it to `_make_implicit_event` — but looking at the code, `_make_implicit_event` does NOT use `user_id` (it creates an `Event` with no user FK). The `user_id=None` call pattern is already used in `surfacing_runner.py`. No change needed.

---

## Open Questions with Recommended Answers

### OQ1: How to handle synchronous pipeline runs without conflicting with async Celery tasks?

**Risk:** Admin triggers a surfacing sweep manually at the same moment the Celery beat fires the 30-minute sweep. Both run concurrently with separate sessions. This could produce double SurfacingAudit rows for the same commitment transitions.

**Recommended answer: Accept the race for MVP, document it, mitigate with idempotency observation.**

The `run_surfacing_sweep` service writes a SurfacingAudit row only if `new_surface != old_surface`. In a race, both sweeps read the same `surfaced_as` value before either commits, then both write an audit row for the same transition. Result: duplicate audit entries, no data corruption. Commitments are not double-counted; scores are just recomputed twice.

**No explicit locking needed for MVP.** The likelihood of the race (admin trigger overlapping with a beat fire within the same 30-min window) is low. The admin UI should label pipeline triggers clearly: "Manual trigger — avoid running while Celery beat is active."

A production solution would use Redis-based advisory locks (same Redis instance that Celery uses). That's Phase C5+ scope.

### OQ2: How to structure the frontend-admin build/commit pattern?

**Recommended answer: Exact mirror of the existing `frontend/` pattern.**

- Source in `frontend-admin/` (parallel to `frontend/`)
- Build output to `frontend-admin/dist/` (via Vite `outDir`)
- Copy/commit built artifacts to `api/public-admin/` (same as `api/public/` for user frontend)
- Build command: `cd frontend-admin && npm run build` → writes directly to `../api/public-admin/`
- Committed to repo: the `api/public-admin/` directory with `index.html` + `assets/`
- The `frontend-admin/dist/` directory is `.gitignore`d (it's the intermediate build directory); `api/public-admin/` is committed (it's what the server serves)

Wait — looking more carefully at the user frontend's `vite.config.ts`:
```
build: { outDir: '../api/public', emptyOutDir: true }
```

The build writes DIRECTLY to `api/public/`. There is no separate `dist/` directory and no copy step. The admin frontend should do the same: `outDir: '../api/public-admin'`. No copy step needed.

### OQ3: Separate `package.json` or monorepo approach?

**Recommended answer: Separate `package.json` (not monorepo).**

The existing `frontend/` is already a standalone package with its own `node_modules`. Adding workspace configuration to the repo root would require a root `package.json`, touching `.gitignore`, potentially touching CI — more blast radius than needed.

Separate `package.json` in `frontend-admin/` with same dependency versions as `frontend/`. Run `npm install` once. No linking or shared dependencies needed — both apps are small and the duplication is 30MB of identical `node_modules` (acceptable).

**One exception:** `tailwindcss` version must match exactly between the two packages if we ever want to share CSS utilities. Pin the same version: `tailwindcss: ^3.4.1`.

### OQ4: Should `GET /admin/health` approximate Celery task health from DB proxies?

**Recommended answer: Yes, DB-proxy approach for MVP.**

Celery does not expose "last run time" via its broker without querying result backend or using Flower. For MVP, derive task health from DB activity proxies:

| Celery task | DB proxy for "last run" |
|-------------|-------------------------|
| `surfacing-sweep` | `MAX(surfacing_audit.created_at)` |
| `google-calendar-sync` | `MAX(events.updated_at) WHERE event_type='explicit'` |
| `pre-event-nudge` | `MAX(surfacing_audit.created_at) WHERE reason LIKE 'nudge:%'` |
| `post-event-resolution` | `MAX(surfacing_audit.created_at) WHERE reason LIKE 'post-event:%'` |
| `daily-digest` | `MAX(digest_log.sent_at)` |
| `clarification-sweep` | `MAX(commitment_candidates.updated_at) WHERE was_promoted=true OR was_discarded=true` (approx) |
| `completion-sweep` | `MAX(lifecycle_transitions.created_at) WHERE trigger_reason='auto_close'` |
| `model-detection-sweep` | `MAX(commitment_candidates.model_called_at)` |

"Stale" = last proxy timestamp > 2× the expected schedule interval. Display as amber if stale, red if last proxy is > 24h old (task may be down), green if within expected window.

This is imprecise but useful for operator triage during testing.

---

## Risk Flags

### Risk 1: SPA fallback ordering — HIGH priority

**The catch-all `/{full_path:path}` currently in `main.py` is defined as a route handler, not a middleware.** FastAPI evaluates route handlers in registration order. If the admin router is registered after the existing routes but before adding the admin SPA fallback route, AND the catch-all is redefined after the admin fallback — all is well. But if the refactoring is done carelessly and the user catch-all is defined before the admin fallback, `/admin/commitments` will serve the user `index.html`.

**Mitigation:** The current `main.py` wraps both the static mount AND the catch-all in `if os.path.isdir(_PUBLIC_DIR)`. The admin section should be similarly wrapped in `if os.path.isdir(_ADMIN_PUBLIC_DIR)`. The admin block must appear BEFORE the user catch-all block. Enforce this with a comment in the code: `# IMPORTANT: admin SPA fallback must precede user SPA catch-all`.

Test coverage must include: `GET /admin/pipeline` returns 200 with admin index.html content, NOT the user index.html.

### Risk 2: `StaticFiles` mount for `/admin/assets` collides with user `/assets` — MEDIUM

The user frontend is mounted at `/assets`. The admin frontend needs `/admin/assets`. FastAPI's `app.mount()` uses prefix matching. `/admin/assets` and `/assets` are different prefixes — no collision. However, both StaticFiles mounts are named: `name="assets"` and `name="admin-assets"`. Using the same name would cause a silent collision in FastAPI's internal routing. Use distinct names.

### Risk 3: `api/public-admin/` does not exist at server startup — LOW

If `api/public-admin/` doesn't exist, `os.path.isdir(_ADMIN_PUBLIC_DIR)` returns False and the admin static serving is silently skipped. This is the same guard as the user frontend — it means the admin UI simply won't be served in local dev until the admin frontend is built once. Document in `CONTRIBUTING.md` (or build notes): run `cd frontend-admin && npm install && npm run build` before the admin UI is accessible.

The `api/public-admin/` directory should be committed (even empty, with `.gitkeep`) so the directory exists in fresh clones. The built files override `.gitkeep`.

### Risk 4: `run_surfacing_sweep` return value doesn't break down by surface destination — LOW

`run_surfacing_sweep` returns `{evaluated, changed, surfaced, held}`. The WO requests `{commitments_scored, surfaced_to_main, surfaced_to_shortlist, duration_ms}`. Extending the return value requires adding ~10 lines to `surfacing_runner.py`. This is additive and doesn't break any existing caller. However it does touch a tested service. **The test for `run_surfacing_sweep` must be updated to check the new keys.**

### Risk 5: Admin state override bypasses `VALID_TRANSITIONS` — DELIBERATE, document clearly

The user-facing `PATCH /commitments/{id}` enforces state machine transitions. The admin override endpoint intentionally skips this. This means an admin can set a commitment from `discarded` to `active` — which is normally forbidden. This is by design (admin = escape hatch). The SurfacingAudit log provides the audit trail. Document this in code comments and in the UI ("This bypasses lifecycle validation").

### Risk 6: `LifecycleTransition` table requires `user_id` — MEDIUM

Looking at `orm.py`: `LifecycleTransition.user_id` is `NOT NULL` (no nullable=True). The admin override endpoint bypasses the per-user auth system. We need a `user_id` to write to `LifecycleTransition`. Options:
- (A) Don't write a `LifecycleTransition` row from admin override — only write `SurfacingAudit`
- (B) Use the commitment's existing `user_id` as the transition's `user_id` with `trigger_reason="admin-override"`
- (C) Create a synthetic "admin" user

**Recommended: Option B.** The commitment already has a `user_id`. For the state override, write a `LifecycleTransition` with `commitment.user_id`, `trigger_reason=f"admin-override: {reason}"`. This satisfies the NOT NULL constraint and keeps the audit trail complete without synthetic users.

### Risk 7: `NudgeService` and `PostEventResolver` require pre-loaded commitment-event pairs

The admin trigger endpoints must replicate the query logic from `tasks.py` that prepares the `commitment_event_pairs` list. This is ~20 lines of SQLAlchemy per endpoint. The query logic lives in `tasks.py` as inline code (not abstracted into a helper). For admin triggers, the query runs inside the `run_in_threadpool` callable using `get_sync_session()` — same as the task.

**Recommendation: Extract the query logic into helper functions in `app/services/nudge.py` and `app/services/post_event_resolver.py`**, e.g. `NudgeService.load_pairs(db, now) -> list` and `PostEventResolver.load_pairs(db, now) -> tuple[list, dict]`. The Celery tasks call these helpers (refactor). The admin endpoints call them too. This reduces duplication and makes the services more testable.

---

## Estimated Test Count and Breakdown

### Unit Tests

| Test class | Count | Coverage |
|------------|-------|----------|
| `TestAdminAuthMiddleware` | 4 | valid key → 200; invalid key → 401; missing header → 422; empty `admin_secret_key` config → 503 |
| `TestAdminCommitmentsFilter` | 8 | each filter param independently (lifecycle_state, surfaced_as, delivery_state, counterparty_type, created_after, created_before, sort, limit/offset) |
| `TestAdminCandidatesFilter` | 3 | trigger_class filter, model_classification filter, pagination |
| `TestAdminSurfacingAuditFilter` | 3 | commitment_id filter, created_after filter, old/new surfaced_as filter |
| `TestAdminEventsFilter` | 3 | event_type filter, status filter, date range filter |
| `TestPipelineTriggerSurfacing` | 2 | calls `run_surfacing_sweep`, returns correct shape; handles service exception gracefully |
| `TestPipelineTriggerLinker` | 2 | calls `DeadlineEventLinker.run`, returns `linked`/`created_implicit` |
| `TestPipelineTriggerNudge` | 2 | calls `NudgeService.run`, returns `nudged` |
| `TestPipelineTriggerDigestPreview` | 2 | builds digest content without calling `DigestDelivery`, returns full shape |
| `TestPipelineTriggerPostEventResolver` | 2 | calls `PostEventResolver.run`, returns `processed`/`escalated` |
| `TestAdminTestSeed` | 4 | creates full row chain, correct source.display_name label, returns all IDs, idempotent (second seed creates second set) |
| `TestAdminTestCleanup` | 3 | deletes only seed rows (not real data), wrong confirm body → 422, logs counts |
| `TestAdminStateOverride` | 4 | lifecycle_state override bypasses transitions, delivery_state override, writes SurfacingAudit with "admin-override:" reason, writes LifecycleTransition with user's user_id |
| **Unit subtotal** | **42** | |

### Integration Tests

| Test class | Count | Coverage |
|------------|-------|----------|
| `TestAdminHealthIntegration` | 2 | `GET /admin/health` returns expected shape; counts match DB state |
| `TestAdminCommitmentsIntegration` | 4 | list with real data; detail with linked events, transitions, audit, source snippet, candidate; state override updates DB; filter returns correct subset |
| `TestAdminCandidatesIntegration` | 2 | list returns candidates; detail includes context_window |
| `TestAdminSurfacingAuditIntegration` | 2 | list with real audit rows; filter by commitment_id |
| `TestAdminEventsIntegration` | 2 | list returns events with linked_commitment_count; detail includes linked commitments |
| `TestAdminDigestsIntegration` | 2 | list with real digest log rows; detail includes digest_content |
| `TestAdminSeedAndCleanupIntegration` | 3 | seed → verify rows exist → cleanup → verify rows deleted (only seed rows) |
| **Integration subtotal** | **17** | |

### **Total: ~59 new tests** (exceeds 30-test minimum from WO by comfortable margin)

No frontend tests required per WO spec.

---

## Files to Create or Modify

| File | Action | Notes |
|------|--------|-------|
| `app/core/config.py` | MODIFY | Add `admin_secret_key`, `admin_ui_enabled` |
| `app/api/deps/admin_auth.py` | NEW | `verify_admin_key` FastAPI dependency |
| `app/api/routes/admin.py` | NEW | All admin endpoints |
| `app/main.py` | MODIFY | Register admin router; add admin static mount + SPA fallback BEFORE user catch-all |
| `app/services/surfacing_runner.py` | MODIFY | Extend return value with `surfaced_main`, `surfaced_shortlist` |
| `app/services/nudge.py` | MODIFY | Extract `load_pairs(db, now)` helper |
| `app/services/post_event_resolver.py` | MODIFY | Extract `load_pairs(db, now)` helper |
| `api/public-admin/.gitkeep` | NEW | Ensure directory exists in repo; replaced by build artifacts on first build |
| `frontend-admin/package.json` | NEW | Separate package, same deps as user frontend minus Supabase |
| `frontend-admin/vite.config.ts` | NEW | `base: '/admin/'`, `outDir: '../api/public-admin'` |
| `frontend-admin/tailwind.config.ts` | NEW | Same config as user frontend |
| `frontend-admin/tsconfig.json` | NEW | Same as user frontend |
| `frontend-admin/index.html` | NEW | Vite entry HTML |
| `frontend-admin/src/` | NEW (full tree) | See directory structure above |
| `tests/test_admin_api.py` | NEW | All unit + integration tests |

---

## Environment Variables to Document

The following must be set in Railway (production) and `.env` (local dev) for the admin UI to work:

```
ADMIN_SECRET_KEY=<strong-random-key>   # Required — admin API returns 503 if empty
ADMIN_UI_ENABLED=true                  # Optional — defaults to true
```

`VITE_API_URL` is set at frontend build time. For production: `VITE_API_URL=https://api.rippled.ai`. For local dev: `VITE_API_URL=http://localhost:8000`.

---

## Summary

Phase C4 is a medium-complexity phase with one genuinely tricky problem (SPA fallback ordering) and one nuanced design decision (sync services from async handlers). Everything else follows established patterns.

The three decisions that matter most:

1. **SPA fallback ordering** — admin fallback BEFORE user catch-all. The current code will intercept admin routes with the user frontend if this is done wrong. Enforce with tests.

2. **`run_in_threadpool` for pipeline triggers** — don't call sync services directly in async handlers. Use `starlette.concurrency.run_in_threadpool` with `get_sync_session()` inside the callable.

3. **Separate `package.json`, no monorepo** — matches existing pattern, lowest blast radius.

No existing routes, frontend, or tests are modified beyond the small service extensions noted above. All 538 existing tests should continue to pass.
