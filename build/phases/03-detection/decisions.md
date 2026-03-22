# Phase 03 — Detection Pipeline: Technical Decisions

**Phase:** 03-detection
**Date:** 2026-03-11 (initial), 2026-03-22 (retroactive documentation)
**Status:** Complete

---

## 1. Two-Layer Detection Strategy

**Decision:** Deterministic regex patterns (Tier 2) + profile-based pattern matching (Tier 1), with LLM model-assisted detection added later as Tier 3 (seed detector / model detection).

**Rationale:** The brief calls for "deterministic heuristics + model assistance." For MVP, deterministic-only detection shipped first because:
- Zero latency, zero API cost per detection
- Predictable, testable, reproducible results
- Architecture designed to slot in model calls later (which happened in Phase C1)

**Evolution:** Tier 1 (profile-based matching from learning loop) was added post-Phase 03 to skip the full pattern scan for high-signal senders. Tier 3 (LLM-assisted via seed detector + model detection) was added in subsequent phases.

---

## 2. Pattern Organization: Structured Data, Not Scattered Logic

**Decision:** All trigger patterns defined as `TriggerPattern` dataclass instances in `patterns.py`, organized by source type and category.

**Rationale:**
- Patterns are data, not control flow — easy to audit, test individually, add new patterns
- Each pattern carries its own metadata (trigger_class, is_explicit, base_confidence, applies_to)
- Suppression patterns run first to strip noise before capture patterns match
- Source-specific patterns only run for their applicable source types

---

## 3. Confidence Score Calibration

**Decision:** Numeric confidence on `NUMERIC(4,3)` scale with heuristic values:
- Explicit pattern + external context: 0.80–0.90
- Explicit pattern (internal): 0.65–0.80
- Implicit pattern: 0.45–0.60
- Edge cases (hedged language, short acceptance): 0.35–0.55
- External context adds +0.10 boost

**Rationale:** Schema already committed to `NUMERIC(4,3)`. Numeric values allow sorting and threshold-based filtering downstream. Values are calibrated conservatively — detection should over-capture, not over-reject.

---

## 4. Schema Migration: Explicit Columns + JSONB

**Decision:** Added explicit columns for frequently queried fields (`trigger_class`, `is_explicit`, `priority_hint`, `commitment_class_hint`, `source_type`, `flag_reanalysis`) and JSONB for complex/variable data (`context_window`, `linked_entities`).

**Rationale:**
- `trigger_class`, `priority_hint`, `commitment_class_hint` are used in WHERE and ORDER BY → must be indexed columns
- `context_window` stores source-type-specific structures (speaker turns, thread parent, email direction) → JSONB is appropriate
- `source_type` denormalized from source_item for query efficiency without joins
- `observe_until` as `TIMESTAMPTZ` — wall-clock deadline, working-hours calculation deferred to application layer

---

## 5. Sync Session for Celery Workers

**Decision:** Separate sync SQLAlchemy engine (`app/db/session.py`) with `create_engine` + `sessionmaker`, parallel to the async engine used by FastAPI routes.

**Rationale:** Celery workers are synchronous by default. Running an async event loop inside Celery tasks adds complexity with no benefit. The dual-engine approach is clean: routes use async, workers use sync, both hit the same Postgres.

---

## 6. Savepoint Isolation for Candidate Inserts

**Decision:** Each candidate insert uses `db.begin_nested()` (savepoint). One bad insert doesn't abort other candidates from the same source item.

**Rationale:** A meeting transcript may produce 5 candidates. If candidate #3 hits a constraint violation, candidates #1, #2, #4, #5 should still persist. This mirrors the batch ingestion pattern from Phase 02 (where the Phase 02 review found a critical bug with non-savepoint rollbacks).

---

## 7. Observation Window Computation

**Decision:** Detection writes `observe_until` to the candidate using wall-clock defaults per source type:
- Slack internal: +2 hours
- Email internal: +8 hours (~1 working day)
- Email external: +48 hours (~2–3 working days)
- Meeting internal: +16 hours (~1–2 working days)
- Meeting external: +48 hours (~2–3 working days)

**Rationale:** Working-hours calculation deferred to application layer. Calendar-hour approximations are acceptable for MVP. Candidate's `observe_until` is copied to the commitment on promotion (later phase handles this).

---

## 8. Suppression Strategy

**Decision:** Two-pass approach:
1. Run suppression patterns first to strip: email quoted chains, forward headers, hypotheticals, conversational fillers, greetings, pleasantries
2. Run capture patterns on the cleaned content

**Rationale:** Stripping quoted email text before detection prevents re-detecting historical commitments. Removing hypotheticals and fillers reduces false positives. Suppression patterns are separate from capture patterns for clarity and testability.

---

## 9. Context Window Design

**Decision:** Source-type-specific context extraction:
- **Meeting:** Parse speaker turns, extract ±2 turns around trigger, flag uncertain attribution
- **Slack:** Pull thread parent from metadata, include channel and mentions
- **Email:** Include direction, external recipient flag, recipients list, strip quoted history

**Rationale:** The brief explicitly requires source-aware context. A generic "200 chars before and after" is insufficient — thread parent in Slack, speaker turns in meetings, and direction in email are all critical for downstream interpretation.

---

## 10. Linked Entity Extraction

**Decision:** Lightweight regex-based extraction for dates and person mentions. No ML/NER.

**Rationale:** MVP scope. Captures obvious date references (Monday, tomorrow, by end of day) and @mentions or "Firstname Lastname" patterns. Good enough for downstream priority elevation. Full NER can be added when model-assisted detection arrives.

---

## 11. Re-analysis Flagging

**Decision:** `flag_reanalysis = True` only for meeting transcripts where uncertain markers (`[inaudible]`, `[crosstalk]`, `[unclear]`, `[unknown speaker]`) appear within 100 chars of the trigger text. Email and Slack always set `flag_reanalysis = False`.

**Rationale:** Per the brief: "meetings are the primary place where re-analysis flags matter." Transcript quality directly affects commitment interpretation. Written channels (Slack, email) don't have transcription uncertainty.

---

## 12. Audit Trail

**Decision:** `DetectionAudit` table tracks every detection invocation: which tier handled it, matched phrase, confidence, whether a candidate was created, and (for LLM tiers) prompt version, raw prompt/response, token counts, cost estimate.

**Rationale:** Essential for cost analysis (Tier 1 is free, Tier 3 costs API tokens), funnel optimization (what % handled at each tier), and debugging (why did detection fire or not fire for a given item).

---

*Decision document complete. Covers all technical choices made during Phase 03 implementation and subsequent detection pipeline evolution.*
