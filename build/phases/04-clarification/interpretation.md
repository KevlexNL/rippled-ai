# Phase 04 — Clarification: Interpretation

## 1. What This Phase Does and Why

**Core philosophy:** Clarification bridges raw detection signals and actionable commitments. Phase 03 cast a broad net and preserved ambiguity. Phase 04 decides what to *do* with each candidate.

The four possible decisions per item:
1. **Do nothing yet** — observation window open, future signals likely
2. **Surface internally only** — worth tracking, not worth prompting
3. **Suggest clarification in review surface** — ambiguity matters, window expired
4. **Escalate for timely review** — external-facing, high stakes

**Critical architectural gap:** There is no promotion service yet. Phase 03 creates `CommitmentCandidate` rows. Phases 05–06 work with `Commitment` rows. Phase 04 must own promotion because you cannot generate a clarification object (which has `commitment_id`) without first creating a commitment, and lifecycle state (`proposed` vs `needs_clarification`) cannot be set without ambiguity analysis. These are necessarily unified.

---

## 2. How Ambiguity Detection Will Work

**Input signals from CommitmentCandidate:**
- `trigger_class` — explicit/implicit, self/collective
- `is_explicit`, `confidence_score`, `raw_text`
- `linked_entities` — `{dates, people}` from detection
- `context_window` — sender, speaker turns, thread parent
- `flag_reanalysis`, `source_type`, `priority_hint`

**Nine issue type inference rules:**

| Issue | Enum value | Key signals |
|-------|-----------|-------------|
| Uncertain commitment | `commitment_unclear` | `is_explicit=False` + `confidence < 0.55`, `flag_reanalysis=True`, implicit trigger classes |
| Missing owner | `owner_missing` | `implicit_unresolved_obligation`, empty `linked_entities.people`, no named speaker |
| Vague owner | `owner_vague_collective` | `explicit_collective_commitment`, "we/us/team" in raw_text |
| Missing deadline | `timing_missing` | empty `linked_entities.dates`, no vague phrase either |
| Vague deadline | `timing_vague` | "soon/later/this week/end of month" in raw_text |
| Unclear deliverable | `deliverable_unclear` | "I'll handle it/sort it/take care of it" — no object noun extractable |
| Unclear target | `target_unclear` | "I'll send that/forward it" — pronoun with no antecedent |
| Conflicting signals | `timing_conflicting` | `trigger_class=deadline_change`, contradictory timing across candidates |
| Completion ambiguity | `status_unclear` | `delivery_signal` with indirect/uncertain evidence |

**Severity:**
- **Critical (high):** `commitment_unclear`, `owner_missing`, `owner_vague_collective`, multiple conflicts
- **Non-critical (medium/low):** `timing_*`, `target_unclear`, `deliverable_unclear`, `status_unclear`
- **Escalated** if `context_type=external` or `priority_hint=high`

---

## 3. Data Model Requirements

**New table: `clarifications`**
- `id`, `commitment_id` (FK), `user_id`
- `issue_severity` (high/medium/low)
- `why_this_matters` (TEXT)
- `observation_window_status` (open/expired/skipped)
- `suggested_values` (JSONB — `{likely_next_step, likely_owner, likely_due_date, likely_completion}`)
- `supporting_evidence` (JSONB — list of candidate/item IDs)
- `suggested_clarification_prompt` (TEXT)
- `surface_recommendation` (do_nothing/internal_only/clarifications_view/escalate)
- `resolved_at`, `created_at`, `updated_at`

**Rationale:** `CommitmentAmbiguity` holds individual issue records (one per type). `Clarification` holds the aggregated surfacing decision. These are different concerns; merging them onto `Commitment` would overload an already heavy model.

**Commitment fields populated at promotion:**
`title` (derived from raw_text), `commitment_text`, `context_type`, `ownership_ambiguity`, `timing_ambiguity`, `deliverable_ambiguity`, `suggested_owner`, `suggested_due_date`, `suggested_next_step`, `confidence_commitment`, `observe_until`, `lifecycle_state`

**Possible enum gap:** `AmbiguityType` has `timing_conflicting` but no `signals_conflicting`. MVP will use `timing_conflicting` + `commitment_unclear` as fallback. See Q2.

---

## 4. Integration with Detection Output

**`run_clarification(candidate_id, db)` flow:**
1. Load candidate → raise if not found or already promoted
2. Check observation window — defer if open + no critical issues; proceed if expired or critical+external
3. Classify ambiguity issues → list of `AmbiguityType` + severity
4. Create `Commitment` with lifecycle_state = `needs_clarification` or `proposed`
5. Create `CandidateCommitment` join record
6. Create `CommitmentAmbiguity` per issue
7. Compute suggested values
8. Create `Clarification` row
9. Create `LifecycleTransition` record
10. Mark `candidate.was_promoted = True`

**Celery beat task** (every 5–15 min) queries candidates where `observe_until <= now() AND was_promoted=false AND was_discarded=false`, enqueues `run_clarification_task(candidate_id)` for each.

---

## 5. Observation Window Logic

- `"open"` — `observe_until > now()`, no override
- `"expired"` — `observe_until <= now()`
- `"skipped"` — window shortened for external + critical issue

**Skip conditions:** `context_type=external` + critical issue, or `priority_hint=high`

Calendar-hour approximations inherited from Phase 03. `# TODO(working-hours)` comments where computed.

---

## 6. Surface Recommendation Algorithm

```
if critical_issues AND external:           → "escalate"
elif critical_issues AND expired:          → "clarifications_view"
elif critical_issues AND (open/skipped):   → "do_nothing"
elif no critical AND expired:              → "internal_only"
else:                                      → "do_nothing"

Override: all-low severity → "do_nothing" always
Override: non-critical + external → max "clarifications_view"
```

**Suggested values:** All deterministic (no LLM for MVP). `likely_next_step` always attempted (normalize raw_text to action phrase). `likely_owner` from sender when explicit_self_commitment. `likely_due_date` from `linked_entities.dates`. Stored with confidence + reason for each.

---

## 7. Key Decisions

1. **Phase 04 owns promotion** — the only logical owner; lifecycle state requires ambiguity analysis
2. **New `clarifications` table** — separate from `CommitmentAmbiguity` (individual issues) and `Commitment` (already heavy)
3. **Deterministic MVP** — consistent with Phase 03; JSONB structure ready for LLM enrichment later
4. **One Clarification per Commitment** — updated in place when new signals arrive (Phase 05 handles this)

---

## 8. Questions for Kevin (need answers before building)

**Q1 — Does Phase 04 own promotion?**
My read: yes. Alternative: detection auto-promotes to `proposed`, clarification runs on commitments. This changes the Celery task significantly — it would query `commitments` not `commitment_candidates`.

**Q2 — Add `signals_conflicting` to `AmbiguityType` enum?**
Current enum only has `timing_conflicting`. My preference: add `signals_conflicting` in this migration.

**Q3 — Title generation at promotion**
`Commitment.title` is NOT NULL. Plan: derive deterministically from `raw_text` (e.g., "I'll send the revised proposal" → "Send revised proposal"). Is this acceptable, or should it be user-provided with a placeholder?

---

## 9. Implementation Plan

1. Migration — `clarifications` table; optionally `signals_conflicting` enum value
2. `app/services/clarification/analyzer.py` — issue classification, severity, surface recommendation
3. `app/services/clarification/promoter.py` — candidate → commitment
4. `app/services/clarification/suggestions.py` — suggested value generation
5. `app/services/clarification/clarifier.py` — orchestration
6. `app/tasks.py` — `run_clarification_task` + beat schedule
7. `tests/services/test_clarification.py` — full suite (TDD)

---
