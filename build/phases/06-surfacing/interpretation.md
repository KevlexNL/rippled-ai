# Phase 06: Surfacing & Prioritization — Interpretation

*Claude Code's analysis and plan*

---

## Summary Understanding

Phase 06 adds the layer that decides *what to show the user, where, and in what order*. The key deliverables: a `surfaced_as` field routing each commitment to a surface (Main / Shortlist / Clarifications / held internal), a multi-dimensional `priority_score` for ordering, and a Celery sweep that re-evaluates all active commitments on schedule.

---

## Key Findings from Existing Codebase

The `Commitment` model already has several surfacing-related fields that overlap with what the brief wants to add:

| **Already exists** | **Phase 06 adds/extends** |
|---|---|
| `priority_class` (big_promise / small_commitment) | `surfaced_as` (main / shortlist / clarifications / NULL) |
| `context_type` ('internal' / 'external') | `priority_score` DECIMAL 0–100 |
| `is_surfaced` BOOLEAN + `surfaced_at` | `timing_strength`, `business_consequence`, `cognitive_burden` (0–10) |
| `observe_until`, `observation_window_hours` | `confidence_for_surfacing`, `surfacing_reason` |

There is also **already a `surface.py` route file** with `/surface/main`, `/surface/shortlist`, `/surface/clarifications` endpoints — but they currently query by `priority_class + is_surfaced`. Phase 06 will update these to query by `surfaced_as + priority_score`.

---

## Implementation Plan

### 1. Extend Commitment Model

Add missing columns via migration:
- `surfaced_as` VARCHAR(20)
- `priority_score` DECIMAL(5,2)
- `timing_strength` SMALLINT (0–10)
- `business_consequence` SMALLINT (0–10)
- `cognitive_burden` SMALLINT (0–10)
- `confidence_for_surfacing` DECIMAL(5,2) or store on 0–1 scale per convention
- `surfacing_reason` VARCHAR(255)
- Index on `(surfaced_as, priority_score DESC)`

### 2. Classification Service

File: `app/services/commitment_classifier.py`

- Detect externality from participants + source metadata
- Score timing strength (explicit date/time vs vague)
- Score business consequence (heuristic: external > internal, derived from evidence count)
- Score cognitive burden (based on language markers and size)
- Score surfacing confidence (owner + deliverable confidence)
- Classify as "big promise" or "small commitment"

### 3. Priority Scoring

File: `app/services/priority_scorer.py`

Combine dimensions into 0–100 score:
- Externality: +25 if external
- Timing: 0–20 (from timing_strength 0–10)
- Consequence: 0–15 (from business_consequence 0–10)
- Cognitive burden: 0–15 (from cognitive_burden 0–10)
- Confidence: 0–15, with asymmetric suppression for low values
- Staleness: +0–10 bonus for unresolved past observation window

### 4. Observation Window Logic

File: `app/services/observation_window.py`

Defaults (per brief):
- Slack internal: 2 hours
- Email internal: 1 day
- Email external: 2–3 days
- Meeting internal: 1–2 days
- Meeting external: 2–3 days

Methods:
- `is_observable(commitment)` → bool
- `should_surface_early(commitment)` → bool (high-consequence external exceptions)

### 5. Surfacing Router

File: `app/services/surfacing_router.py`

Routing logic:
- If observation window not closed (and not early-surfaced): return None
- If critical ambiguity + above threshold: → Clarifications
- If priority ≥ 60: → Main
- If priority ≥ 35: → Shortlist
- Otherwise: → None (held internally)

### 6. Batch Surfacing Task

File: `app/tasks/surfacing_tasks.py`

Celery task `recompute_surfacing`:
- Find all non-completed, non-closed commitments
- Re-evaluate routing + priority for each
- Update `surfaced_as`, `priority_score`, `surfacing_reason`
- Log all changes to `SurfacingAudit` table
- Run every 30 minutes during business hours

### 7. API Updates

File: `app/routes/surface.py` (existing)

Update endpoints to query by `surfaced_as + priority_score DESC`:
- `GET /surface/main`
- `GET /surface/shortlist`
- `GET /surface/clarifications`
- `GET /surface/internal` (debug/admin only)

### 8. Tests

File: `tests/test_surfacing.py`, `tests/test_classifier.py`, etc.

Target: 30–40 new tests, bringing total to 210+
- Classification correctness
- Scoring across all dimensions
- Observation window logic
- Routing decisions
- Batch task
- API correctness

### 9. Documentation

Update/create:
- `docs/surfacing_architecture.md` — overall design
- `docs/priority_scoring.md` — dimensions and algorithm
- Code docstrings for all major functions

---

## Open Questions for Trinity

### Q1: `is_surfaced` vs `surfaced_as`

The existing model has `is_surfaced` BOOLEAN + `surfaced_at` TIMESTAMP. Phase 06 adds `surfaced_as` VARCHAR(20). Should I:
- Keep both for backward compatibility (set `is_surfaced = (surfaced_as IS NOT NULL)`)?
- Deprecate `is_surfaced` now and clean it up later?

**My recommendation:** Keep both. It's safer. Future cleanup phase can remove `is_surfaced` when all clients migrate to `surfaced_as`.

### Q2: Source Type Access

The brief calls `commitment.primary_source.source_type`, but this relationship doesn't exist. The actual path is:
```python
commitment.candidate_commitments[0].source_item.source.source_type
```

Should I:
- Add a helper method to traverse this chain and default to 'email_internal'?
- Or denormalize `source_type` onto the `commitment` table itself?

**My recommendation:** Add a helper method first. If it becomes a bottleneck, denormalize in a follow-up.

### Q3: `confidence_for_surfacing` Scale

The brief specifies `DECIMAL(5,2)` on 0–100 scale. All existing confidence fields use `Numeric(4,3)` on 0–1 scale. Should I:
- Store on 0–1 scale to match codebase convention, scale in the scorer?
- Or store on 0–100 scale per the brief?

**My recommendation:** Store 0–1 scale for consistency, scale to 0–100 in the scoring function.

### Q4: Surfacing Audit Table

The brief mentions logging decisions but doesn't fully spec the schema. My recommendation:

```sql
CREATE TABLE surfacing_audit (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    commitment_id BIGINT NOT NULL REFERENCES commitment(id),
    old_surfaced_as VARCHAR(20),
    new_surfaced_as VARCHAR(20),
    priority_score DECIMAL(5,2),
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (commitment_id),
    INDEX (created_at)
);
```

Is this acceptable, or should the audit record include additional fields?

### Q5: File Path Convention

The brief references `src/rippled/...`, but the actual codebase uses `app/...`. I'll use `app/` throughout. Correct?

---

## Confidence Level & Blockers

**Confidence:** High. The existing model already supports most of what Phase 06 needs. The work is mainly adding new fields, new scoring logic, and updating routing. No architectural surprises.

**Blockers:** None. I have everything I need to move to implementation.

**Dependencies:** Existing `Commitment` model, existing Celery task infrastructure, existing API route patterns (all from Phases 01–05).

---

## Next Step

Awaiting Trinity's review of this interpretation and approval to proceed to Phase A3 (Build). Specifically:
1. Guidance on Q1–Q5 above
2. Confirmation that the plan aligns with product intent
3. Go/no-go to implement

---

*Interpretation written: 2026-03-12 22:25 UTC*
