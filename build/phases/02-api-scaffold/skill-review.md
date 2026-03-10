# Phase 02 API Scaffold — Skill Review

**Skills applied:** modern-python, static-analysis (semgrep, conceptual), insecure-defaults, property-based-testing
**Files audited:** `app/api/routes/`, `app/core/`, `app/db/`, `app/tasks.py`, `app/models/schemas.py`
**Date:** 2026-03-10

---

## Issues Found

### CRITICAL

#### C1 — Lifecycle state machine references a non-existent state (`"completed"`)

**Location:** `app/api/routes/commitments.py:22-28`

```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["active", "needs_clarification", "discarded"],
    "active": ["needs_clarification", "completed", "discarded"],  # ← "completed" doesn't exist
    "needs_clarification": ["active", "discarded"],
    "completed": ["discarded"],  # ← this key can never be matched
    "discarded": [],
}
```

The `LifecycleState` enum (and the database schema) defines: `proposed`, `needs_clarification`, `active`, `delivered`, `closed`, `discarded`. There is **no `"completed"` state**.

**Impact:**
1. A commitment in `"active"` state cannot be transitioned to `"delivered"` or `"closed"` — those valid transitions are missing from the map.
2. `VALID_TRANSITIONS["completed"]` is dead code — no commitment can ever have `lifecycle_state == "completed"`.
3. The `delete_commitment` route checks `"discarded" not in VALID_TRANSITIONS.get(current_state, [])`. A `"delivered"` or `"closed"` commitment returns `[]` (not found in map), so `"discarded" not in []` is `True`, and the delete is blocked — but for the wrong reason. Users cannot discard delivered commitments.

**Fix:**
```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["active", "needs_clarification", "discarded"],
    "active": ["needs_clarification", "delivered", "closed", "discarded"],
    "needs_clarification": ["active", "discarded"],
    "delivered": ["closed", "discarded"],
    "closed": ["discarded"],
    "discarded": [],
}
```

#### C2 — Batch ingestion rollback destroys already-successful items

**Location:** `app/api/routes/source_items.py:97-128`

```python
for req_item in body:
    ...
    db.add(item)
    try:
        await db.flush()
        await db.refresh(item)
        results.append({"status": 201, ...})
    except IntegrityError:
        await db.rollback()  # ← rolls back the ENTIRE transaction, not just this item
        results.append({"status": 409, ...})
```

When `IntegrityError` is raised on item N, `await db.rollback()` rolls back the **entire session transaction** — including all previously flushed items (items 1 through N-1) that were reported as `{"status": 201}`. The HTTP 207 response tells the client those items succeeded, but they never persist.

**Impact:** Silent data loss on any batch containing a duplicate. The client is told "201 created" for items it never sees in the DB.

**Fix:** Use nested transactions (savepoints) per item:
```python
for req_item in body:
    try:
        async with db.begin_nested():  # savepoint
            item = _build_item(req_item, user_id)
            db.add(item)
            await db.flush()
            await db.refresh(item)
        results.append({"status": 201, "id": item.id, ...})
        _enqueue_detection(item.id)
    except IntegrityError:
        results.append({"status": 409, "error": "Duplicate", ...})
```

#### C3 — `get_current_user_id` provides no real authentication

**Location:** `app/core/dependencies.py:4-7`

```python
async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header required")
    return x_user_id
```

Any caller can pass `X-User-ID: <any-uuid>` and impersonate any user. There is no JWT verification, no session lookup, no signature check.

**Assessment (insecure-defaults):** This is a **fail-open** pattern for authentication. The header is required (good), but the value is completely unverified. This is appropriate for internal/development use only, and must not reach production without real auth.

**Fix for Phase 3+:** Either:
- Validate a JWT (`Authorization: Bearer <token>`) and extract the `sub` claim as `user_id`
- OR use Supabase Auth JWT middleware and validate against the Supabase JWT secret from `settings.supabase_anon_key`

At minimum, add a UUID format check to prevent obviously malformed IDs from reaching DB queries:
```python
import uuid
async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    try:
        uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID format")
    return x_user_id
```

---

### WARNING

#### W1 — `_enqueue_detection` silently swallows all exceptions

**Location:** `app/api/routes/source_items.py:53-59`

```python
def _enqueue_detection(source_item_id: str) -> None:
    """Fire-and-forget: enqueue detect_commitments task. Silently skips if broker unavailable."""
    try:
        from app.tasks import detect_commitments
        detect_commitments.delay(source_item_id)
    except Exception:
        pass
```

The docstring says "silently skips if broker unavailable" — the intent is correct for resilience. But the bare `except Exception: pass` silently hides all failures including programming errors, import errors, and serialization bugs. These will never appear in logs.

**Fix:** Log at WARNING level at minimum:
```python
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to enqueue detection for source_item %s: %s",
            source_item_id, exc
        )
```

#### W2 — `openai_api_key: str = ""` — empty default causes silent runtime failures

**Location:** `app/core/config.py:20`

```python
openai_api_key: str = ""
```

This is a **fail-open** default from the insecure-defaults perspective: the app starts and accepts ingestion even when the detection dependency (OpenAI) is not configured. Detection tasks will fail at runtime when the Phase 3 detection service calls the API with an empty key. The errors will surface as task failures in Celery, not as startup failures.

**Assessment:** Lower risk now (Phase 03 not implemented), but should be changed before detection goes live. Use `Optional[str] = None` and validate before invoking the API rather than failing with a confusing `AuthenticationError`.

#### W3 — No modern Python tooling configured

**Location:** Project root — no `pyproject.toml` found

The project has no `pyproject.toml`, no `ruff` configuration, no type checker (mypy/ty), no `uv` lock file. This means:
- No consistent code style enforcement
- No static type checking (type annotation bugs only surface at runtime)
- No pinned dependency versions beyond what's in `requirements.txt`/`setup.py` (if they exist)

**Fix:** Add `pyproject.toml` with ruff and ty per the modern-python skill:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "S", "ASYNC"]
ignore = ["S101"]

[tool.ty.environment]
python-version = "3.11"
```

#### W4 — `echo=settings.app_env == "development"` at module load time

**Location:** `app/db/engine.py:17`

```python
engine = create_async_engine(
    _make_async_url(settings.database_url),
    ...
    echo=settings.app_env == "development",
)
```

`settings` is imported at module load time, which means the engine is created eagerly on import. In test environments or CLI scripts that import any route, this will attempt to read config and create a DB engine immediately. Prefer lazy initialization or pass `echo` via an explicit config value.

Minor issue — documents the assumption that `app_env` is always correctly set in deployment.

#### W5 — Surface endpoints hardcode `limit=5` with no pagination

**Location:** `app/api/routes/surface.py:37, 62, 85`

```python
.limit(5)
```

All three surface endpoints (main, shortlist, clarifications) have hardcoded `limit=5` with no `offset` parameter. As the product scales this will be a problem — users may have more than 5 active big promises.

This may be intentional UX design (surface shows top N only). If so, document it as a constraint. If not, add pagination consistent with other endpoints.

---

### INFO

#### I1 — `list_sources` pagination uses inconsistent validation style

**Location:** `app/api/routes/sources.py:43-45`

```python
async def list_sources(
    limit: int = 5,
    offset: int = 0,
    ...
) -> list[SourceRead]:
    if limit > 200:
        limit = 200
```

All other routes use `Query(ge=1, le=200)` for pagination validation. `list_sources` uses a manual cap and has no minimum guard (a caller can pass `limit=0` or `limit=-1`).

**Fix:** Replace with `limit: int = Query(5, ge=1, le=200)`.

#### I2 — `AmbiguityPatch` defined inline in routes file

**Location:** `app/api/routes/commitments.py:260-263`

```python
class AmbiguityPatch(BaseModel):
    is_resolved: bool
    resolved_by_item_id: str | None = None
```

This Pydantic model is defined inside `commitments.py` instead of `schemas.py`. Minor consistency issue — all other schemas are in `schemas.py`, and this pattern makes it harder to reuse.

#### I3 — `delete_source` is a soft-delete with no documentation in API response

**Location:** `app/api/routes/sources.py:99-113`

The DELETE endpoint sets `is_active = False` rather than deleting the row. This is sensible (preserves data lineage), but the API returns `204 No Content` with no indication that the source still exists. Clients might retry creation if they check for the source's existence.

The behavior is correct but should be documented in API docs/comments.

#### I4 — Property-based testing opportunities

Based on the property-based-testing skill analysis, these are high-value PBT candidates for Phase 3 tests:

| Target | Property | Priority |
|---|---|---|
| Lifecycle state machine (`VALID_TRANSITIONS`) | No impossible transition reachable; all valid states coverable | HIGH |
| Confidence scores (0.0–1.0) | Always clamped after create/update; never negative/over 1.0 | HIGH |
| Batch ingestion (1–100 items) | Total `201+409` counts always equals input count; no silent drops | HIGH |
| UUID string inputs to route params | No crash on well-formed UUIDs; 404 on non-existent | MEDIUM |
| Pagination params `(offset, limit)` | Result set is deterministic; order stable; offset+limit coverage | MEDIUM |

The state machine is the highest priority — it has already caused C1 above, and PBT with a state reachability property would have caught it.

---

## What's Already Good

- **All queries are user-scoped.** Every `select` in every route includes `WHERE user_id = :user_id`. No IDOR vulnerabilities found in query patterns — tenant isolation is consistently applied.
- **Async throughout.** All DB calls use `AsyncSession` with `await`, no sync blocking in the request path.
- **`get_db` auto-commits and auto-rolls back** — the dependency handles transaction lifecycle cleanly; routes only need to `flush()`.
- **409 conflict handling on ingestion** — the `IntegrityError` catch on duplicate `(source_id, external_id)` returns a useful 409 with the existing item's ID. Good UX.
- **Enum validation at API boundary** — `SourceType`, `LifecycleState`, `SignalRole`, etc. are all Pydantic enum fields on `Create` schemas, so invalid values are rejected before touching the DB.
- **`_validate_source_ownership` helper** — source ownership check is extracted into a helper, not repeated inline.
- **`Query(ge=1, le=200)` pagination** — properly validated in candidates, commitments, signals, ambiguities routes.
- **`LifecycleTransition` written on every state change** — full audit trail of lifecycle events.
- **`expire_on_commit=False` on session factory** — prevents lazy-load errors on objects accessed after `commit()`.
- **`pool_size=10, max_overflow=20`** — reasonable connection pool settings for a Railway deployment.
- **Celery config: JSON only, UTC, explicit serializers** — secure and predictable task queue configuration.
