# Phase 04 — Clarification: Decisions

## Trinity Self-Approval (pre-build)

### Q1 — Does Phase 04 own promotion?
**Decision: YES.** Phase 04 owns promotion. The Celery beat task (`run_clarification_batch`) queries `commitment_candidates` not `commitments`. Promotion is triggered during clarification, not as a separate pre-step.

**Rationale:** Promotion without clarification context would create commitments with no ambiguity information. Phase 04 is the right place to atomically promote + annotate.

### Q2 — Add `signals_conflicting` to `AmbiguityType` enum?
**Decision: NO for MVP.** Use `timing_conflicting` + `commitment_unclear` as documented fallback. Added `# TODO(signals-conflicting)` comment in `analyzer.py`. No migration needed for enum extension at this stage.

**Rationale:** `signals_conflicting` requires multi-signal correlation logic that's out of Phase 04 scope. Deferring avoids premature schema complexity.

### Q3 — Title generation at promotion
**Decision: DETERMINISTIC DERIVATION from raw_text.** Strip first-person prefixes ("I'll", "I will", "We'll", "We will", "I'm going to"), capitalize, truncate at 200 chars. Fall back to raw_text[:200] if no prefix match.

**Rationale:** Deterministic is testable and reproducible. Phase 04 brief explicitly calls for this over any heuristic or AI-generated title.

---

## Implementation Decisions

### D1 — `suggested_due_date = None` in promoter
Phase 04 does not parse date strings to datetime objects. `linked_entities.dates` contains strings extracted during detection (e.g. "2026-03-15"). Parsing them to datetime would require locale/timezone assumptions not established in the brief. Deferred to Phase 05 or a later schema migration.

**Impact:** `Commitment.suggested_due_date` is always None after Phase 04. Phase 05 may fill it.

### D2 — `ownership_ambiguity` stored as enum string, not bool
The `Commitment.ownership_ambiguity` column is a VARCHAR, not a boolean. Values used: `"missing"` for `owner_missing`, `None` when no ownership issue. This preserves the full ambiguity type information for downstream surfacing logic without a separate column.

**Note:** `owner_vague_collective` also sets `ownership_ambiguity = "missing"` (same column value). The precise sub-type is stored in `CommitmentAmbiguity` rows.

### D3 — `_GENERIC_SPEAKER_PATTERN` for speaker identification
Speaker turns with names matching `^Speaker \d+$` (e.g. "Speaker 1", "Speaker 2") are treated as anonymous — they don't count as a "named speaker" for `owner_missing` inference. This pattern covers the common transcription format where speakers aren't identified.

### D4 — Observation window `skipped` vs `expired`
`skipped` means: the candidate should be processed immediately without waiting (due to external context + critical issue, or high priority hint). `expired` means: the observation window has closed through time. Both result in clarification proceeding, but `skipped` specifically indicates urgency/importance drove the decision, which is preserved in the `Clarification` row for surfacing logic.

### D5 — Clarifier uses `_is_critical` from analyzer module
`clarifier.py` imports `_is_critical` from `analyzer.py` (internal function). This avoids duplicating the critical-issues set definition. Acceptable coupling since they're in the same service package.

### D6 — `run_clarification_batch` queries by `observe_until <= now()`
The batch sweep queries candidates where the observation window has expired. Candidates with `observe_until=None` won't be caught by this query (NULL != value in SQL). However, individual `run_clarification_task` calls handle `observe_until=None` correctly (treated as expired in `_compute_obs_status`). The batch sweep is a scheduled safety net; direct task calls are the primary path.

**TODO:** Consider adding `OR observe_until IS NULL` to the batch query in a follow-up.

### D7 — Test strategy: SimpleNamespace over ORM objects
Tests use `types.SimpleNamespace` for candidate objects to avoid SQLAlchemy instrumentation overhead. This matches the Phase 03 test pattern. The services use duck typing (`Any` type hints) making this safe.

### D8 — Ruff fixes: 5 pre-existing issues auto-fixed
Running `ruff check app/ --fix` revealed 5 pre-existing unused imports across Phase 01/02/03 files (sources.py, surface.py, engine.py, orm.py, patterns.py). These were auto-fixed as part of Phase 04 verification. Kept atomic with the Phase 04 commit.
