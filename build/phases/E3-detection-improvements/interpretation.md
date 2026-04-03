# Phase E3: Detection Improvements — Interpretation

**Author:** Claude (Stage 2)  
**Date:** 2026-04-03  
**Status:** Ready for Trinity review

---

## What this phase is asking for

Three detection-fidelity improvements that close gaps identified in the vision delta review:

1. **4.1 — Cross-source merge logic:** When the same real-world commitment is detected from multiple sources (e.g., meeting transcript + follow-up email), merge them into one commitment instead of duplicating.

2. **10.1 — Cross-channel completion matching:** Completion evidence from one source channel should be able to close a commitment originating from a different channel (e.g., email delivery closes meeting-sourced commitment).

3. **10.2 — Type-specific completion scoring:** Different commitment types (`send`, `reply`, `review`, `create`, `coordinate`) should have differentiated scoring paths, not just the existing multiplier.

---

## Codebase Analysis

### Where each sub-task hooks in

#### 4.1 — Cross-source merge logic

**Current state:** No merge/dedup mechanism exists. The `CandidateCommitment` join table (N:M) theoretically supports linking multiple candidates to one commitment, but nothing populates it that way. Each detection run creates independent candidates → independent commitments.

**Hook points:**
- **After seed detection** (`app/services/detection/seed_detector.py`): The seed pass creates `Commitment` + `CommitmentSignal` rows directly. Post-run is where merge detection should fire.
- **After promotion** (`app/services/clarification/promoter.py:111-200`): When a `CommitmentCandidate` gets promoted to `Commitment`, that's the second natural point to check for merge candidates.
- **New service:** `app/services/detection/merge_detector.py` — a new module that runs similarity matching against existing active commitments.

**Matching dimensions for merge detection:**
- `resolved_owner` / `suggested_owner` (actor)
- `target_entity` (recipient)
- `deliverable` / `commitment_text` (deliverable overlap)
- `created_at` (timeframe proximity)
- `commitment_type` (same type)

**Merge action:**
- Keep highest-confidence commitment as canonical
- Link additional signals from the duplicate to the canonical commitment via `CommitmentSignal`
- Mark duplicate with `lifecycle_state = 'discarded'` + `discard_reason = 'merged::{canonical_id}'`
- No new DB column needed — we can use the existing `discard_reason` field to encode the merge relationship

#### 10.1 — Cross-channel completion matching

**Current state:** Already partially solved. The completion detector at `app/services/completion/detector.py:96-101` queries commitments by `user_id` + `lifecycle_state == active` — no source_type filter. So email evidence *already* gets matched against meeting-sourced commitments.

**However, there is a gap:** The matcher at `app/services/completion/matcher.py` does not apply any cross-channel confidence bonus. Brief 10 specifies "multiple corroborating signals across channels" as a confidence-increasing factor, and the phase brief calls for `cross_channel_match_score = source_signal_bonus × standard_match_score`.

**Hook points:**
- **Matcher** (`app/services/completion/matcher.py:191-287`): Needs to track whether the evidence source_type differs from the commitment's origin source_type. This requires knowing the commitment's origin source — available via `CommitmentSignal` with `signal_role='origin'`.
- **Scorer** (`app/services/completion/scorer.py`): Add a `_cross_channel_bonus()` or integrate into `_compute_delivery_confidence()`. If evidence comes from a different channel than the commitment's origin, apply a configurable bonus (the cross-channel corroboration signal).
- **Detector** (`app/services/completion/detector.py:106-110`): Already pre-loads origin thread_ids. Extend to also attach origin `source_type` to each commitment for the matcher/scorer to use.

#### 10.2 — Type-specific completion scoring

**Current state:** Partially implemented. The scorer already has:
- `_COMPLETION_MULTIPLIERS` (line 40-51): Maps commitment types to multipliers applied to `delivery_confidence`.
- `_DELIVER_TYPES` / `_REVIEW_TYPES` (lines 34, 37): Attachment bonus and review penalty.

**What's missing:** The brief asks for differentiated *detection paths* per type, not just multipliers. Specifically:
- `send`: delivery signal strong → attachment/"sent you" patterns should boost score more
- `reply`: delivery easy → reply thread in same channel should boost
- `review`: harder → need explicit "reviewed"/"looked at" signals
- `create`: hardest → requires artifact signal
- `coordinate`: meeting booked/"sorted with X" signals

**Hook points:**
- **Scorer** (`app/services/completion/scorer.py`): Extend `_compute_delivery_confidence()` with type-specific adjustments that go beyond the current `+0.05`/`-0.10` pattern.
- **Matcher** (`app/services/completion/matcher.py:164-184`): `_compute_evidence_strength()` currently uses generic rules. Could add type-aware evidence strength classification (e.g., a `create` commitment with no artifact = always "weak").

---

## Concerns and Questions

### 4.1 — Merge logic

1. **When does merge detection run?** Two options:
   - **(A) Post-promotion hook:** After each `promote_candidate()` call, check the new commitment against existing active commitments for the same user. Simpler, real-time.
   - **(B) Periodic sweep:** A Celery beat task that scans for merge candidates periodically. Catches cases where commitments were created from different detection methods at different times.
   
   **Recommendation:** Option A (post-promotion hook) for immediate dedup, with a lightweight sweep as safety net. The brief says "after each detection run" which aligns with A.

2. **Similarity threshold configuration:** Brief says "configurable." I recommend a simple config dict in `app/services/detection/merge_detector.py` with sensible defaults (e.g., actor exact match required, deliverable word overlap >= 50%, timeframe <= 72 hours). Configurable via function parameters, not a DB settings table.

3. **Merge vs. link:** Brief says "link signals, keep highest-confidence as canonical, mark duplicate as merged." This is a soft merge (both rows persist, duplicate is discarded). No hard delete. This is safe and reversible.

4. **UI signal count:** Brief says "merged commitments show signal count." This is a frontend concern. The backend needs to ensure merged signals are properly linked to the canonical commitment. I'll focus on the backend merge logic; the frontend display is out of scope per the "What NOT to do" section.

### 10.1 — Cross-channel matching

5. **Determining origin source_type:** A commitment can have multiple origin signals from different sources. Which source_type is "the" origin? **Recommendation:** Use the earliest origin signal's `source_type`. If there's only one origin, that's it. Pre-load this alongside `_origin_thread_ids` in the detector.

6. **Cross-channel bonus magnitude:** Brief says `cross_channel_match_score = source_signal_bonus × standard_match_score`. What should `source_signal_bonus` be? **Recommendation:** 1.10 (10% bonus). Cross-channel corroboration is a confidence signal, not a dramatic score change. This aligns with Brief 10's "multiple corroborating signals across channels" as a confidence-increasing factor.

### 10.2 — Type-specific scoring

7. **Brief 10 defines 5 commitment types (A-E) but the enum has 12.** The brief's type categories map as follows:
   - A (send/share/deliver) → `send`, `deliver`, `introduce` (existing `_DELIVER_TYPES`)
   - B (reply/follow up/answer) → `follow_up`, `update`
   - C (review/check/look into) → `review`, `investigate` (existing `_REVIEW_TYPES`)
   - D (create/revise/prepare) → *(no direct enum match — falls to `other`)*
   - E (coordinate/introduce/arrange) → `coordinate`, `schedule`, `introduce`
   
   **Question for Trinity:** The brief's "create" type has no enum value. Should we add `create` to `CommitmentType`? Or map it to existing types? The current enum has `delegate`, `confirm`, `other` which don't clearly map to Brief 10's Type D.

8. **How deep should type-specific scoring go?** The current implementation applies a single multiplier. The brief asks for *different detection difficulty*. I propose type-specific adjustments in `_compute_delivery_confidence()` that modify the base score based on evidence characteristics — not a completely separate scoring path per type. This is the minimal viable change.

---

## Planned Implementation Order

### Order: 4.1 → 10.2 → 10.1

**Rationale for this order (differs slightly from brief's suggestion):**

1. **4.1 (merge) first** — most independent, as the brief notes. No impact on scorer/matcher.

2. **10.2 (type-specific scoring) second** — extends the scorer, which 10.1 will also modify. Building the type-specific infrastructure first means 10.1's cross-channel bonus can be type-aware if needed.

3. **10.1 (cross-channel) third** — builds on top of the scorer changes from 10.2 and requires changes to the detector's pre-loading logic.

### Detailed plan

**4.1 — Cross-source merge (estimated: 0.5 day)**
1. New module: `app/services/detection/merge_detector.py`
   - `find_merge_candidates(commitment, active_commitments, threshold_config) -> list[Commitment]`
   - `execute_merge(canonical, duplicate, db) -> None`
2. Integration: hook into `promoter.py` post-promotion
3. Tests: unit tests with mocked commitments, merge action verification

**10.2 — Type-specific scoring (estimated: 0.5 day)**
1. Extend `scorer.py` with type-specific delivery confidence adjustments:
   - `send`/`deliver`: bonus for attachment (+0.10) and outbound direction (+0.05)
   - `reply`/`follow_up`: bonus for same-thread evidence (+0.10)
   - `review`/`investigate`: require explicit review keywords, higher base penalty
   - `coordinate`/`schedule`: bonus for calendar-related keywords
2. Update `_compute_evidence_strength()` in matcher.py to be type-aware
3. Tests: parameterized tests per type with expected score adjustments

**10.1 — Cross-channel completion (estimated: 0.5 day)**
1. Extend `detector.py` to pre-load origin source_type per commitment
2. Pass origin source_type through to matcher/scorer
3. Add cross-channel bonus in scorer when evidence source != origin source
4. Tests: meeting commitment + email evidence, verify bonus applied

---

## Migration Considerations

**4.1 — No migration needed.** The merge relationship can be encoded using:
- Existing `lifecycle_state = 'discarded'` on the duplicate commitment
- Existing `discard_reason` field to store `'merged::{canonical_id}'`
- Existing `CommitmentSignal` table to re-link signals from duplicate to canonical

This avoids a new column and keeps the change additive. If we later want a dedicated `merged_into_id` FK column, that can be a separate migration in a future phase.

**10.1 — No migration needed.** Origin source_type is derived at runtime from `CommitmentSignal` + `SourceItem` join. No new columns.

**10.2 — No migration needed.** Scoring changes are pure logic in the scorer.

---

## Risks and Complexity Flags

### Medium risk: 4.1 merge similarity matching
- **False merges:** Two genuinely different commitments with the same actor, similar deliverable, close timeframe could be incorrectly merged. Mitigation: require high overlap threshold and same commitment_type match. Make it conservative — missing a merge is better than false-merging.
- **Seed vs. deterministic:** Seed detection creates commitments directly (bypassing candidates). Deterministic detection goes through candidates → promotion. The merge detector needs to handle both paths. Hooking post-promotion covers deterministic; for seed, hook into `seed_detector.py` after the batch creates commitments.

### Low risk: 10.1 cross-channel matching
- Already works at the query level (user-scoped, not source-scoped). The enhancement is just a scoring bonus. Low blast radius.

### Low risk: 10.2 type-specific scoring
- Additive changes to existing scorer. Existing multiplier structure already differentiates by type. We're deepening that differentiation, not rewriting the pipeline.

### Process risk: test isolation
- The completion tests use `SimpleNamespace` mocks (no DB). This is good — changes to scorer/matcher can be tested without DB fixtures. Merge tests will need to mock DB interactions for signal re-linking.

---

## Summary

| Sub-task | Complexity | Migration | Key files | Risk |
|----------|-----------|-----------|-----------|------|
| 4.1 Merge | Medium | None | New `merge_detector.py`, modify `promoter.py`, `seed_detector.py` | False merge (mitigated by conservative thresholds) |
| 10.1 Cross-channel | Low | None | `detector.py`, `scorer.py` | Minimal — additive scoring bonus |
| 10.2 Type-specific | Low-Medium | None | `scorer.py`, `matcher.py` | Minimal — extends existing multiplier pattern |

**Open question for Trinity:** Should we add `create` to the `CommitmentType` enum for Brief 10 Type D alignment, or defer?
