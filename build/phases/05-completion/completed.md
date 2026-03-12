# Phase 05 — Completion Detection: Build Complete

**Date:** 2026-03-12
**Tests:** 32 new tests passing (178 total — Phase 03 + 04 + 05 all green)
**Ruff:** Clean

---

## What was built

### Schema (migration already existed)
- `commitments.delivered_at TIMESTAMP WITH TIME ZONE NULL` — set on active→delivered transition
- `commitments.auto_close_after_hours INTEGER NOT NULL DEFAULT 48` — per-commitment auto-close window
- Index: `ix_commitments_state_delivered_at` on `(lifecycle_state, delivered_at)` for sweep queries
- ORM model updated: `delivered_at` and `auto_close_after_hours` mapped_columns added to `Commitment`

### Service: `app/services/completion/`

**matcher.py** — `CompletionEvidence` dataclass + `find_matching_commitments()`
- Suppresses quoted email lines (`> ...`) before keyword matching
- `is_quoted_content=True` items excluded entirely
- Actor match is mandatory (case-insensitive fuzzy contains)
- Requires at least one of: deliverable keyword overlap, thread continuity, recipient match
- Evidence strength: strong (deliverable + thread OR outbound+attachment+recipient) / moderate (one signal) / weak (never generated in production)

**scorer.py** — `CompletionScore` dataclass + `score_evidence()`
- `delivery_confidence`: base (strong=0.85, moderate=0.65, weak=0.40) + adjustments (+0.05 attachment bonus, -0.10 review/investigate, -0.15 external email non-outbound)
- `completion_confidence`: delivery × type multiplier (send/share/introduce=0.95, review/investigate=0.70, follow_up/update/coordinate=0.80, other=0.75)
- `recipient_match_confidence`: explicit=0.90, fuzzy=0.65, no target=0.50
- `artifact_match_confidence`: deliverable+attachment=0.90, deliverable-only=0.70, no deliverable=0.50, pattern-only=0.40
- `closure_readiness_confidence`: delivery×0.5 + recipient×0.3 + artifact×0.2

**updater.py** — `apply_completion_result()` + `apply_auto_close()`
- Thresholds: active→delivered requires delivery_confidence ≥ 0.65 AND evidence_strength != "weak"
- Log-only zone: 0.40–0.65 → CommitmentSignal written, no transition
- No-op guards: closed → complete no-op; delivered → signal only (no duplicate transition)
- Insert-or-ignore: checks for existing CommitmentSignal before writing
- Sets `commitment.delivered_at` on active→delivered transition

**detector.py** — `run_completion_detection()` + `run_auto_close_sweep()`
- Pre-loads origin thread_ids via `_load_origin_thread_ids()` for thread continuity matching
- Auto-close: queries delivered commitments with `delivered_at` set, applies Python-side time + confidence checks

### Tasks: `app/tasks.py`
- New `run_completion_sweep` Celery task on 10-minute beat schedule
- Sweep A: processes source_items ingested in last 30 minutes (30-min window for beat jitter overlap)
- Sweep B: auto-closes delivered commitments exceeding their threshold
- Session-per-item for Sweep A to limit transaction scope

---

## No-regression status
- `pytest tests/services/test_detection.py` — 56 passed
- `pytest tests/services/test_clarification.py` — 90 passed
- `pytest tests/services/test_completion.py` — 32 passed
- No new imports into Phase 03 or 04 service files
- `ruff check app/` — clean
