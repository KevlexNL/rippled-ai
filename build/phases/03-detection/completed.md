# Phase 03 — Detection Pipeline: Completed Files

**Phase:** 03-detection
**Date completed:** 2026-03-11 (initial), 2026-03-22 (documentation update)
**Status:** Complete

---

## Core Detection Service — `app/services/detection/`

| File | Purpose | Lines |
|------|---------|-------|
| `__init__.py` | Public API exports: `run_detection`, `run_tier1`, `should_skip_detection`, audit functions | 35 |
| `detector.py` | Main detection orchestration — loads item, normalizes, runs patterns, creates candidates with savepoints | 377 |
| `patterns.py` | Trigger pattern definitions (TriggerPattern dataclass) organized by source type and category | 502 |
| `context.py` | Context window extraction per source type (meeting turns, Slack threads, email direction) | 210 |
| `audit.py` | Detection audit logging — tier tracking, cost estimation, prompt versioning | 128 |
| `profile_matcher.py` | Tier 1 profile-based pattern matching (learning loop integration) | ~140 |
| `seed_detector.py` | LLM-assisted seed detection for building user commitment profiles | ~650 |
| `learning_loop.py` | Profile update logic after LLM and dismissal events | ~180 |

---

## Celery Task Integration — `app/tasks.py`

- `detect_commitments(source_item_id)` — Celery task with `max_retries=3`, calls `run_detection` with sync session
- `detection_sweep()` — Periodic task (every 5 minutes) for catching missed items
- `model_detection_sweep()` — Periodic task (every 10 minutes) for LLM-assisted detection

---

## Test Files — `tests/services/`

| File | Purpose | Test Count |
|------|---------|------------|
| `test_detection.py` | Core detection: all trigger classes, source-specific patterns, context extraction, confidence scoring, priority elevation, observation windows, suppression, re-analysis flags | 107 |
| `test_seed_detector.py` | Seed/LLM detection: prompt construction, response parsing, profile building, code fence stripping, version tracking | ~75 |
| `test_detection_audit.py` | Audit logging: tier tracking, cost estimation | ~12 |
| `test_detection_signal_integration.py` | End-to-end: detection → candidate → signal integration | ~10 |

**Total: 182 tests passing**

---

## Coverage (Core Phase 03 Modules)

| Module | Coverage |
|--------|----------|
| `patterns.py` | 100% |
| `context.py` | 99% |
| `audit.py` | 100% |
| `detector.py` | 84% |
| `__init__.py` | 100% |

Core detection module coverage exceeds 80% target.

---

## Schema Migration

- Added columns to `commitment_candidates`: `trigger_class`, `is_explicit`, `priority_hint`, `commitment_class_hint`, `context_window` (JSONB), `linked_entities` (JSONB), `observe_until`, `flag_reanalysis`, `source_type`
- Added `detection_method` column for tier tracking
- Added `DetectionAudit` table for audit trail

---

## Database Session Layer

- `app/db/session.py` — Sync SQLAlchemy engine + session factory for Celery workers

---

## Static Analysis Results

- `ruff check app/services/detection/` — All checks passed, zero findings
- No critical security findings in detection module

---

## Trigger Classes Implemented (from Brief 8 Taxonomy)

| Category | Patterns | Source |
|----------|----------|--------|
| `explicit_self_commitment` | I'll, I will, let me, I'll handle, I'll revise, I'll introduce | All / Email |
| `explicit_collective_commitment` | we'll | All |
| `request_for_action` | can you, will you | All |
| `accepted_request` | yep, yes, sure, will do, on it | Slack |
| `implicit_next_step` | next step, action item, we should, let's have [name] | Meeting |
| `implicit_unresolved_obligation` | from our side, someone should/needs to, who's going to, can someone | Meeting |
| `small_practical_commitment` | I'll check, let me look/check/confirm | Slack |
| `obligation_marker` | needs to, has to, must | All |
| `pending_obligation` | still needs to | All |
| `follow_up_commitment` | follow up on/with, follow up (bare), checking in on | All |
| `delivery_signal` | just sent, done, handled, completed, please find attached | All / Slack / Email |
| `blocker_signal` | still waiting on, blocked on/by | All |
| `owner_clarification` | actually, instead, that's on me, I'll take that | All |
| `deadline_change` | moving this to, pushing the deadline, rescheduling | All / Email |

**Total: 14 trigger classes across 30+ patterns**

---

## Completion Criteria Checklist

- [x] Phase 1 skill-review.md written
- [x] Phase 2 skill-review.md written
- [x] Critical issues from reviews documented (credential encryption, lifecycle state machine, batch rollback)
- [x] interpretation.md written and approved
- [x] All trigger classes from Brief 8 implemented
- [x] Source-specific detection for meeting/slack/email
- [x] Context window extraction working
- [x] Celery task triggers on source_item creation
- [x] Tests passing (182 tests, >80% coverage on core detection)
- [x] Static analysis passes with no critical findings
- [x] decisions.md documents all choices
- [x] completed.md lists all files
