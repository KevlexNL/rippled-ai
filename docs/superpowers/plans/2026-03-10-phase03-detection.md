# Phase 03 Detection Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the commitment detection pipeline that processes SourceItems into CommitmentCandidates using regex patterns.

**Architecture:** A Celery task calls `run_detection(source_item_id, db)` which loads the SourceItem, applies suppression + trigger patterns, and creates CommitmentCandidate rows using savepoints for isolation. All detection is deterministic regex — no ML/LLM in Phase 03.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 (sync + async), Alembic, Celery, psycopg2-binary, pytest

---

## Chunk 1: Schema + Infrastructure

### Task 1: Alembic Migration

**Files:**
- Create: `migrations/versions/<rev>_phase03_detection_columns.py`

- [ ] Write migration adding 9 columns + 3 indexes to `commitment_candidates`
- [ ] Run `alembic upgrade head` — verify clean apply
- [ ] Commit: `git commit -m "feat: Phase 03 migration — detection columns on commitment_candidates"`

### Task 2: ORM Model Update

**Files:**
- Modify: `app/models/commitment_candidate.py`

- [ ] Add 9 new mapped columns (trigger_class, is_explicit, priority_hint, commitment_class_hint, context_window, linked_entities, observe_until, flag_reanalysis, source_type)
- [ ] Update `__table_args__` with new CheckConstraints + Indexes
- [ ] Commit: `git commit -m "feat: add Phase 03 detection columns to CommitmentCandidate ORM"`

### Task 3: Config + Sync Session

**Files:**
- Modify: `app/core/config.py`
- Create: `app/db/session.py`

- [ ] Add `database_url_sync` field to Settings (strips `+asyncpg`, uses psycopg2)
- [ ] Create `app/db/session.py` with `get_sync_session()` context manager
- [ ] Commit: `git commit -m "feat: add sync session factory for Celery workers"`

---

## Chunk 2: Detection Service (TDD)

### Task 4: Tests for patterns.py

**Files:**
- Create: `tests/services/test_detection.py` (patterns tests only first)
- Create: `tests/__init__.py`, `tests/services/__init__.py`

- [ ] Write failing tests for `get_patterns_for_source()` (meeting/slack/email patterns)
- [ ] Run tests — verify they fail
- [ ] Implement `app/services/detection/patterns.py`
- [ ] Run tests — verify they pass
- [ ] Commit

### Task 5: Tests for context.py

- [ ] Write failing tests for `extract_context()` — meeting speaker turns, slack thread, email direction
- [ ] Run tests — verify they fail
- [ ] Implement `app/services/detection/context.py`
- [ ] Run tests — verify they pass
- [ ] Commit

### Task 6: Tests for detector.py (all 14 required tests)

- [ ] Write all 14 failing tests from brief.md Section 6
- [ ] Run tests — verify they fail
- [ ] Implement `app/services/detection/detector.py`
- [ ] Create `app/services/detection/__init__.py`
- [ ] Run tests — verify all 14 pass
- [ ] Commit

### Task 7: Celery Task + Completion

**Files:**
- Modify: `app/tasks.py`
- Create: `build/phases/03-detection/completed.md`
- Create: `build/phases/03-detection/completed.flag`

- [ ] Replace stub `detect_commitments` with real implementation
- [ ] Run full test suite — all green
- [ ] Write `build/phases/03-detection/completed.md`
- [ ] Create `build/phases/03-detection/completed.flag`
- [ ] Final commit
