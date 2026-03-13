# Phase C1 — Model-Assisted Detection: Interpretation

**Written by:** Claude Code
**Date:** 2026-03-13
**Stage:** STAGE 2 — INTERPRET

---

## What This Phase Does and Why

Phase C1 adds a model-assisted detection layer on top of the existing deterministic pipeline. The deterministic pipeline captures ~85-90% of obvious commitments via regex patterns. The model layer (OpenAI GPT-4.1-mini) handles:
- Implicit commitments ("I'll look into that", "consider it done")
- Ambiguous phrasing that regex misses or over-captures
- Context-dependent signals that benefit from language understanding

The design principle: **deterministic first, model only for the ambiguous zone (0.35–0.75 confidence)**. This keeps cost low and avoids touching high-confidence results.

---

## Proposed Implementation

### Architecture

```
Source item ingested
       ↓
run_detection() [existing deterministic pipeline]
       ↓ candidates created with confidence_score
       ↓
run_model_detection_pass(candidate_id) [new Celery task]
       ↓
HybridDetectionService.classify(candidate)
       ├── confidence >= 0.75 → skip (accept deterministic result)
       ├── confidence < 0.35 → skip (discard deterministic result)
       └── 0.35 <= confidence < 0.75 → call ModelDetectionService
              ↓
         OpenAI API call (gpt-4.1-mini, structured output)
              ↓
         Update candidate: model_confidence, model_classification, model_explanation, model_called_at
         Apply decision rule → may update was_discarded
```

### Key Files to Create/Modify

| File | Action |
|------|--------|
| `app/core/openai_client.py` | NEW — OpenAI client with retry/rate limit handling |
| `app/services/model_detection.py` | NEW — ModelDetectionService |
| `app/services/hybrid_detection.py` | NEW — HybridDetectionService (pre-filter + model call + decision) |
| `app/tasks.py` | MODIFY — add `run_model_detection_pass` and `run_model_detection_batch` tasks |
| `app/models/orm.py` | MODIFY — add 4 model detection columns to CommitmentCandidate |
| `app/models/schemas.py` | MODIFY — extend CommitmentCandidateRead, add detection_method computed field |
| `app/core/config.py` | MODIFY — add OPENAI_MODEL and MODEL_DETECTION_ENABLED settings |
| `migrations/versions/e9f0a1b2c3d4_phase_c1_model_detection.py` | NEW — Alembic migration |
| `tests/services/test_model_detection.py` | NEW — 30+ tests |

**Note on WO discrepancy:** The WO references `app/services/detection.py` but the actual file is `app/services/detection/detector.py`. The hybrid pipeline is implemented as a new `app/services/hybrid_detection.py` (as the WO also permits). The existing detection pipeline stays untouched.

**Note on tasks location:** The WO suggests `app/tasks/model_detection.py` but the existing codebase uses a flat `app/tasks.py`. I will add model detection tasks to the existing `app/tasks.py` to match the established pattern.

### OpenAI Client (`app/core/openai_client.py`)

- Initialize from `settings.openai_api_key`
- Default model: `gpt-4.1-mini` (per `settings.openai_model`)
- Retry: exponential backoff on 429 (tenacity), max 3 retries
- Cost logging: log prompt_tokens + completion_tokens at DEBUG level
- Returns None if `openai_api_key` is empty (graceful degradation)

### ModelDetectionService (`app/services/model_detection.py`)

Structured prompt:
```
You are a commitment classifier for a workplace intelligence system.
Given a communication fragment and its surrounding context, determine if it contains a commitment.
A commitment is a statement where someone is obligating themselves or others to do something.

Return JSON with:
- is_commitment: boolean
- confidence: float 0-1
- explanation: string (1-2 sentences)
- suggested_owner: string or null (who made the commitment)
- suggested_deadline: string or null (ISO date or natural language)
```

Uses OpenAI `response_format={"type": "json_object"}` with a system prompt that enforces the schema. Input: `context_window` JSONB (trigger_text + pre_context + post_context).

### HybridDetectionService (`app/services/hybrid_detection.py`)

```python
AMBIGUOUS_LOWER = Decimal("0.35")
AMBIGUOUS_UPPER = Decimal("0.75")
MODEL_PROMOTE_THRESHOLD = 0.6
MODEL_DEMOTE_THRESHOLD = 0.7
```

Decision logic:
1. If `confidence_score >= 0.75`: return `detection_method="deterministic"`, no model call
2. If `confidence_score < 0.35`: return `detection_method="deterministic"`, no model call
3. `0.35 <= confidence_score < 0.75`: call model
   - Model says commitment, confidence > 0.6 → promote, `detection_method="model-assisted"`
   - Model says not-commitment, confidence > 0.7 → demote (set `was_discarded=True`, `discard_reason="model-overridden"`), `detection_method="model-overridden"`
   - Model uncertain (< thresholds) → keep deterministic result, `detection_method="deterministic"`

### Schema Migration

New columns on `commitment_candidates`:
```sql
model_confidence NUMERIC(4,3) NULLABLE
model_classification VARCHAR(20) NULLABLE  -- 'commitment' | 'not-commitment' | 'uncertain'
model_explanation TEXT NULLABLE
model_called_at TIMESTAMPTZ NULLABLE
```

Migration revision: `e9f0a1b2c3d4`, down_revision: `d7e8f9a0b1c2`

### Celery Tasks (in `app/tasks.py`)

```python
@celery_app.task(name="app.tasks.run_model_detection_pass")
def run_model_detection_pass(candidate_id: str) -> dict

@celery_app.task(name="app.tasks.run_model_detection_batch")
def run_model_detection_batch(limit: int = 50) -> dict
```

Beat schedule: `"model-detection-sweep"` every 600s (10 minutes).

**OpenAI Batch API:** The WO mentions using Batch API for >10 candidates. However, the Batch API has ~24h latency and requires async job polling. For MVP, I recommend **direct synchronous calls** with rate limiting instead. The Batch API adds significant complexity (job IDs, polling tasks, result parsing) that isn't warranted for non-real-time processing. We can add Batch API support in a future phase if cost is a concern. **Recommended answer: skip Batch API for now.**

### API Changes (`CommitmentCandidateRead`)

Add to `CommitmentCandidateRead`:
```python
model_confidence: Decimal | None
model_classification: str | None
model_explanation: str | None
model_called_at: datetime | None
detection_method: str | None  # computed: 'deterministic' | 'model-assisted' | 'model-overridden'
```

`detection_method` is a computed property — derived from model_classification + confidence values, not stored separately (reduces schema drift risk).

**Note on WO Deliverable 6:** The WO says to add `detection_method` to "commitment detail response." However, `detection_method` logically belongs on the **candidate** (which is where detection happens), not the commitment. I will add it to `CommitmentCandidateRead`. If needed on commitments, it can be surfaced via the candidate relationship.

### Config Changes (`app/core/config.py`)

```python
openai_model: str = "gpt-4.1-mini"
model_detection_enabled: bool = True
```

`openai_api_key` already exists in config.

---

## Open Questions with Recommended Answers

### Q1: Batch API vs synchronous calls
**WO says:** Use OpenAI Batch API if >10 candidates.
**Recommendation:** Skip Batch API for C1. Use direct calls with rate limiting. Batch API adds polling complexity and 24h latency. We can add it post-MVP if needed.

### Q2: `detection_method` field location
**WO says:** Add to "commitment detail response."
**Recommendation:** Add to `CommitmentCandidateRead` (candidates endpoint), not `CommitmentRead`. Detection happens at the candidate level. The commitment is a promoted artifact — its detection_method is implicit from the candidate it came from.

### Q3: Tasks file location
**WO says:** `app/tasks/model_detection.py`.
**Recommendation:** Add to existing `app/tasks.py` (flat file). Matches established codebase pattern. Creating a `tasks/` directory would require restructuring imports across the whole app for no benefit.

### Q4: `suggested_owner` / `suggested_deadline` from model
**WO says:** Return these from ModelDetectionService.
**Recommendation:** Store in model_explanation as supplementary info, but don't write them to separate DB columns (the candidate already has `commitment_class_hint` and `linked_entities`). The clarification pipeline (Phase 04) handles owner/deadline resolution. Keeping boundaries clean.

---

## Risk Assessment

- **Regression risk: LOW** — existing detection pipeline untouched. Model layer runs as a separate Celery pass after candidates are created.
- **API cost risk: LOW** — only ambiguous zone (0.35–0.75) triggers model calls. High-confidence results skip.
- **Failure mode: SAFE** — all model calls wrapped in try/except. Failure falls back to deterministic result.
- **No schema breaking changes** — only adding nullable columns.
