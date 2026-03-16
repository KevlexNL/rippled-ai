# Build Decisions Log

## Phase 03 — Detection Pipeline
*Date: 2026-03-10 | Owner: Trinity*

### D-03-01: Schema additions — explicit columns vs single JSONB
**Question:** Add 9 explicit columns to `commitment_candidates`, or use a single `detection_metadata` JSONB?

**Decision:** Hybrid. Explicit columns for all queryable/filterable fields. JSONB for unstructured context.

**Explicit columns added:**
- `trigger_class TEXT` — queried for analytics and downstream filtering
- `is_explicit BOOLEAN` — frequently filtered
- `priority_hint TEXT` — CHECK IN ('high','medium','low') — used in surfacing queries
- `commitment_class_hint TEXT` — CHECK IN ('big_promise','small_commitment','unknown')
- `flag_reanalysis BOOLEAN DEFAULT false` — indexed, used in scheduled re-analysis jobs
- `source_type TEXT` — denormalized from source_item for join-free queries
- `observe_until TIMESTAMPTZ` — queried by observation sweep jobs

**JSONB columns:**
- `context_window JSONB` — stored but not relationally queried
- `linked_entities JSONB` — stored but not relationally queried

**Rationale:** Explicit columns on queryable fields prevent expensive JSONB extractions in hot paths. JSONB for unstructured context data that downstream stages will read as a blob anyway.

---

### D-03-02: Sync SQLAlchemy session for Celery workers
**Question:** Add sync session factory, or run async event loop inside Celery tasks?

**Decision:** Add sync session factory (`create_engine` + `sessionmaker`) in `app/db/session.py`. Two engines: async for FastAPI routes, sync for Celery workers.

**Rationale:** Running an async event loop inside a Celery worker adds complexity and risk (multiple loops, context propagation issues). Sync session is the idiomatic Celery pattern. The overhead is negligible for background tasks.

**Implementation:** `app/db/session.py` exports `get_sync_session()` context manager.

---

### D-03-03: Confidence score calibration
**Question:** Validate the proposed confidence score calibration.

**Decision:** Approve as proposed.

| Signal type | Score range |
|-------------|-------------|
| Explicit match + external context | 0.85 |
| Explicit match (internal) | 0.75 |
| Implicit match | 0.50–0.60 |
| Edge cases ("I'll try", acceptance without clear object) | 0.35–0.45 |

**Rationale:** The `confidence_score` column is `NUMERIC(4,3)` — numeric scores are already committed. These ranges are conservative enough not to overclaim certainty, while still creating a useful gradient for downstream filtering. Can be recalibrated with real data post-MVP.

---

### D-03-04: Model-assisted detection — deferred to post-Phase 03
**Question:** Include model-assisted detection in Phase 03, or deterministic-only?

**Decision:** Deterministic-only for Phase 03. Model assistance deferred to a future phase.

**Rationale:** Brief 8 says "combine deterministic heuristics with model assistance." Brief 7 (MVP Scope) explicitly permits simplification of the scoring layer for MVP. The context_window stored per candidate is purpose-built to enable model calls in a later phase with no schema changes needed. Shipping a solid deterministic baseline first gives us real data to calibrate model calls against.

**Stored for future use:** `context_window` JSONB on every candidate — sufficient for any model-assisted re-analysis phase.

---

### D-03-05: Batch ingestion — one Celery task per source item
**Question:** One `detect_commitments` task per source item, or a single `detect_commitments_batch` task?

**Decision:** Keep one-task-per-item.

**Rationale:** Batch tasks complicate partial failure handling. If one item in a batch of 100 causes the task to crash, the retry re-processes all 100. Per-item isolation means one bad item fails independently. Can be batched later if queue pressure requires it — the API contract doesn't need to change.

---

### D-03-06: observe_until ownership across detection → promotion
**Question:** Detection writes `observe_until` to the candidate. Promotion copies it to the commitment. Is this correct?

**Decision:** Confirmed. Detection writes to candidate; promotion reads from candidate and writes to commitment.

**Edge case:** If the candidate's `observe_until` has already elapsed by promotion time, promotion should recompute a fresh window rather than copy an expired value. Implementation note added to Phase 03 brief.

**Rationale:** Clean separation of concerns. Detection sets intent; promotion enforces it at the time commitment objects are created.

---

## WO-001 — Celery Worker Deployment
*Date: 2026-03-16 | Owner: Trinity*

### D-WO001-01: Worker deployment strategy
**Question:** How to deploy Celery worker as a second Railway service?

**Decision:** Create empty Railway service via CLI (`railway add --service celery-worker`), set env vars to match API service, deploy via `railway up` with a temporary `railway.toml` override for the worker start command.

**Start command:** `celery -A app.tasks worker --beat --loglevel=info`

**Key fix:** `REDIS_URL` on both API and worker services was set to `redis://localhost:6379/0` (default). Changed to Railway's internal Redis URL: `redis://default:<password>@redis.railway.internal:6379`.

**Rationale:** Railway's service model requires each service to have its own deployment. The worker shares the same repo and env vars but runs a different start command. Using `railway up` with a temporary config avoids needing GitHub-linked auto-deploy for the worker.

### D-WO001-02: REDIS_URL was misconfigured on API service
**Question:** Why was the pipeline not processing tasks even with Redis deployed?

**Decision:** Fixed `REDIS_URL` on the API service from `redis://localhost:6379/0` to the Railway internal Redis URL. This was the root cause — the API could enqueue tasks to Redis, but was sending them to a non-existent localhost Redis.

**Rationale:** The `settings.redis_url` default in `app/core/config.py` is `redis://localhost:6379/0`. This was never overridden in Railway env vars with the actual Redis service URL.
