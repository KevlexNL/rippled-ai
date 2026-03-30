# Signal Trace Inspector Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trace CLI, micro-seed script, and Signal Lab UI for inspecting the detection pipeline step-by-step without full reseeds.

**Architecture:** Three deliverables share a core trace service (`app/services/trace/tracer.py`) that walks a source_item through each pipeline stage (raw -> normalized -> pattern -> LLM -> extraction -> candidate -> clarification -> commitment) and returns structured results. The CLI and API both consume this service. The frontend Signal Lab page calls the API.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind (frontend), SQLAlchemy sync sessions (scripts)

---

## File Structure

### New Files
- `app/services/trace/__init__.py` — exports `trace_source_item`, `fetch_samples`
- `app/services/trace/tracer.py` — core trace logic
- `app/api/routes/lab.py` — Lab API endpoints
- `scripts/trace_signal.py` — Trace CLI
- `scripts/micro_seed.py` — Micro-seed CLI
- `frontend/src/screens/SignalLabScreen.tsx` — Signal Lab UI
- `frontend/src/api/lab.ts` — Lab API client
- `tests/unit/services/trace/test_tracer.py` — Trace service tests

### Modified Files
- `app/main.py` — register lab router
- `frontend/src/App.tsx` — add /lab route

---

## Chunk 1: Backend (Trace Service + API + Scripts)

### Task 1: Core Trace Service

**Files:** `app/services/trace/__init__.py`, `app/services/trace/tracer.py`

The trace service inspects DB state for a given source_item_id and reconstructs what happened at each pipeline stage:

1. **Raw** — load SourceItem: sender, direction, content, source_type
2. **Normalization** — apply suppression patterns, show before/after
3. **Pattern detection** — run patterns, show which fired with confidence
4. **LLM detection** — look up DetectionAudit for prompt/response
5. **Extraction** — show CommitmentCandidate fields if any exist
6. **Candidate decision** — promoted? why/why not? confidence
7. **Clarification** — show Clarification record if exists
8. **Final state** — show Commitment record if exists

Also: `fetch_samples(source_type, count, db)` — get recent source_items for sampling.

### Task 2: Trace CLI (`scripts/trace_signal.py`)

Accepts: `--id`, `--sample --type --count`, `--json`
Uses `get_sync_session()` + `trace_source_item()`.
Terminal output: colored stage headers, indented details.

### Task 3: Micro-seed (`scripts/micro_seed.py`)

Follows `full_reseed.py` phase 3+4 pattern but scoped:
- `--type email --count 5` — N recent unprocessed of type
- `--all --count-per-type 3` — 3 of each type
- `--ids <id1> <id2>` — specific items
Additive only, idempotent via `seed_processed_at`.

### Task 4: Lab API Routes

- `GET /lab/source-items?type=email&limit=20` — list recent source_items
- `POST /lab/trace` body: `{source_item_ids: []}` — run traces, return results

### Task 5: Frontend Signal Lab

Two-panel layout at `/lab`:
- Left: source type tabs, item list with checkboxes, "Run Trace" button
- Right: accordion per pipeline stage with color coding

### Task 6: Tests

Unit tests for tracer using mocked DB objects.
