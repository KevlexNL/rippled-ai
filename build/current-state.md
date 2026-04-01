# Rippled.ai — Current State (2026-04-01)

## Summary

**Status:** Cycle A complete (9 phases) → Cycle C complete (C1–C6) → Cycle D fix-iteration complete (RI-F01 through RI-F11) → Cycle B platform review in progress (B1)

**Last validated:** 2026-04-01 — All Cycle D fixes confirmed deployed. Production healthy at `rippled-ai-production.up.railway.app`.

**Architecture:** FastAPI (Python 3.11+) + PostgreSQL (Supabase) + Celery (Redis) + React frontend (Vite) + Twilio/Gemini voice bridge. Deployed on Railway.

---

## Architecture Delivered

### Phase 01 — Schema
**Completion:** 2026-03-09

Database schema for commitments, sources, candidates, lifecycle, evidence tracking.

**Key objects:**
- `commitments` — core domain object (id, owner, description, class, state, confidence, dates, evidence links, context_tags JSONB, speech_act, structure_complete, due_precision)
- `commitment_candidates` — raw signals before promotion to commitment (trigger_class, confidence_score, source link, observe_until)
- `commitment_evidence` — linked evidence items per commitment (message_id, transcript_id, channel, timestamp)
- `commitment_sources` — abstract source items (email, Slack message, meeting)
- `commitment_source_items` — cross-source unification layer (abstract edges across email ↔ Slack ↔ meetings)
- `commitment_signals` — origin signal records created on candidate promotion (fixes timestamp display)
- `clarifications` — ambiguity objects awaiting resolution (field, type, candidates, status)
- `audit_log` — immutable record of all state transitions
- `normalized_signals` — standardized signal format across all connectors
- `raw_signal_ingests` — raw inbound data before normalization
- `normalization_runs` — tracking for normalization batch runs
- `users` — user model for auth and identity
- `common_terms` — term/alias vocabulary for entity resolution

**Decision highlights:**
- Hybrid schema: explicit columns for queryable/filterable fields, JSONB for unstructured context
- `confidence_score` NUMERIC(4,3) — enables fine-grained sorting
- `observe_until` TIMESTAMPTZ on candidates — supports observation window compliance
- `context_tags` JSONB on commitments — flexible context metadata
- `due_precision` enum — captures date specificity (day, week, month, quarter)
- `structure_complete` boolean — gates promotion eligibility
- Reversible state transitions per lifecycle rules
- Full audit trail per row

**Migrations:** Alembic with migration tracking mechanism (applied + verified on deploy).

---

### Phase 02 — API Scaffold
**Completion:** 2026-03-09

FastAPI REST API with structured request/response models, dependency injection, error handling.

**Key endpoints (original):**
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

**Additional endpoints (Cycles C–D):**
- `GET /api/v1/admin/*` — admin dashboard, review queue, audit sampling
- `GET /api/v1/digest/*` — daily digest generation
- `GET /api/v1/events/*` — event timeline, post-event resolution
- `GET /api/v1/stats/*` — commitment stats and counts
- `GET /api/v1/contexts/*` — context management
- `GET /api/v1/identity/*` — identity/entity resolution settings
- `GET /api/v1/terms/*` — common terms vocabulary CRUD
- `GET /api/v1/user-settings/*` — user preferences
- `GET /api/v1/surface/*` — surfacing views
- `GET /api/v1/lab/*` — Signal Lab / trace inspector UI
- `POST /api/v1/voice/query` — voice query endpoint
- `POST /api/v1/debug/pipeline` — debug pipeline endpoint (diagnose detection flow)
- `GET /api/v1/report/*` — reporting

**Structured models:**
- Pydantic for all request/response contracts
- Enum types for states, classes, priority dimensions, due_precision
- Validation rules baked into models

**Error handling:**
- Custom exception handlers (400, 404, 422, 500, etc.)
- Structured error responses with request_id tracing
- Auth error clarity improvements (Cycle D)

**Documentation:**
- Auto-generated OpenAPI/Swagger at `/docs`

---

### Phase 03 — Detection Pipeline
**Completion:** 2026-03-11 | **Enhanced:** Cycle C1 (model detection) + Cycle D (fixes)

Core commitment signal detection. Takes raw Slack/email/meeting text and identifies commitment candidates.

**Delivered (original — deterministic):**
- `DetectionAnalyzer` — pattern matching + heuristics for commitment signals
- Signal types: explicit commitments ("I'll do X"), implicit signals ("will handle"), edge cases ("I'll try")
- Confidence scoring: 0.85 (explicit + external), 0.75 (explicit internal), 0.50–0.60 (implicit), 0.35–0.45 (edge)
- `observe_until` window assignment (1–3 days depending on source/direction)
- Batched Celery ingestion (`detect_commitments` task)

**Enhanced (Cycle C1 — model-assisted detection):**
- `model_detection.py` — LLM-based commitment detection alongside deterministic
- `hybrid_detection.py` — hybrid pipeline combining deterministic + model results
- `llm_judge.py` — LLM judge for confidence calibration
- Entity extraction: always-on (Cycle D fix — previously intermittent)
- `speech_act`, `structure_complete`, `deliverable` fields populated on promotion
- Fragment gate: rejects short text fragments (<10 chars) from promotion
- `seed_processed_at` stamping prevents detection rescan loops
- Meeting-specific LLM detection pipeline

**Decision:**
- Hybrid approach: deterministic for speed, model for nuance
- Entity extraction runs on every candidate (not gated behind conditions)
- `resolved_owner` fallback ensures owner is always populated

---

### Phase 04 — Clarification
**Completion:** 2026-03-12

Identifies ambiguous candidates and surfaces resolution workflow.

**Delivered:**
- `ClarificationAnalyzer` — detects ambiguity types (owner resolution, object inference, deadline ambiguity, etc.)
- Candidate promotion rules: promote only if confidence ≥ 0.55 OR complexity permits clarification
- Clarification suggestion engine: field-specific candidate values + null/empty/optional flags
- Celery integration: scheduled clarification sweep jobs
- Observation windows honored (no premature surfacing)

**Key rules:**
- "We" ownership never auto-resolves (stays null)
- Deadline inference only on explicit date signals
- Candidates below 0.55 that are complex → clarification (not discarded)

---

### Phase 05 — Completion Detection
**Completion:** 2026-03-12

Infers when commitments have been delivered or closed.

**Delivered:**
- `CompletionMatcher` — searches evidence for delivery signals
- `CompletionScorer` — assigns confidence to completion candidates
- `CompletionUpdater` — moves commitment from `active` → `delivered` → `closed` (with reversibility)
- Evidence-based state transition rules per lifecycle brief
- Celery sweep job for continuous completion detection
- Audit trail for every transition

**Key decision:**
- Delivery ≠ Closure: distinct states with distinct thresholds
- Reversibility supported (back to `active` if new evidence contradicts closure)

---

### Phase 06 — Surfacing & Prioritization
**Completion:** 2026-03-13 | **Enhanced:** Cycle D (fixes)

Determines which commitments get shown to the user and in what order.

**Delivered:**
- `CommitmentClassifier` — routes each commitment to Main / Shortlist / Clarifications surface
- `CommitmentScorer` / `priority_scorer.py` — multi-dimensional scoring (urgency, consequence, visibility, time-until-due)
- `surfacing_router.py` + `surfacing_runner.py` — distributes commitments across surfaces
- `structure_complete` gating — only fully structured commitments are surfaced (Cycle D fix)
- Confidence scoring threshold enforcement (Cycle D fix)
- Stale discard sweep + routing backlog cleanup (Cycle D fix)
- `surfacing_audit` with `user_id` column for audit tracking

**Key outputs:**
- `/commitments?surface=main` returns ordered main view
- `/commitments?surface=shortlist` returns ordered shortlist
- `/commitments?surface=clarifications` returns unresolved items
- Each surface sorted by priority score (desc)

---

### Phase 07 — Connectors (Source Integrations)
**Completion:** 2026-03-13 | **Enhanced:** Cycle C + D

Multi-source ingestion: email (IMAP + webhook), Slack (Events API + thread enrichment), meeting transcripts (webhook + LLM pipeline).

**Delivered:**

**Email:**
- Bidirectional: IMAP for historical fetch + webhook for real-time ingest
- Newsletter/noreply sender filter (widened in Cycle D to catch plurals/prefixed patterns)
- Source error isolation for email processing failures

**Slack:**
- Events API integration
- Slack-specific prompt overlay for LLM detection
- Thread enrichment — fetches full thread context for better detection
- Auto-source-creation per workspace + channel

**Meetings:**
- Webhook ingest for external transcript files
- Meeting-specific LLM detection pipeline
- Speaker attribution from transcript metadata
- `NormalizedSignal` WO fields populated in meeting normalizers

**Google Calendar:**
- `google_calendar.py` connector (event integration)

**Shared:**
- `NormalizedSignal` model — standardized format across all sources
- `normalization/` service layer for signal normalization
- Idempotent source creation (no duplicates per endpoint)
- Error handling with retry (Celery tasks)
- Webhook signature validation

---

### Phase 08 — Frontend
**Completion:** 2026-03-13 | **Enhanced:** Cycles C3–C6

React + TypeScript dashboard for Rippled.

**Delivered (original):**
- **Dashboard:** Main / Shortlist / Clarifications tabs with surface filtering
- **Commitment Review:** Detail view for each item (full evidence, history, state machine buttons)
- **Commitment Log:** Historical view of all resolved/closed items
- **Supabase Auth:** Sign-up / Login / OAuth integration

**Enhanced (Cycles C–D):**
- **Event timeline:** Linked events view with post-event banner
- **Admin panel:** Admin review queue, audit sampling
- **User settings:** Preferences page
- **Identity settings:** Entity resolution configuration
- **Common terms vocabulary:** Term/alias management UI
- **Signal Lab / Trace Inspector:** Debug UI for tracing signal detection flow
- **Onboarding tour:** Interactive onboarding component
- **Context selector:** Context assignment UI
- **Delivery actions + badge:** Delivery state management in UI
- **Validation feedback:** Auth error clarity in Log Commitment modal
- **Source badges + grouping:** Visual source identification

**Tech stack:**
- Vite + React 18 + TypeScript
- Tailwind CSS
- Supabase client for auth
- Axios for API calls

---

### Phase 09 — Onboarding
**Completion:** 2026-03-15 (approx)

User onboarding flow for first-time setup.

**Delivered:**
- `OnboardingTour.tsx` component — interactive walkthrough
- Source connection setup guidance
- Initial commitment surface orientation

---

### Cycle C — Feature Phases

#### C1 — Model Detection
LLM-assisted commitment detection running alongside deterministic pipeline. See Phase 03 enhanced section.

#### C2 — Daily Digest
- `digest.py` service — generates daily commitment digest
- `/api/v1/digest/*` endpoints
- Admin review integration for digest approval

#### C3 — Events
- `events.py` route — event timeline endpoints
- `event_linker.py` — links events to commitments
- `post_event_resolver.py` — resolves commitments after events occur
- `PostEventBanner.tsx` — UI for post-event resolution
- Meeting webhook improvements for C6

#### C4 — Admin
- `admin.py` + `admin_review.py` routes — admin dashboard and review queue
- Audit sampling endpoints
- Stats endpoint for commitment counts

#### C5 — User UI
- `user_settings.py` route — user preferences
- `clarifications.py` route — clarification management
- Delivery state management
- Linked events in user views

#### C6 — Fixes
- Meeting webhook fixes
- Celery readiness improvements
- Various bug fixes across the platform

---

### Cycle D — Fix Iteration (RI-F01 through RI-F11)
**Completion:** 2026-04-01

Systemic fix cycle addressing production issues discovered during real usage.

**Fixes delivered:**
- **RI-F01:** Entity extraction made always-on + resolved_owner fallback
- **RI-F02:** Confidence surfacing and threshold corrections
- **RI-F03:** `structure_complete` backfill for 373 blocked commitments + migration
- **RI-F04:** Routing backlog cleanup — stale discard sweep, ValueError handling
- **RI-F05:** Fragment gate — reject <10 char text from promotion
- **RI-F06:** Eligibility filter corrections
- **RI-F07:** Signal link schema — CommitmentSignal created on promotion (fixes timestamps)
- **RI-F08:** Classification/extraction pipeline fixes (speech_act, structure_complete, deliverable populated)
- **RI-F09:** Newsletter/noreply sender filter widened
- **RI-F10:** Context UX fix — context_tags JSONB, auto-assignment
- **RI-F11:** Debug pipeline endpoint (`POST /api/v1/debug/pipeline`)

**Additional operational work:**
- Full DB reset + comprehensive re-seed
- Migration tracking mechanism
- Detection rescan loop fix (seed_processed_at stamping)
- Validation feedback and auth error clarity
- `python-multipart` dependency for voice route

---

## Running State

### Database
- PostgreSQL via Supabase (connection string in `.env`)
- All migrations applied via Alembic with migration tracking mechanism
- Production catchup migrations for `context_tags`, `due_precision`, `structure_complete`

### API Server
- FastAPI + Uvicorn
- Startup command: `uvicorn app.main:app --reload` (dev) or `--host 0.0.0.0 --port 8000` (prod)
- OpenAPI docs at `/docs`
- Health check at `/health`
- Debug pipeline at `/api/v1/debug/pipeline`

### Background Jobs
- Celery worker + Redis
- Scheduled tasks:
  - Commitment candidate detection (per-source-item)
  - Model-assisted detection (hybrid pipeline)
  - Clarification analysis (every 5 min)
  - Completion detection sweep (every 10 min)
  - Surface routing + scoring (every 15 min)
  - Observation window expiry checks (every 30 min)
  - Stale discard sweep (routing backlog cleanup)
  - Daily digest generation

### Frontend
- Built with `npm run build` → static assets to `/frontend/dist`
- Dev server: `npm run dev` in `/frontend`
- Served from root `/` via FastAPI `StaticFiles` (production)

### Voice Bridge
- Twilio ↔ Gemini Live voice bridge service
- `app/voice_bridge/` — standalone service (audio_pipe, gemini_client, twilio_handler)
- `POST /api/v1/voice/query` — voice query endpoint

### Deployment
- Railway.app integration
- Production URL: `rippled-ai-production.up.railway.app`
- Env vars set in Railway dashboard (never in `.env`)
- Auto-deploy on push to `main`
- Worker processes: API + Celery (separate dynos)

---

## Testing

**Coverage:**
- 131 test files across API, database, services, connectors, integration, and voice layers
- Unit tests: detection heuristics, confidence scoring, state transitions, entity extraction
- Integration tests: end-to-end flows (ingest → detect → promote → clarify → surface)
- API tests: all webhook endpoints, CRUD operations, admin, digest, events, debug
- Cycle D regression tests: routing backlog, structure_complete backfill, entity extraction always-on, debug pipeline

**Test runner:** pytest

**Current status:** All tests passing as of Cycle D completion (2026-04-01).

---

## Known Limitations (Current)

1. **Multi-user:** Not fully scoped; single primary user per deployment assumed
2. **Connectors:** Email IMAP requires relay; Slack requires app token; meetings require webhook POST
3. **Observation windows:** Hard-coded per source type (no customization yet)
4. **Frontend:** Functional but basic — no advanced filtering, export, or custom views
5. **Voice bridge:** Early stage — Twilio/Gemini integration, not yet production-hardened
6. **Google Calendar:** Connector exists but integration depth TBD

---

## Code Organization

```
app/
  main.py                          # FastAPI app entry
  core/
    config.py                      # Pydantic settings
  api/
    routes/
      commitments.py               # CRUD
      webhooks/                    # Email/Slack/meetings ingest
      admin.py                     # Admin dashboard
      admin_review.py              # Review queue
      candidates.py                # Candidate management
      clarifications.py            # Clarification views
      contexts.py                  # Context management
      debug.py                     # Debug pipeline
      digest.py                    # Daily digest
      events.py                    # Event timeline
      identity.py                  # Identity/entity settings
      integrations.py              # Integration management
      lab.py                       # Signal Lab / Trace Inspector
      report.py                    # Reporting
      source_items.py              # Source item views
      sources.py                   # Source management
      stats.py                     # Stats endpoints
      surface.py                   # Surfacing views
      terms.py                     # Common terms vocabulary
      user_settings.py             # User preferences
      voice.py                     # Voice query endpoint
  connectors/
    email/                         # Email IMAP + webhook
    slack/                         # Slack Events API + thread enrichment
    meeting/                       # Meeting transcript webhook
    google_calendar.py             # Google Calendar connector
    shared/                        # Shared connector utilities
  models/
    commitment.py                  # Core domain model
    commitment_candidate.py        # Candidate model
    commitment_signal.py           # Signal model (origin tracking)
    normalized_signal.py           # Standardized signal format
    raw_signal_ingest.py           # Raw inbound data
    normalization_run.py           # Normalization tracking
    user.py                        # User model
    enums.py                       # State/class enums
    schemas.py                     # Pydantic schemas
    ...                            # Additional domain models
  services/
    detection/                     # Commitment detection (deterministic)
    model_detection.py             # LLM-assisted detection
    hybrid_detection.py            # Hybrid pipeline
    llm_judge.py                   # LLM confidence judge
    clarification/                 # Ambiguity resolution
    completion/                    # Completion inference
    surfacing_router.py            # Surface routing
    surfacing_runner.py            # Surfacing execution
    priority_scorer.py             # Priority scoring
    commitment_classifier.py       # Commitment classification
    context_assigner.py            # Context auto-assignment
    digest.py                      # Daily digest generation
    event_linker.py                # Event-commitment linking
    post_event_resolver.py         # Post-event resolution
    lifecycle_transitions.py       # State machine
    observation_window.py          # Window management
    nudge.py                       # Nudge service
    identity/                      # Identity/entity resolution
    normalization/                 # Signal normalization
    orchestration/                 # Pipeline orchestration
    trace/                         # Signal trace inspector
    voice/                         # Voice query service
    eval/                          # Evaluation utilities
    adhoc_matcher.py               # Ad-hoc signal matching
  tasks.py                         # Celery tasks (all scheduled jobs)
  voice_bridge/                    # Twilio ↔ Gemini Live bridge
    main.py                        # Bridge entry point
    twilio_handler.py              # Twilio WebSocket handler
    gemini_client.py               # Gemini Live client
    audio_pipe.py                  # Audio stream pipeline
    config.py                      # Bridge configuration

migrations/
  alembic/
    versions/                      # Timestamped migration files

tests/
  api/                             # API endpoint tests
  connectors/                      # Connector tests
  core/                            # Core config tests
  integration/                     # End-to-end flow tests
  models/                          # Model tests
  scripts/                         # Script tests
  services/                        # Service logic tests
  unit/                            # Unit tests
  voice_bridge/                    # Voice bridge tests
  test_*.py                        # Cycle D regression tests (root level)

frontend/
  src/
    App.tsx                        # Root component
    pages/
      Dashboard.tsx                # Main view
      CommitmentDetail.tsx         # Detail page
      HistoryLog.tsx               # Closed items
    components/
      CommitmentRow.tsx            # List item
      ContextSelector.tsx          # Context picker
      ContextLine.tsx              # Context display
      DeliveryActions.tsx          # Delivery state controls
      DeliveryBadge.tsx            # Delivery status badge
      ErrorBanner.tsx              # Error display
      LoadingSpinner.tsx           # Loading state
      OnboardingTour.tsx           # Onboarding walkthrough
      PostEventBanner.tsx          # Post-event resolution
      SourceBadge.tsx              # Source type indicator
      SourceGroup.tsx              # Source grouping
      StatusDot.tsx                # Status indicator
      BottomBar.tsx                # Navigation bar
    api/
      client.ts                    # Axios instance
      types.ts                     # Response models
    auth/                          # Supabase auth
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
| 08 | Frontend | ✅ | 2026-03-13 | Dashboard, detail, history views |
| 09 | Onboarding | ✅ | 2026-03-15 | Onboarding tour + setup flow |
| C1 | Model Detection | ✅ | 2026-03-20 | LLM-assisted hybrid detection |
| C2 | Daily Digest | ✅ | 2026-03-21 | Digest generation + admin review |
| C3 | Events | ✅ | 2026-03-22 | Event timeline + post-event resolution |
| C4 | Admin | ✅ | 2026-03-23 | Admin dashboard + review queue |
| C5 | User UI | ✅ | 2026-03-24 | Settings, clarifications, delivery UX |
| C6 | Fixes | ✅ | 2026-03-25 | Bug fixes across platform |
| — | Context UX Fix | ✅ | 2026-03-28 | context_tags JSONB, auto-assignment |
| — | Entity Extraction Fix | ✅ | 2026-03-29 | Always-on extraction + fallback |
| — | Cycle D Fix Iteration | ✅ | 2026-04-01 | RI-F01–F11: systemic production fixes |

---

## Next Steps (B1 → B2)

**B1:** Document current state ✅ **COMPLETE** (2026-04-01)

**B2 (next):** Compare to vision
- Read original briefs (01-10)
- Compare delivered state against product vision
- Identify gaps, deviations, drift
- Document in `vision-delta.md`

**B3:** Assess decisions
- For each gap: intentional or drift?
- Decisions: document rationale in `decisions.md`
- Drift: flag for correction

**B4:** Corrections work order
- If gaps found: create + execute WO
- Do not advance until corrections complete

Then → Next cycle planning or deploy.

---

*This document is a snapshot of what's been delivered as of 2026-04-01. Read it with the original briefs (briefs/ folder) to assess completeness.*
