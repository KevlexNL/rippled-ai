# Rippled.ai — Current State (2026-04-02)

## Summary

**Status:** Cycle A (9 phases) + Cycle C (C1-C6) + Cycle D fix-iteration (RI-F01 through RI-F11) + Cycle D features (D1-D4) complete. Cycle B2 vision review in progress.

**Test count:** 1750 tests collected, all passing.

**Architecture:** FastAPI (Python 3.11+) + PostgreSQL (Supabase) + Celery (Redis) + React frontend (Vite) + Twilio/Gemini voice bridge. Deployed on Railway.

---

## Backend Services (app/services/)

### Detection & Classification
| Service | File | Purpose |
|---------|------|---------|
| Deterministic Detector | `detection/detector.py` | Pattern-matching commitment detection |
| Seed Detector | `detection/seed_detector.py` | Initial seed pass for historical data |
| Detection Patterns | `detection/patterns.py` | Detection heuristics and patterns |
| Detection Context | `detection/context.py` | Context window management |
| Profile Matcher | `detection/profile_matcher.py` | Identity/profile matching during detection |
| Detection Audit | `detection/audit.py` | Audit logging for detection decisions |
| Learning Loop | `detection/learning_loop.py` | Feedback-driven detection improvement |
| Model Detection | `model_detection.py` | GPT-4-mini model-assisted re-classification |
| Hybrid Detection | `hybrid_detection.py` | Combines deterministic + model results |
| Commitment Classifier | `commitment_classifier.py` | Big promise vs small commitment classification |

### Clarification
| Service | File | Purpose |
|---------|------|---------|
| Analyzer | `clarification/analyzer.py` | Detects ambiguity types |
| Suggestions | `clarification/suggestions.py` | Generates suggested values |
| Clarifier | `clarification/clarifier.py` | Main clarification orchestrator |
| Promoter | `clarification/promoter.py` | Promotes candidates to commitments |

### Completion Detection
| Service | File | Purpose |
|---------|------|---------|
| Detector | `completion/detector.py` | Detects delivery/completion signals |
| Matcher | `completion/matcher.py` | Matches signals to commitments |
| Updater | `completion/updater.py` | State transitions on completion |
| Scorer | `completion/scorer.py` | Completion confidence scoring |

### Normalization & Ingestion
| Service | File | Purpose |
|---------|------|---------|
| Email Normalization | `normalization/email_normalization_service.py` | Raw email to normalized signal |
| Email Raw Ingest | `normalization/email_raw_ingest_service.py` | Raw email payload handling |
| Participant Resolver | `normalization/participant_resolver.py` | Email participant resolution |
| Quoted Text Parser | `normalization/quoted_text_parser.py` | Quoted email content parsing |
| Replay Runner | `normalization/replay_runner.py` | Signal replay for re-processing |
| Normalization Repo | `normalization/normalization_repository.py` | Data access layer |

### Orchestration Pipeline (6-stage)
| Service | File | Purpose |
|---------|------|---------|
| Orchestrator | `orchestration/orchestrator.py` | Main pipeline controller |
| Eligibility | `orchestration/stages/eligibility.py` | Stage 0: deterministic eligibility |
| Candidate Gate | `orchestration/stages/candidate_gate.py` | Stage 1: binary relevance |
| Speech Act | `orchestration/stages/speech_act.py` | Stage 2: speech-act classification |
| Extraction | `orchestration/stages/extraction.py` | Stage 3: commitment field extraction |
| Routing | `orchestration/stages/routing.py` | Stage 4: deterministic routing |
| Escalation | `orchestration/stages/escalation.py` | Stage 5: strong model escalation |
| LLM Caller | `orchestration/stages/llm_caller.py` | Shared LLM call logic |
| Config | `orchestration/config.py` | Model routing configuration |
| Stage Logger | `orchestration/stage_logger.py` | Per-stage logging |
| Contracts | `orchestration/contracts.py` | Data contracts for stages |
| Prompts | `orchestration/prompts/` | LLM prompts for each stage |

### Surfacing & Prioritization
| Service | File | Purpose |
|---------|------|---------|
| Surfacing Runner | `surfacing_runner.py` | Main surfacing sweep orchestrator |
| Surfacing Router | `surfacing_router.py` | Routes to Main/Shortlist/Clarifications |
| Priority Scorer | `priority_scorer.py` | 0-100 multi-dimensional scoring |
| Observation Window | `observation_window.py` | D1: Configurable observation windows |
| Auto-Close Config | `auto_close_config.py` | D2: Configurable auto-close timing |

### Events & Calendar
| Service | File | Purpose |
|---------|------|---------|
| Event Linker | `event_linker.py` | D3: Links calendar events to commitments |
| Calendar Matcher | `calendar_matcher.py` | D3: Calendar-as-evidence matching |
| Post-Event Resolver | `post_event_resolver.py` | D3: Delivery state after events |
| Nudge | `nudge.py` | D3: Pre-event nudging |

### Digest & Reporting
| Service | File | Purpose |
|---------|------|---------|
| Digest | `digest.py` | Daily digest aggregation and delivery |
| LLM Judge | `llm_judge.py` | Weekly LLM quality evaluation |

### Identity & Context
| Service | File | Purpose |
|---------|------|---------|
| Owner Resolver | `identity/owner_resolver.py` | Commitment owner resolution |
| Term Resolver | `identity/term_resolver.py` | Domain term/jargon resolution |
| Context Assigner | `context_assigner.py` | Auto-assigns commitments to contexts |

### Feedback & Adaptation
| Service | File | Purpose |
|---------|------|---------|
| Feedback Adapter | `feedback_adapter.py` | D4: User feedback → threshold adjustment |

### Other
| Service | File | Purpose |
|---------|------|---------|
| Lifecycle Transitions | `lifecycle_transitions.py` | Allowed state transitions |
| Ad-hoc Matcher | `adhoc_matcher.py` | Text similarity signal matching |
| Tracer | `trace/tracer.py` | Signal trace debugging |
| Eval Runner | `eval/runner.py` | Evaluation harness |
| Voice STT | `voice/stt_service.py` | Speech-to-text |
| Voice TTS | `voice/tts_service.py` | Text-to-speech |
| Voice Intent | `voice/intent_parser.py` | Voice intent parsing |
| Voice Query | `voice/query_service.py` | Voice query service |

---

## API Endpoints (all under /api/v1)

### Commitments (commitments.py)
- `GET /commitments` — List commitments (supports surface filter)
- `POST /commitments` — Create commitment
- `GET /commitments/{id}` — Get commitment
- `PATCH /commitments/{id}` — Update commitment
- `DELETE /commitments/{id}` — Soft delete
- `POST /commitments/{id}/skip` — Skip commitment
- `GET /commitments/{id}/signals` — List signals
- `POST /commitments/{id}/signals` — Add signal
- `GET /commitments/{id}/ambiguities` — List ambiguities
- `POST /commitments/{id}/ambiguities` — Add ambiguity
- `PATCH /commitments/{id}/ambiguities/{aid}` — Update ambiguity
- `PATCH /commitments/{id}/delivery-state` — Update delivery state
- `GET /commitments/{id}/events` — List linked events
- `POST /commitments/{id}/events` — Link event
- `POST /commitments/{id}/feedback` — Submit feedback (D4)

### Candidates (candidates.py)
- `GET /candidates` — List candidates
- `GET /candidates/{id}` — Get candidate

### Contexts (contexts.py)
- `GET /contexts` — List contexts
- `POST /contexts` — Create context
- `GET /contexts/{id}/commitments` — Context commitments
- `POST /contexts/auto-assign` — Auto-assign

### Surface (surface.py)
- `GET /surface/main` — Main surface
- `GET /surface/shortlist` — Shortlist surface
- `GET /surface/clarifications` — Clarifications surface
- `GET /surface/best-next-moves` — Best next moves with reasoning
- `GET /surface/internal` — Internal/system surface

### Digest (digest.py)
- `POST /digest/trigger` — Trigger digest
- `GET /digest/log` — Digest log
- `GET /digest/preview` — Preview digest

### Clarifications (clarifications.py)
- `GET /clarifications` — List clarifications
- `POST /clarifications/{id}/respond` — Respond to clarification

### Sources (sources.py)
- `POST /sources/test/email` — Test email connection
- `POST /sources/test/slack` — Test Slack connection
- `GET /sources/onboarding-status` — Onboarding status
- `POST /sources/setup/email` — Setup email
- `POST /sources/setup/slack` — Setup Slack
- `POST /sources/setup/meeting` — Setup meeting
- `POST /sources/{id}/regenerate-secret` — Regenerate secret
- `GET /sources` — List sources
- `POST /sources` — Create source
- `GET /sources/{id}` — Get source
- `PATCH /sources/{id}` — Update source
- `DELETE /sources/{id}` — Delete source

### Source Items (source_items.py)
- `POST /source-items` — Create item
- `POST /source-items/batch` — Batch create (207 multi-status)
- `GET /source-items/{id}` — Get item

### Webhooks
- `POST /webhooks/email/inbound` — Email inbound
- `POST /webhooks/slack/events` — Slack events
- `POST /webhooks/meetings/transcript` — Meeting transcript

### Events (events.py)
- `GET /events` — List events
- `POST /events` — Create event
- `GET /events/{id}` — Get event
- `PATCH /events/{id}` — Update event

### Integrations (integrations.py)
- `GET /integrations/google/auth` — Google OAuth
- `GET /integrations/google/callback` — Google callback
- `GET /integrations/google/status` — Google status
- `DELETE /integrations/google/disconnect` — Disconnect Google
- `GET /integrations/slack/oauth/start` — Slack OAuth start
- `GET /integrations/slack/oauth/callback` — Slack callback

### Identity (identity.py)
- `GET /identity/profile` — List profiles
- `POST /identity/seed` — Seed profiles
- `POST /identity/confirm` — Confirm profile
- `POST /identity/manual` — Manual entry
- `DELETE /identity/{id}` — Delete profile
- `GET /identity/status` — Status
- `POST /identity/backfill` — Backfill

### Terms (terms.py)
- `GET /identity/terms` — List terms
- `POST /identity/terms` — Create term
- `PATCH /identity/terms/{id}` — Update term
- `DELETE /identity/terms/{id}` — Delete term
- `POST /identity/terms/{id}/aliases` — Add alias
- `DELETE /identity/terms/{id}/aliases/{aid}` — Delete alias

### User Settings (user_settings.py)
- `GET /user/settings` — Get settings
- `PATCH /user/settings` — Update settings (includes D1 observation windows, D2 auto-close, D4 feedback thresholds)
- `GET /user/feedback-stats` — Feedback statistics (D4)

### Stats & Reports
- `GET /stats` — Platform stats
- `GET /report/weekly-summary` — Weekly summary

### Admin (admin.py)
- `GET /admin/health` — Health check
- `GET/PATCH /admin/commitments` — Commitment management
- `GET/PATCH /admin/candidates` — Candidate management
- `GET /admin/surfacing-audit` — Surfacing audit
- `GET /admin/events` — Events
- `GET /admin/digests` — Digests
- `POST /admin/pipeline/*` — Pipeline execution (detection, surfacing, linker, nudge, digest, resolver)
- `POST /admin/seed-detection`, `POST /admin/seed-reset` — Seed operations
- `POST /admin/test/seed-commitment` — Test commitment
- `DELETE /admin/test/cleanup` — Cleanup
- `POST/GET /admin/eval/*` — Evaluation harness
- `POST/GET /admin/adhoc-signals` — Ad-hoc signal management
- `POST /admin/backfill-source` — Source backfill

### Admin Review (admin_review.py)
- `GET /admin/review/signals` — Detection signals
- `POST /admin/review/signals/{id}` — Review signal
- `GET /admin/review/outcomes` — Commitment outcomes
- `POST /admin/review/outcomes/{id}` — Review outcome
- `GET /admin/review/stats` — Review stats
- `GET /admin/review/audit-sample` — Audit sample

### Lab & Debug
- `GET /lab/source-items` — Source items listing
- `POST /lab/trace` — Trace functionality
- `POST /debug/pipeline` — Debug pipeline execution

### Voice
- `POST /voice/*` — Voice processing endpoints

---

## Database Models (app/models/)

### Core
| Model | Table | Key Fields |
|-------|-------|------------|
| User | users | id, email, display_name |
| Commitment | commitments | id, user_id, resolved_owner, owner_candidates, deliverable, commitment_type, lifecycle_state, delivery_state, priority_class, speech_act, confidence_*, surfaced_as, priority_score, observation_window_hours (D1), observe_until (D1), context_id, structure_complete, post_event_reviewed, due_precision |
| CommitmentCandidate | commitment_candidates | id, trigger_class, confidence_score, is_explicit, priority_hint, commitment_class_hint, source_type, observe_until, context_window, linked_entities |
| CommitmentSignal | commitment_signals | id, commitment_id, source_item_id, signal_role (origin/clarification/progress/delivery/closure/conflict/reopening) |
| CommitmentAmbiguity | commitment_ambiguities | id, commitment_id, field, type, candidates, status |
| CommitmentEventLink | commitment_event_links | id, commitment_id, event_id, metadata (D3) |
| CommitmentContext | commitment_contexts | id, name, user_id |
| CandidateCommitment | candidate_commitments | Maps candidates to promoted commitments |
| Clarification | clarifications | id, commitment_id, issue_types, suggested_values |

### Sources & Signals
| Model | Table | Key Fields |
|-------|-------|------------|
| Source | sources | id, user_id, source_type, credentials, last_synced_at |
| SourceItem | source_items | id, source_id, body, sender, recipients, metadata |
| RawSignalIngest | raw_signal_ingests | id, provider, raw_payload |
| NormalizedSignalORM | normalized_signals | id, canonical signal format |
| NormalizationRun | normalization_runs | id, audit of runs |

### Events & Lifecycle
| Model | Table | Key Fields |
|-------|-------|------------|
| Event | events | id, user_id, title, start_time, end_time, recurrence |
| LifecycleTransition | lifecycle_transitions | id, commitment_id, from_state, to_state, reason |
| SurfacingAudit | surfacing_audits | id, user_id, commitment_id, action |

### User & Settings
| Model | Table | Key Fields |
|-------|-------|------------|
| UserSettings | user_settings | id, user_id, observation_window_config (D1), auto_close_config (D2), feedback_thresholds (D4) |
| UserCommitmentProfile | user_commitment_profiles | id, user_id, contact info |
| CommonTerm | common_terms | id, term, user_id |
| Alias | aliases | id, term_id, alias_value |

### Audit & Evaluation
| Model | Table | Key Fields |
|-------|-------|------------|
| DetectionAudit | detection_audits | id, decision, reasoning |
| LLMJudgeRun | llm_judge_runs | id, results, run_at |

---

## Celery Tasks (app/tasks.py)

### Periodic (Beat Schedule)
| Task | Frequency | Purpose |
|------|-----------|---------|
| `run_detection_sweep` | Every 5 min | Catch missed source items |
| `run_clarification_batch` | Every 5 min | Process clarification queue |
| `run_completion_sweep` | Every 10 min | Evidence sweep + auto-close |
| `run_model_detection_batch` | Every 10 min | Model-assisted re-classification |
| `sync_google_calendar` | Every 15 min | Google Calendar sync (D3) |
| `recompute_surfacing` | Every 30 min | Re-score and re-route surfaces |
| `run_adhoc_signal_match_check` | Every 30 min | Ad-hoc signal matching |
| `run_pre_event_nudge` | Hourly at :00 | Pre-event nudging (D3) |
| `run_post_event_resolution` | Hourly at :30 | Post-event delivery (D3) |
| `run_stale_candidate_discard` | Every 6 hours | Stale candidate cleanup |
| `send_daily_digest` | Daily 8 AM UTC | Daily digest email |
| `recompute_feedback_thresholds_all` | Daily 3 AM UTC | Feedback threshold recalc (D4) |
| `run_llm_judge` | Weekly Mon 8 AM | LLM quality evaluation |

### On-Demand
| Task | Trigger | Purpose |
|------|---------|---------|
| `detect_commitments` | Source item creation | Per-item detection |
| `run_clarification_task` | Per candidate | With retry, max 3 |
| `run_model_detection_pass` | Per candidate | Model re-classification |
| `process_slack_event` | Slack webhook | Process Slack events |
| `poll_email_imap` | Every 5 min | IMAP polling |
| `run_source_backfill` | Manual | Per user/source backfill |
| `run_seed_pass_task` | Manual | Seed pass per user |
| `update_profile_after_model_detection` | Post-model | Profile update |
| `update_profile_after_dismissal` | On dismissal | Profile update |
| `run_eval_task` | Manual | Evaluation runs |
| `cleanup_routing_backlog` | Manual | Routing cleanup |

---

## Frontend Components (frontend/src/)

### Screens (19)
| Screen | File | Purpose |
|--------|------|---------|
| Dashboard | `Dashboard.tsx` | Main dashboard with surface tabs |
| Commitments | `CommitmentsScreen.tsx` | Commitments list view |
| Commitment Detail | `CommitmentDetail.tsx` | Full detail panel |
| Detail Panel | `DetailPanel.tsx` | Generic detail panel |
| Active | `ActiveScreen.tsx` | Active commitments |
| Review | `Review.tsx` | Review/approval screen |
| Log | `Log.tsx` | Event log |
| Log Commitment Modal | `LogCommitmentModal.tsx` | Manual commitment entry |
| Settings Modal | `SettingsModal.tsx` | Settings interface |
| Prototype Dashboard | `PrototypeDashboard.tsx` | Experimental dashboard |
| Signal Lab | `SignalLabScreen.tsx` | Signal debugging |
| Admin | `AdminScreen.tsx` | Admin panel |
| Architecture | `ArchitectureScreen.tsx` | System diagram |
| Onboarding | `OnboardingScreen.tsx` | Onboarding flow |
| Onboarding Identity | `OnboardingIdentityScreen.tsx` | Identity setup |
| Login | `LoginScreen.tsx` | Login |
| Sign Up | `SignUpScreen.tsx` | Registration |
| Forgot Password | `ForgotPasswordScreen.tsx` | Password recovery |
| Reset Password | `ResetPasswordScreen.tsx` | Password reset |

### Settings Screens
| Screen | File | Purpose |
|--------|------|---------|
| Sources Settings | `SourcesSettingsScreen.tsx` | Source configuration |
| Integrations Settings | `IntegrationsSettingsScreen.tsx` | OAuth integrations |
| Identity Settings | `IdentitySettingsScreen.tsx` | Identity/profile management |
| Account Settings | `AccountSettingsScreen.tsx` | Account settings |
| Observation Windows | `ObservationWindowsSection.tsx` | D1: Window config UI |
| Auto-Close Timing | `AutoCloseTimingSection.tsx` | D2: Auto-close config UI |

### Reusable Components (13)
CommitmentRow, ContextSelector, ContextLine, SourceGroup, SourceBadge, StatusDot, DeliveryBadge, DeliveryActions, PostEventBanner, OnboardingTour, BottomBar, ErrorBanner, LoadingSpinner

---

## External Integrations

| Integration | Connector | Status |
|-------------|-----------|--------|
| Email (IMAP) | `connectors/email/imap_poller.py` | Active — polling + webhook |
| Email (Webhook) | `api/routes/webhooks/email.py` | Active |
| Slack (Events API) | `connectors/slack/normalizer.py` | Active — events + thread enrichment |
| Slack (OAuth) | `api/routes/integrations.py` | Active |
| Meetings (ReadAI) | `connectors/meeting/readai_client.py` | Active — transcript webhook |
| Google Calendar | `connectors/google_calendar.py` | Active — D3: 15-min sync + OAuth |
| Twilio Voice | `voice_bridge/twilio_handler.py` | Experimental |
| Gemini Live | `voice_bridge/gemini_client.py` | Experimental |
| Supabase Auth | `frontend/src/lib/auth.tsx` | Active |

---

## Test Coverage Summary

**Total tests:** 1750 collected, all passing (2026-04-02)

| Area | Test Files | Coverage |
|------|------------|----------|
| API endpoints | ~16 files in tests/api/ | Webhooks, CRUD, surfacing, admin, events, identity |
| Services | ~16 files in tests/services/ | Detection, completion, digest, events, nudge, audit, orchestration (10 files) |
| Connectors | ~18 files in tests/connectors/ | Email, Slack, meeting normalizers; IMAP; Google Calendar; participant resolution |
| Integration | ~12 files in tests/integration/ | End-to-end flows, detection pipeline, contexts, learning loop |
| Feature/regression | ~20 files in tests/ (root) | Cycle C/D features, lifecycle, feedback, admin, celery readiness |
| Frontend | 4 test files | Context selector, architecture screen, log commitment modal |
| Voice | tests/voice_bridge/ | Voice bridge tests |

---

## Migrations

**40 migration files** in migrations/versions/ tracking full schema evolution from Phase 01 through Cycle D4.

Key Cycle D migrations:
- `t4u5v6w7x8y9_add_observation_window_config.py` — D1
- `u5v6w7x8y9z0_add_auto_close_config.py` — D2
- `v6w7x8y9z0a1_add_metadata_to_commitment_event_links.py` — D3
- `w7x8y9z0a1b2_d4_user_feedback_thresholds.py` — D4

---

## Deliverables Status

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 01 | Schema | Done | Core domain model, 40 migrations |
| 02 | API Scaffold | Done | REST endpoints, error handling |
| 03 | Detection | Done | Deterministic + model-assisted hybrid |
| 04 | Clarification | Done | Ambiguity analysis + suggestions |
| 05 | Completion | Done | State machine + evidence tracking |
| 06 | Surfacing | Done | Prioritization + surface routing |
| 07 | Connectors | Done | Email/Slack/meetings/Google Calendar |
| 08 | Frontend | Done | Dashboard, detail, history, settings |
| 09 | Onboarding | Done | Onboarding tour + setup flow |
| C1 | Model Detection | Done | LLM-assisted hybrid detection |
| C2 | Daily Digest | Done | Digest generation + delivery |
| C3 | Events | Done | Event timeline + post-event resolution |
| C4 | Admin | Done | Admin dashboard + review queue |
| C5 | User UI | Done | Settings, clarifications, delivery UX |
| C6 | Fixes | Done | Bug fixes across platform |
| D1 | Observation Windows | Done | Configurable per-source windows |
| D2 | Auto-Close Config | Done | Configurable auto-close timing |
| D3 | Calendar Integration | Done | Calendar-as-evidence matching |
| D4 | Feedback Loops | Done | User feedback → adaptive thresholds |

*This document is a snapshot of what exists as of 2026-04-02, post-Cycle-D completion.*
