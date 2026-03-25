# Build Decisions Log

## WO-RIPPLED-CANDIDATE-PROMOTION-BROKEN — Fix Promotion Pipeline
*Date: 2026-03-25 | Owner: Claude (Stage 3)*

**Problem:** 274 commitment_candidates created since launch, 0 ever promoted. Promotion failures were invisible due to silent exception handling and SQL NULL semantics.

**Root causes fixed:**
1. `run_clarification_task` swallowed exceptions silently — generic `except Exception` retried 3x with no logging, then abandoned. Added ERROR-level logging with candidate_id, retry count, and actual exception.
2. Clarification sweep used `observe_until <= now` — NULL values silently excluded from results. Added `observe_until IS NULL` branch to treat missing observation window as expired.
3. No promotion activity logging — sweep ran silently. Added INFO-level log with found/enqueued counts.

**Files changed:**
- `app/tasks.py` — Error logging in task, NULL handling in sweep, activity logging
- `tests/services/test_candidate_promotion.py` — 6 new tests covering all 3 bugs
- `tests/services/test_clarification.py` — Updated stale flush count assertion
- `scripts/backfill_promote_candidates.py` — Backfill script for existing candidates

**Backfill:** `python scripts/backfill_promote_candidates.py` promotes eligible candidates. Idempotent (skips already-promoted). Use `--dry-run` to preview.

---

## WO-RIPPLED-LLM-ORCHESTRATION — Staged Pipeline Architecture
*Date: 2026-03-22 | Owner: Claude (Stage 3)*

**Decision:** Replaced monolithic interpretation step with a staged orchestration pipeline (6 stages) operating on NormalizedSignal objects.

**Architecture:**
- Stage 0: Eligibility check (deterministic — no LLM)
- Stage 1: Candidate gate (cheap model, binary relevance)
- Stage 2: Speech-act classification (cheap model, closed enum)
- Stage 3: Commitment field extraction (LLM, conditional on stages 1-2)
- Stage 4: Deterministic routing decision (code only, no LLM)
- Stage 5: Optional escalation (strong model, only when warranted)
- Stage 6: Persistence and logging (every stage persisted)

**Key design choices:**
- Separate pipeline SpeechAct enum from existing DB SpeechAct (pipeline has `delegation`, `suggestion`, `unclear` not in DB)
- Model routing config externalized (cheap-first by default, escalation uses gpt-4.1)
- All thresholds in code/config, never in prompts (WO 8.4 compliance)
- Markdown fence stripping on all LLM responses (lesson 2026-03-17)
- Replay runner compares 6 key fields between prior and new runs

**New tables:** `signal_processing_runs`, `signal_processing_stage_runs`, `candidate_signal_records`
**New modules:** `app/services/orchestration/` (13 files)
**Tests:** 83 new tests, 0 regressions

---

## WO-RIPPLED-PROMPT-IMPROVEMENT (run-1, duplicate) — Judge Hardening + WO Dedup
*Date: 2026-03-22 | Owner: Claude (Stage 3)*

**Decision:** Hardened judge prompt with actionable suggestion examples and added duplicate WO prevention.

**Rationale:** A second identical WO was generated for the same aud-42 failure because `_create_prompt_improvement_wo` had no duplicate check — it blindly overwrites any existing PENDING file. Additionally, the judge prompt lacked example suggestion formats, resulting in empty "Top Prompt Improvement Suggestions" sections in WOs.

**Changes:**
- `llm_judge.py`: Added PENDING/INPROGRESS existence check before WO creation; added actionable suggestion examples to judge prompt
- `test_llm_judge.py`: 3 new tests (dedup prevention, actionable suggestion format)

---

## WO-RIPPLED-PROMPT-IMPROVEMENT (run-1) — Prompt Positioning
*Date: 2026-03-22 | Owner: Claude (Stage 3)*

**Decision:** Restructured seed detector (seed-v9) and model detection (ongoing-v10) prompts to leverage primacy/recency effect for critical rules.

**Rationale:** Audit aud-42 showed missed "follow up on budget" and false positive "greeting" despite both patterns being explicitly covered in prompts. Root cause: critical rules were positioned mid-prompt where LLMs pay least attention. Solution: move CRITICAL RULE (follow-ups) and ZERO TOLERANCE (greetings) to the very top of both prompts, consolidate duplicated greeting exclusions, keep BEFORE YOU RESPOND self-check at end for recency.

**Changes:**
- `seed_detector.py`: seed-v8 → seed-v9 — CRITICAL RULE + ZERO TOLERANCE moved to top
- `model_detection.py`: ongoing-v9 → ongoing-v10 — same structural repositioning
- Tests updated with version assertions and new structural positioning tests
- `lessons.md` updated with primacy/recency pattern

---

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

---

## WO-RIPPLED-SEED-DEBUG — Seed pass: 178 processed, 0 commitments
*Date: 2026-03-17 | Owner: Trinity*

### D-SEED-DEBUG-01: Root cause — LLM markdown code fences break JSON parser
**Question:** Why did the seed pass process 178 items with 0 commitments and 0 errors?

**Root cause:** The Anthropic LLM wraps its JSON response in markdown code fences (`` ```json ... ``` ``). The `json.loads()` call failed with `JSONDecodeError` on every item. This exception was caught silently (returned `[]`), so items were marked as processed with 0 commitments and 0 errors.

**Fix:**
1. Added `_strip_markdown_json()` helper that strips markdown code fences before parsing.
2. Added debug logging of raw LLM response and parsed commitment count.
3. Seed-reset must be called before re-running since all 178 items now have `seed_processed_at` set.

**Rationale:** This is a common LLM integration issue. Even with "Respond with valid JSON only" in the prompt, LLMs frequently wrap output in code fences. The fix is defensive parsing, not prompt engineering.

### D-SEED-DEBUG-02: Relax detection prompt — "Infer more than you assert"
**Question:** Is the seed pass prompt too conservative, potentially missing legitimate commitments?

**Decision:** Yes. Relaxed the prompt in three ways:
1. Added "Tentative" language category: "I'll try to", "Let me check", "I'll get back to you"
2. Added "Soft promises" category: "I'll see what I can do", "Let me look into it"
3. Added explicit instruction: "Cast a WIDE net" and "When in doubt, INCLUDE it with lower confidence (0.4-0.6)"

**Rationale:** Per product-truth.md: "Infer more than you assert." Better to surface a probable commitment and let the user dismiss it than to miss it entirely. The original prompt excluded tentative language which is common in real email.
