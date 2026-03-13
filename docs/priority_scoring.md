# Priority Scoring — Phase 06

## Overview

Each commitment receives a 0–100 priority score computed from six dimensions. Higher scores surface to `main`; lower scores go to `shortlist`, or are held internally.

Implemented in `app/services/priority_scorer.py`.

---

## Formula

```
score = externality + timing + consequence + burden + confidence + staleness
```

### Dimensions

| Dimension | Source field | Range | Max contribution |
|---|---|---|---|
| Externality | `is_external` | bool | **25** (flat bonus) |
| Timing | `timing_strength` (0–10) | 0–10 | **20** (×2 scale) |
| Business consequence | `business_consequence` (0–10) | 0–10 | **20** (×2 scale) |
| Cognitive burden | `cognitive_burden` (0–10) | 0–10 | **15** (×1.5 scale) |
| Confidence | `confidence_for_surfacing` (0–1) | 0–1 | **15** (×15 scale) |
| Staleness bonus | `observe_until` vs now | 0–1 fraction | **10** |
| **Total** | | | **105** (capped at 100) |

---

## Dimension Details

### Externality (+25)

A flat 25-point bonus for external/client-facing commitments. Determined by `context_type == 'external'` or source type inference via the candidate chain.

### Timing (0–20)

Derived from `timing_strength` (0–10) × 2.

`timing_strength` is scored by `commitment_classifier.score_timing_strength()`:
- `resolved_deadline` present → 8
- Strong vague phrase (e.g., "by Friday", "today") → 7
- Weak vague phrase (e.g., "soon", "eventually") → 2
- `deadline_candidates` present → 4
- `timing_ambiguity = 'missing'` → 0
- Otherwise → 3

### Business Consequence (0–20)

Derived from `business_consequence` (0–10) × 2.

`business_consequence` is scored by `commitment_classifier.score_business_consequence()`:
- External base: 7 | Internal base: 4
- +1 if `confidence_commitment ≥ 0.8`
- +1 if explicit `deliverable` present
- +1 if `resolved_deadline` present
- Capped at 10

### Cognitive Burden (0–15)

Derived from `cognitive_burden` (0–10) × 1.5.

`cognitive_burden` scores how easy it is to forget the commitment:
- Baseline: 3
- 1 follow-up phrase match → 6
- 2+ follow-up phrase matches → 7–8
- Long deliverable (>80 chars) → +1
- External context → +1
- Capped at 10

Follow-up phrases: "I'll send", "I'll reply", "let me", "remind me", etc.

### Confidence (0–15)

Derived from `confidence_for_surfacing` (0–1) × 15.

**Asymmetric suppression:** if `confidence_for_surfacing < 0.3`, the confidence contribution is halved. This prevents very low-confidence signals from accumulating enough score to surface.

`confidence_for_surfacing` = weighted composite:
- `confidence_commitment` × 0.4
- `confidence_owner` × 0.3
- `confidence_actionability` × 0.3
- Missing dimensions default to 0.5 (uncertain but not disqualifying)

### Staleness Bonus (0–10)

A time-based bonus for commitments that have passed their observation window but remain unresolved.

```
staleness = min(hours_past_window / 168, 1.0) × 10
```

- At 168 hours (7 days) past the window → full 10-point bonus
- Only applies to `proposed`, `active`, `needs_clarification` states
- Zero if `observe_until` is None or still in the future

---

## Routing Thresholds

| Threshold | Surface |
|---|---|
| Score ≥ 60 | `main` |
| Score 35–59 | `shortlist` |
| Score < 35 (or in window) | `None` (held internally) |
| Any score ≥ 25 + critical ambiguity | `clarifications` |

---

## Example Scores

| Commitment profile | ~Score |
|---|---|
| External, explicit deadline, high confidence, stale | 85–95 |
| External, vague deadline, medium confidence | 55–70 |
| Internal, strong follow-up language, explicit deadline | 45–58 |
| Internal, no timing, low confidence | 10–25 |
