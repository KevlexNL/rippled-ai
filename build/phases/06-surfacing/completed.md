# Phase 06 Completion — Surfacing & Prioritization

*Completed: 2026-03-13*

---

## What Was Built

### New Services

| File | Purpose |
|---|---|
| `app/services/commitment_classifier.py` | Scores commitments on 4 dimensions: timing_strength, business_consequence, cognitive_burden, confidence_for_surfacing. Detects externality, critical ambiguity, and source type via candidate chain traversal. |
| `app/services/priority_scorer.py` | Combines classifier dimensions into a 0–100 score using weighted formula. Includes staleness bonus for overdue commitments. |
| `app/services/observation_window.py` | `is_observable()` / `should_surface_early()` — controls the silent observation window before surfacing. |
| `app/services/surfacing_router.py` | Routes commitments to main / shortlist / clarifications / None based on score + ambiguity. |
| `app/services/surfacing_runner.py` | Batch sweep runner called by the Celery task. Processes all active commitments, updates fields, writes SurfacingAudit rows. |

### Updated Files

| File | Change |
|---|---|
| `app/models/orm.py` | Added `surfaced_as`, `priority_score`, `timing_strength`, `business_consequence`, `cognitive_burden`, `confidence_for_surfacing`, `surfacing_reason` columns + `SurfacingAudit` model. |
| `app/models/schemas.py` | Added Phase 06 fields to `CommitmentRead`. |
| `app/api/routes/surface.py` | Updated to query by `surfaced_as + priority_score DESC`. Added `/surface/internal` endpoint. |
| `app/tasks.py` | Added `recompute_surfacing` Celery task + beat schedule (30 min). Imports `run_surfacing_sweep`. |

### Migrations

| File | Change |
|---|---|
| `migrations/versions/d7e8f9a0b1c2_phase06_surfacing.py` | Adds surfacing columns to `commitments`, creates `surfacing_audit` table, adds composite index. |

### Tests

| File | Count | Coverage |
|---|---|---|
| `tests/services/test_classifier.py` | 27 tests | get_source_type, is_external, timing/consequence/burden/confidence scorers, has_critical_ambiguity, classify() |
| `tests/services/test_surfacing.py` | 28 tests | priority scorer, observation window, surfacing router, surfacing runner |

**Total test count: 255** (up from 200 before Phase 06, +55 new tests)

### Documentation

- `docs/surfacing_architecture.md` — full pipeline overview, DB schema, API endpoints
- `docs/priority_scoring.md` — scoring formula with examples and thresholds

---

## Decisions Made During Implementation

1. **Q1 (is_surfaced vs surfaced_as):** Kept both. `is_surfaced = (surfaced_as IS NOT NULL)` set in `surfacing_runner.py`. Clean-up deferred.

2. **Q2 (source type access):** Added `get_source_type()` helper in classifier. Traverses `candidate_commitments[0].source_item.source.source_type`. Defaults to `email_internal` on any broken link.

3. **Q3 (confidence scale):** `confidence_for_surfacing` stored on 0–1 scale. Scaled ×15 in priority scorer. Matches `Numeric(4,3)` convention used by all other confidence fields.

4. **Q4 (surfacing_audit schema):** Used proposed schema exactly. `BIGINT` auto-increment PK, indexed on `commitment_id` and `created_at`.

5. **Q5 (file paths):** `app/` throughout. No `src/rippled/` references.

6. **Ruff fixes:** Removed unused imports from `surface.py`, `commitment_classifier.py`, `observation_window.py`, and `surfacing_runner.py` flagged by ruff after initial implementation.

---

## Verification

```
255 passed, 1 warning in 0.36s
ruff check app/ → All checks passed!
```

Committed: `feat(phase-06): surfacing & prioritization — classifier, scorer, router, celery sweep, audit`
