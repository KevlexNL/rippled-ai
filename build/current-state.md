# Rippled.ai — Current State (2026-03-13)

## Summary

**Status:** Cycle A complete (7 phases delivered) → Cycle B, Phase B1 (platform review in progress)

**Last validated:** 2026-03-13 11:30 UTC — Phase 07 (connectors) validation complete. All 320 tests passing, no regressions. Frontend (Phase 08) shipped but not yet fully validated.

**Architecture:** FastAPI (Python) + PostgreSQL (Supabase) + Celery (Redis) + React frontend (vite) on Railway.

---

## Architecture Delivered

### Phase 01 — Schema
**Completion:** 2026-03-09

Database schema for commitments, sources, candidates, lifecycle, evidence tracking.

**Key objects:**
- `commitments` — core domain object (id, owner, description, class, state, confidence, dates, evidence links)
- `commitment_candidates` — raw signals before promotion to commitment (trigger_class, confidence_score, source link, observe_until)
- `commitment_evidence` — linked evidence items per commitment (message_id, transcript_id, channel, timestamp)
- `commitment_sources` — abstract source items (email, Slack message, meeting)
- `commitment_source_items` — cross-source unification layer (abstract edges across email ↔ Slack ↔ meetings)
- `clarifications` — ambiguity objects awaiting resolution (field, type, candidates, status)
- `audit_log` — immutable record of all state transitions

**Decision highlights:**
- Hybrid schema: explicit columns for queryable/filterable fields, JSONB for unstructured context
- `confidence_score` NUMERIC(4,3) — enables fine-grained sorting
- `observe_until` TIMESTAMPTZ on candidates — supports observation window compliance
- Reversible state transitions per lifecycle rules
- Full audit trail per row

**Migrations:** Alembic setup with auto-detected migrations directory; all migrations applied to dev/prod.

---

### Phase 02 — API Scaffold
**Completion:** 2026-03-09

FastAPI REST API with structured request/response models, dependency injection, error handling.

**Key endpoints:**
- `POST /commitments` — create new commitment manually
- `GET /commitments` — list (main/shortlist/clarifications surfaces)
- `GET /commitments/:id` — retrieve one
- `PATCH /commitments/:id` — update state/fields
- `DELETE /commitments/:id` — soft delete
- `GET /commitments/:id/history` — full audit trail
- `POST /webhook/email` — inbound email signal webhook
- `POST /webhook/slack` — inbound Slack signal webhook
- `POST /webhook/meetings` — inbound meeting transcript webhook
- `GET /health` — readiness check

**Structured models:**
- Pydantic for all request/response contracts
- Enum types for states, classes, priority dimensions
- Validation rules baked into models

**Error handling:**
- Custom exception handlers (400, 404, 422, 500, etc.)
- Structured error responses with request_id tracing

**Documentation:**
- Auto-generated OpenAPI/Swagger at `/docs`
- Markdown docstrings on all routes

---

### Phase 03 — Detection Pipeline
**Completion:** 2026-03-11

Core commitment signal detection. Takes raw Slack/email/meeting text and identifies commitment candidates.

**Delivered:**
- `DetectionAnalyzer` — pattern matching + heuristics for commitment signals
- Signal types: explicit commitments ("I'll do X"), implicit signals ("will handle"), edge cases ("I'll try")
- Confidence scoring: 0.85 (explicit + external), 0.75 (explicit internal), 0.50–0.60 (implicit), 0.35–0.45 (edge)
- `observe_until` window assignment (1–3 days depending on source/direction)
- Batched Celery ingestion (`detect_commitments` task)
- Stored in `commitment_candidates` with full context_window JSONB (prepared for future model-assisted re-analysis)

**Decision:**
- Deterministic-only for MVP (model assistance deferred post-MVP)
- One task per source item (isolated failure handling)
- `context_window` JSONB stores all raw data for future model calls

---

### Phase 04 — Clarification
**Completion:** 2026-03-12

Identifies ambiguous candidates and surfaces resolution workflow.

**Delivered:**
- `ClarificationAnalyzer` — detects ambiguity types (owner resolution, object inference, deadline ambiguity, etc.)
- Candidate promotion rules: promote only if confidence ≥ 0.55 OR complexity permits clarification
- `ClarificationPromover` — moves qualified candidates → `clarifications` table
- Clarification suggestion engine: field-specific candidate values + null/empty/optional flags
- Celery integration: scheduled clarification sweep jobs
- Observation windows honored (no premature surfacing)

**Key rules:**
- "We" ownership never auto-resolves (stays null)
- Deadline inference only on explicit date signals
- Candidates below 0.55 that are complex → clarification (not discarded)
- Clarification suggestions pulled from context_window + linked evidence

---

### Phase 05 — Completion Detection
**Completion:** 2026-03-12

Infers when commitments have been delivered or closed.

**Delivered:**
- `CompletionMatcher` — searches evidence for delivery signals (completion phrases, explicit closure, time-based inference)
- `CompletionScorer` — assigns confidence to completion candidates
- `CompletionUpdater` — moves commitment from `active` → `delivered` → `closed` (with reversibility support)
- Evidence-based state transition rules per lifecycle brief
- Celery sweep job for continuous completion detection
- Audit trail for every transition

**Key decision:**
- Delivery ≠ Closure: distinct states with distinct thresholds
- Reversibility supported (back to `active` if new evidence contradicts closure)

---

### Phase 06 — Surfacing & Prioritization
**Completion:** 2026-03-13

Determines which commitments get shown to the user and in what order.

**Delivered:**
- `CommitmentClassifier` — routes each commitment to Main / Shortlist / Clarifications surface
- Routing rules: Main (big promises, external signals, high-priority), Shortlist (internal, small but cognitively meaningful), Clarifications (needs resolution)
- `CommitmentScorer` — assigns priority rank using multi-dimensional scoring (urgency, consequence, visibility, time-until-due)
- Priority ≠ Confidence: high-priority items can have low confidence (clarifications); low-priority items can be high-confidence
- `CommitmentRouter` — distributes commitments across three surfaces
- Celery scheduler for continuous re-scoring and surfacing updates
- Audit logging of all surface changes

**Key outputs:**
- `/commitments?surface=main` returns ordered main view
- `/commitments?surface=shortlist` returns ordered shortlist
- `/commitments?surface=clarifications` returns unresolved items
- Each surface sorted by priority score (desc)

---

### Phase 07 — Connectors (Source Integrations)
**Completion:** 2026-03-13

Multi-source ingestion: email (IMAP + webhook), Slack (Events API), meeting transcripts (webhook).

**Delivered:**

**Email:**
- Bidirectional: IMAP for historical fetch + webhook for real-time ingest
- IMAP client: Supabase connection string → direct PostgreSQL ingest
- Webhook endpoint: raw MIME parsing + attachment handling
- Auto-source-creation on first use (smart default email parsing)
- Threading via Message-ID and In-Reply-To headers

**Slack:**
- Events API v3 integration (app-level events)
- Events subscribed: `message.channels`, `message.direct_messages` (filtered)
- Auto-source-creation per workspace + channel
- User resolution (real names mapped from member list)

**Meetings:**
- Webhook ingest for external transcript files
- Auto-source-creation per meeting (from transcript header)
- Speaker attribution from transcript metadata

**Shared:**
- Idempotent source creation (no duplicates per endpoint)
- Error handling with retry (Celery tasks)
- Webhook signature validation (configurable via env)
- Graceful degradation (one source failure doesn't block others)

**Integration test coverage:**
- Email IMAP fetch integration
- Slack event webhook parsing + routing
- Meeting transcript webhook ingest
- Cross-source linking (same person across platforms)

---

### Phase 08 — Frontend (NEW)
**Completion:** 2026-03-13

React + TypeScript dashboard for Rippled.

**Delivered:**
- **Dashboard:** Main / Shortlist / Clarifications tabs with surface filtering
- **Commitment Review:** Detail view for each item (full evidence, history, state machine buttons)
- **Commitment Log:** Historical view of all resolved/closed items
- **Commitment Detail:** Modal or page with full context, evidence links, audit trail
- **Supabase Auth:** Sign-up / Login / OAuth integration (if configured)
- **Real-time updates:** Auto-refresh from API (interval polling or WebSocket-ready)

**Tech stack:**
- Vite (fast dev/build)
- React 18 + TypeScript
- Tailwind CSS for styling
- Supabase client for auth
- Axios for API calls

**Routes:**
- `/` — dashboard (main/shortlist/clarifications tabs)
- `/commitment/:id` — detail view
- `/history` — closed/delivered log
- `/login` — auth entry point

---

## Running State

### Database
- PostgreSQL via Supabase (connection string in `.env`)
- All migrations applied automatically on API startup (Alembic)
- Test database (optional) isolated from production

### API Server
- FastAPI + Uvicorn
- Startup command: `uvicorn app.main:app --reload` (dev) or `--host 0.0.0.0 --port 8000` (prod)
- OpenAPI docs at `/docs`
- Health check at `/health`

### Background Jobs
- Celery worker + Redis
- Scheduled tasks:
  - Commitment candidate detection (per-source-item)
  - Clarification analysis (every 5 min)
  - Completion detection sweep (every 10 min)
  - Surface routing + scoring (every 15 min)
  - Observation window expiry checks (every 30 min)

### Frontend
- Built with `npm run build` → static assets to `/frontend/dist`
- Dev server: `npm run dev` in `/frontend`
- Served from root `/` via FastAPI `StaticFiles` (production)

### Deployment
- Railway.app integration via `railway.toml`
- Env vars set in Railway dashboard (never in `.env`)
- Auto-deploy on push to `main`
- Worker processes: API + Celery (separate dynos)

---

## Testing

**Coverage:**
- 320 tests across API, database, services, and integration layers
- Unit tests: detection heuristics, confidence scoring, state transitions
- Integration tests: end-to-end flows (ingest → detect → promote → clarify → surface)
- API tests: all webhook endpoints, CRUD operations, error cases

**Test runner:** pytest (in `.venv`)

**Current status:** All tests passing as of Phase 07 validation. Phase 08 frontend tests included.

---

## Known Limitations (MVP Constraints)

1. **Detection:** Deterministic only (model assistance deferred)
2. **Clarification:** Suggestion engine uses stored context + simple heuristics (no active model calls)
3. **Frontend:** Basic dashboard (no advanced filtering, export, or custom views)
4. **Connectors:** Email IMAP requires relay; Slack requires app token; meetings require webhook POST
5. **Observation windows:** Hard-coded per source type (no customization yet)
6. **Multi-user:** Not scoped; single user per deployment assumed

---

## Code Organization

```
app/
  main.py                      # FastAPI app entry
  core/
    config.py                  # Pydantic settings
  api/
    routes/
      commitments.py           # CRUD
      webhooks.py              # Email/Slack/meetings ingest
      health.py                # Health check
  models/
    commitment.py              # Domain models
    state.py                   # State machine enums
    surface.py                 # Surfacing types
  db/
    client.py                  # Supabase client
    session.py                 # SQLAlchemy async + sync engines
  services/
    detection.py               # Commitment detection
    clarification.py           # Ambiguity resolution
    completion.py              # Completion inference
    surfacing.py               # Prioritization + routing
  tasks/
    detection.py               # Celery task: detect_commitments
    clarification.py            # Celery task: analyze_clarifications
    completion.py              # Celery task: detect_completions
    surfacing.py               # Celery task: route_and_score

migrations/
  alembic/
    versions/                  # Timestamped migration files

tests/
  api/
    test_commitments_*.py      # CRUD tests
    test_webhook_*.py          # Webhook tests
  services/
    test_detection.py          # Detection heuristics
    test_clarification.py      # Ambiguity logic
    test_completion.py         # State transitions
  integration/
    test_end_to_end.py         # Full pipelines

frontend/
  src/
    App.tsx                    # Root component
    pages/
      Dashboard.tsx            # Main view
      CommitmentDetail.tsx     # Detail modal/page
      HistoryLog.tsx           # Closed items
    components/
      CommitmentCard.tsx       # List item
      SurfaceFilter.tsx        # Surface selector
    api/
      client.ts                # Axios instance
      types.ts                 # Response models
    auth/                      # Supabase auth

docs/
  API.md                       # Endpoint reference
  Architecture.md              # System design overview
  DESIGN_DECISIONS.md          # Detailed rationale
```

---

## Deliverables Status

| Phase | Name | Status | Validated | Notes |
|-------|------|--------|-----------|-------|
| 01 | Schema | ✅ | 2026-03-09 | Core domain model, migrations |
| 02 | API Scaffold | ✅ | 2026-03-09 | REST endpoints, error handling |
| 03 | Detection | ✅ | 2026-03-11 | Commitment signal detection pipeline |
| 04 | Clarification | ✅ | 2026-03-12 | Ambiguity analysis + suggestions |
| 05 | Completion | ✅ | 2026-03-12 | State machine + evidence tracking |
| 06 | Surfacing | ✅ | 2026-03-13 | Prioritization + surface routing |
| 07 | Connectors | ✅ | 2026-03-13 | Email/Slack/meetings integration |
| 08 | Frontend | ✅ | *pending* | Dashboard, detail, history views |

---

## Next Steps (Cycle B1 → B2)

**B1 (now):** Document current state ← **YOU ARE HERE**

**B2:** Compare to vision
- Read original briefs (01-10)
- Identify gaps, deviations, drift
- Document in `vision-delta.md`

**B3:** Assess decisions
- For each gap: intentional or drift?
- Decisions: document rationale in `decisions.md`
- Drift: flag for correction

**B4:** Corrections work order
- If gaps found: create + execute WO
- Do not advance until corrections complete

Then → Cycle C (phase planning) or deploy.

---

*This document is a snapshot of what's been delivered. Read it with the original briefs (briefs/ folder) to assess completeness.*
