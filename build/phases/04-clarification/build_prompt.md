# Phase 04 — Clarification: BUILD PROMPT

## You are entering STAGE 3 — BUILD

Trinity has reviewed the interpretation against Brief 09 (Clarification) and the directive. All open questions are resolved. Proceed directly to implementation using TDD.

---

## Resolved Open Questions (Trinity decisions)

**Q1 — Does Phase 04 own promotion?**
**Decision: YES.** Phase 04 owns promotion. The Celery beat task queries `commitment_candidates` not `commitments`.

**Q2 — Add `signals_conflicting` to `AmbiguityType` enum?**
**Decision: NO for MVP.** Use `timing_conflicting` + `commitment_unclear` as documented fallback. Add a `# TODO(signals-conflicting)` comment in analyzer. No migration needed for enum extension.

**Q3 — Title generation at promotion**
**Decision: DETERMINISTIC DERIVATION from raw_text.** Normalize to action phrase (e.g., "I'll send the revised proposal" → "Send revised proposal"). Use `title = raw_text[:200]` as safe fallback if normalization fails. This is acceptable MVP.

---

## What To Build

### 1. Alembic Migration — `clarifications` table

File: `migrations/versions/<hash>_phase04_clarifications.py`

Table: `clarifications`
- `id` UUID PK default gen_random_uuid()
- `commitment_id` UUID FK → commitments.id NOT NULL
- `user_id` UUID FK → users.id NULLABLE (populated at promotion)
- `issue_types` TEXT[] NOT NULL (array of AmbiguityType enum values as strings)
- `issue_severity` VARCHAR NOT NULL (high/medium/low)
- `why_this_matters` TEXT
- `observation_window_status` VARCHAR NOT NULL DEFAULT 'open' (open/expired/skipped)
- `suggested_values` JSONB DEFAULT '{}'
- `supporting_evidence` JSONB DEFAULT '[]'
- `suggested_clarification_prompt` TEXT
- `surface_recommendation` VARCHAR NOT NULL DEFAULT 'do_nothing'
- `resolved_at` TIMESTAMP WITH TIME ZONE NULLABLE
- `created_at` TIMESTAMP WITH TIME ZONE DEFAULT now()
- `updated_at` TIMESTAMP WITH TIME ZONE DEFAULT now()

Also add SQLAlchemy ORM model in: `app/models/clarification.py`
Register it in `app/models/__init__.py` and `app/models/orm.py`.

### 2. `app/services/clarification/analyzer.py`

**Function:** `analyze_candidate(candidate) -> AnalysisResult`

AnalysisResult (dataclass or TypedDict):
- `issue_types: list[AmbiguityType]`
- `issue_severity: str` (high/medium/low)
- `why_this_matters: str`
- `observation_window_status: str` (open/expired/skipped)
- `surface_recommendation: str` (do_nothing/internal_only/clarifications_view/escalate)

**Nine issue inference rules** (from interpretation section 2):
- `commitment_unclear`: `is_explicit=False` AND `confidence_score < 0.55`, OR `flag_reanalysis=True`, OR implicit trigger classes
- `owner_missing`: trigger_class contains "unresolved_obligation" OR empty linked_entities.people AND no named speaker
- `owner_vague_collective`: trigger_class contains "collective_commitment" OR "we/us/team/someone" in raw_text (case-insensitive)
- `timing_missing`: linked_entities.dates is empty AND no vague phrase in raw_text
- `timing_vague`: any of "soon", "later", "this week", "end of month", "after the" in raw_text
- `deliverable_unclear`: any of "handle it", "sort it", "take care of it", "sort that" in raw_text
- `target_unclear`: any of "send that", "forward it", "update the doc", "update that" in raw_text AND no clear antecedent in context_window
- `timing_conflicting`: trigger_class == "deadline_change"
- `status_unclear`: source_type detection signal with delivery patterns

**Severity logic:**
- CRITICAL → high: `commitment_unclear`, `owner_missing`, `owner_vague_collective`, or 3+ issue types
- NON-CRITICAL → medium: `timing_*`, `target_unclear`, `deliverable_unclear`, `status_unclear`
- Escalated to high if: `context_type=external` AND critical issue present

**Observation window status:**
- `skipped`: `context_type=external` AND critical issue, OR `priority_hint=high`
- `expired`: `observe_until <= now()` (or observe_until is None)
- `open`: `observe_until > now()`

**Surface recommendation algorithm (exact):**
```python
critical = [i for i in issue_types if is_critical(i)]
if critical and context_type == "external":          → "escalate"
elif critical and obs_status == "expired":           → "clarifications_view"
elif critical and obs_status in ("open", "skipped"): → "do_nothing"
elif not critical and obs_status == "expired":       → "internal_only"
else:                                                → "do_nothing"

# Overrides:
if all severity == "low":                            → "do_nothing"
if not critical and context_type == "external":      → max "clarifications_view"
```

### 3. `app/services/clarification/promoter.py`

**Function:** `promote_candidate(candidate, db) -> Commitment`

Steps (from interpretation section 4):
1. Load candidate → raise ValueError if already promoted or discarded
2. Derive title from raw_text: strip "I'll/I will/We'll/We will/I'm going to" prefix, capitalize, truncate at 200 chars
3. Create `Commitment` with:
   - `title` = derived
   - `commitment_text` = candidate.raw_text
   - `context_type` = derived from candidate.source_type ("external" if email/external, "internal" otherwise)
   - `ownership_ambiguity` = True if `owner_missing` or `owner_vague_collective` in issues
   - `timing_ambiguity` = True if `timing_missing` or `timing_vague` or `timing_conflicting` in issues
   - `deliverable_ambiguity` = True if `deliverable_unclear` or `target_unclear` in issues
   - `suggested_owner` = None (Phase 04 doesn't resolve — just flags)
   - `suggested_due_date` = first date in linked_entities.dates if any
   - `suggested_next_step` = None (set by suggestions.py)
   - `confidence_commitment` = candidate.confidence_score
   - `observe_until` = candidate.observe_until
   - `lifecycle_state` = `needs_clarification` if any issue, else `proposed`
   - `user_id` = candidate.user_id (if present)
4. Create `CandidateCommitment` join record
5. Create `CommitmentAmbiguity` per issue type
6. Mark `candidate.was_promoted = True`
7. Return commitment (do NOT flush — caller owns transaction)

### 4. `app/services/clarification/suggestions.py`

**Function:** `generate_suggestions(candidate, issues) -> dict`

Returns JSONB-ready dict with keys present only when there's meaningful evidence:

- `likely_next_step`: normalize raw_text to action phrase (strip subject, keep verb+object). Always attempt.
- `likely_owner`: only if `is_explicit=True` and single person in linked_entities.people → `{value, confidence: 0.7, reason}`
- `likely_due_date`: only if linked_entities.dates non-empty → first entry, `{value, confidence: 0.6, reason: "extracted from source"}`
- `likely_completion`: only if `status_unclear` in issues AND source_type matches delivery pattern → `{value, confidence: 0.4, reason}`

### 5. `app/services/clarification/clarifier.py`

**Function:** `run_clarification(candidate_id: str, db) -> dict`

Orchestration flow:
1. Load candidate; raise if not found
2. If `was_promoted=True` or `was_discarded=True` → return `{"status": "skipped", "reason": "already processed"}`
3. Call `analyze_candidate(candidate)` → analysis
4. If `observation_window_status == "open"` AND no critical issues → return `{"status": "deferred", "candidate_id": str(candidate_id)}`
5. Call `promote_candidate(candidate, db)` with analysis results → commitment
6. Call `generate_suggestions(candidate, analysis.issue_types)` → suggested_values
7. Create `Clarification` row
8. Create `LifecycleTransition` record (from_state=None, to_state=lifecycle_state, trigger="phase04_clarification")
9. db.flush()
10. Return `{"status": "clarified", "commitment_id": str(commitment.id), "surface_recommendation": analysis.surface_recommendation}`

### 6. `app/tasks.py` — Clarification task + beat schedule

Add to existing tasks.py:

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.run_clarification")
def run_clarification_task(self, candidate_id: str) -> dict:
    ...calls run_clarification(candidate_id, session)...

# Beat schedule (add to celery_app.conf):
beat_schedule = {
    "clarification-sweep": {
        "task": "app.tasks.run_clarification_batch",
        "schedule": 300.0,  # 5 minutes
    }
}

@celery_app.task(name="app.tasks.run_clarification_batch")
def run_clarification_batch() -> dict:
    """Queries candidates where observe_until <= now() AND was_promoted=False AND was_discarded=False.
    Enqueues run_clarification_task for each. Returns count."""
    ...
```

### 7. `tests/services/test_clarification.py`

Full TDD suite. Cover:

**Analyzer tests:**
- `test_analyze_commitment_unclear` — low confidence implicit → commitment_unclear detected
- `test_analyze_owner_missing` — no people in linked_entities → owner_missing
- `test_analyze_owner_vague_collective` — "we'll handle it" → owner_vague_collective
- `test_analyze_timing_missing` — no dates, no vague phrases → timing_missing
- `test_analyze_timing_vague` — "soon" in raw_text → timing_vague
- `test_analyze_severity_critical_owner_missing` — owner_missing → high severity
- `test_analyze_severity_medium_timing` — timing_missing only → medium
- `test_analyze_surface_escalate` — critical + external → escalate
- `test_analyze_surface_clarifications_view` — critical + expired → clarifications_view
- `test_analyze_surface_do_nothing_open` — critical + open → do_nothing
- `test_analyze_surface_internal_only` — non-critical + expired → internal_only
- `test_analyze_observation_skipped_external_critical` — external + critical → skipped
- `test_analyze_all_low_override` — all low severity → do_nothing regardless

**Promoter tests:**
- `test_promote_creates_commitment` — happy path, commitment created
- `test_promote_sets_lifecycle_needs_clarification` — when issues present
- `test_promote_sets_lifecycle_proposed` — when no issues
- `test_promote_raises_already_promoted` — ValueError on double-promote
- `test_promote_title_derived` — "I'll send the revised proposal" → "Send the revised proposal"
- `test_promote_title_fallback` — no prefix match → raw_text[:200]
- `test_promote_creates_candidate_commitment_join`
- `test_promote_creates_ambiguity_records`
- `test_promote_marks_candidate_promoted`

**Suggestions tests:**
- `test_suggestions_likely_next_step` — always included
- `test_suggestions_likely_owner_when_explicit` — single person + explicit
- `test_suggestions_no_owner_when_collective` — vague → not included
- `test_suggestions_due_date_from_entities`
- `test_suggestions_empty_when_no_signals`

**Clarifier (integration) tests:**
- `test_clarifier_full_flow` — end-to-end with DB, returns clarified status
- `test_clarifier_deferred_open_window` — open window + no critical → deferred
- `test_clarifier_skips_already_promoted`
- `test_clarifier_creates_clarification_row`
- `test_clarifier_creates_lifecycle_transition`

Use pytest fixtures matching `tests/services/test_detection.py` patterns.
Use `conftest.py` if one exists; create minimal one if not.
Mock DB for unit tests; use in-memory SQLite or test DB for integration tests.

---

## After implementation:

1. Run `pytest tests/services/test_clarification.py -v` — all tests must pass
2. Run `ruff check app/` — fix all issues
3. Run `pytest tests/` to confirm no regressions in Phase 03 tests
4. Update `build/phases/04-clarification/decisions.md` with every non-obvious choice
5. Write `build/phases/04-clarification/completed.md` listing every file created/modified
6. Write empty `build/phases/04-clarification/completed.flag`
7. `git add` relevant files, commit: `feat: phase 04 — clarification analyzer, promoter, suggestions, celery integration`
8. `git push`

DO NOT modify files in `briefs/`. DO NOT reference OpenAgency OS or archived code.
DO NOT modify existing Phase 01/02/03 models without strong justification (add fields only if strictly needed).

Hand off cleanly. Trinity will review your commits and update state.json.
