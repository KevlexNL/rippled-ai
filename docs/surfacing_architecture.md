# Surfacing Architecture — Phase 06

## Overview

Phase 06 adds the surfacing layer: the logic that decides **what to show the user, where, and in what order**.

Each commitment is evaluated against four scoring dimensions and routed to one of four destinations:

| Destination | Description |
|---|---|
| `main` | High-priority commitments (score ≥ 60) |
| `shortlist` | Medium-priority commitments (score 35–59) |
| `clarifications` | Commitments with critical ambiguity that need user input |
| `None` | Held internally — not shown to user yet |

---

## Pipeline

```
SourceItem → CommitmentCandidate → Commitment
                                       ↓
                              commitment_classifier.classify()
                                       ↓
                              priority_scorer.score()
                                       ↓
                              observation_window.is_observable()
                              observation_window.should_surface_early()
                                       ↓
                              surfacing_router.route()
                                       ↓
                          Update commitment.surfaced_as
                          Append SurfacingAudit row if changed
```

### 1. Classifier (`app/services/commitment_classifier.py`)

Produces `ClassifierResult` with:
- `timing_strength` (0–10): How explicit/urgent the deadline is
- `business_consequence` (0–10): How costly it would be to miss this
- `cognitive_burden` (0–10): How easy it is to forget (small follow-ups score high)
- `confidence_for_surfacing` (0–1): Composite surfacing confidence
- `is_external`: Whether the commitment is client/partner-facing
- `has_critical_ambiguity`: Whether the commitment needs user clarification
- `source_type`: Source channel (email, slack, meeting, etc.)

### 2. Priority Scorer (`app/services/priority_scorer.py`)

Combines classifier dimensions into a 0–100 score. See `docs/priority_scoring.md` for the formula.

### 3. Observation Window (`app/services/observation_window.py`)

Each commitment has a silent observation window — a period where Rippled waits for more signals before surfacing. The window is stored as `observe_until` (timestamp).

- `is_observable(commitment)` → True if still in window (not ready to surface)
- `should_surface_early(commitment)` → True if the commitment is high-consequence enough to bypass the window

Early surfacing requires: **external + resolved_deadline + confidence_commitment ≥ 0.75**

Default windows by source type:
- Slack internal: ~2.8 calendar hours (2 working hours)
- Email internal: ~33.6 calendar hours (1 working day)
- Email external: ~67.2 calendar hours (2 working days)
- Meeting: ~33.6–67.2 calendar hours (1–2 working days)

### 4. Surfacing Router (`app/services/surfacing_router.py`)

Routing rules (evaluated in order):
1. If in observation window and no early-surface exception → `None`
2. If `has_critical_ambiguity` AND score ≥ 25 → `clarifications`
3. If score ≥ 60 → `main`
4. If score ≥ 35 → `shortlist`
5. Otherwise → `None` (held internally)

### 5. Surfacing Runner (`app/services/surfacing_runner.py`)

Called by the `recompute_surfacing` Celery task. Processes all non-terminal commitments in batch:
- Evaluates all `proposed`, `active`, `needs_clarification` commitments
- Updates `surfaced_as`, `priority_score`, dimension scores, `surfacing_reason`
- Sets `is_surfaced = (surfaced_as IS NOT NULL)` for backward compatibility
- Writes a `SurfacingAudit` row whenever `surfaced_as` changes

---

## Database Schema

### `commitments` additions

| Column | Type | Description |
|---|---|---|
| `surfaced_as` | VARCHAR(20) | Routing destination or NULL |
| `priority_score` | DECIMAL(5,2) | 0–100 computed score |
| `timing_strength` | SMALLINT | 0–10 timing clarity |
| `business_consequence` | SMALLINT | 0–10 consequence score |
| `cognitive_burden` | SMALLINT | 0–10 burden score |
| `confidence_for_surfacing` | DECIMAL(4,3) | 0–1 composite confidence |
| `surfacing_reason` | VARCHAR(255) | Human-readable routing reason |

Index: `ix_commitments_surfaced_as_priority` on `(surfaced_as, priority_score DESC)` where `surfaced_as IS NOT NULL`.

### `surfacing_audit`

Append-only log of every time `surfaced_as` changes for a commitment.

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT | Auto-increment PK |
| `commitment_id` | STRING (FK) | References commitments.id |
| `old_surfaced_as` | VARCHAR(20) | Previous value |
| `new_surfaced_as` | VARCHAR(20) | New value |
| `priority_score` | DECIMAL(5,2) | Score at time of change |
| `reason` | VARCHAR(255) | Routing reason |
| `created_at` | TIMESTAMP | When the change occurred |

---

## API Endpoints

All endpoints in `app/api/routes/surface.py`:

- `GET /surface/main` — commitments with `surfaced_as = 'main'`, ordered by `priority_score DESC`
- `GET /surface/shortlist` — commitments with `surfaced_as = 'shortlist'`, ordered by `priority_score DESC`
- `GET /surface/clarifications` — commitments with `surfaced_as = 'clarifications'`, ordered by `state_changed_at ASC`
- `GET /surface/internal` — unsurfaced active commitments (debug/admin)

All endpoints filter by `user_id` from the authenticated session.

---

## Celery Beat Schedule

Task `recompute_surfacing` runs every **30 minutes** (configured in `app/tasks.py`).
