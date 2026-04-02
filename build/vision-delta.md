# Vision Delta — Briefs vs Reality (2026-04-02)

Post-Cycle-D (D1-D4) vision review. Compares all 10 briefs against current platform state.

**Prior review:** 2026-04-01 (post-Cycle-D fix iteration, pre-D1-D4 features)
**This review:** 2026-04-02 (post-D1 observation windows, D2 auto-close config, D3 calendar integration, D4 feedback loops)

---

## Executive Summary

**Completeness:** ~98% of specified MVP scope delivered and operational. The two gaps flagged in the prior review (hardcoded observation windows, non-configurable auto-close) are now resolved by D1 and D2.

**Remaining gaps are primarily UX-layer concerns** (suggestion language, push notifications, compact bundling) rather than architectural or domain model deficiencies. The backend comprehensively implements the vision; the frontend presentation layer has not been systematically audited against brief language standards.

---

## Brief 1: Product Vision

### Planned
Single-user commitment intelligence from meetings/Slack/email. Reduce cognitive load. NOT a task manager. Capture broadly, surface selectively. Big promises (Main) vs small commitments (Shortlist). Suggestion-first, trust over cleverness.

### Built — Aligned
- Single-user architecture
- Three sources with working connectors
- Big promise vs small commitment classification
- Selective surfacing with observation windows

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 1.1 | **Suggestion language in frontend** — Brief demands "likely," "seems," "may need" throughout. Frontend presents commitments more factually than tentatively. | Medium |

---

## Brief 2: Product Principles (20 Principles)

### Alignment by Principle

| # | Principle | Status |
|---|-----------|--------|
| 1 | Reduce cognitive load | Aligned |
| 2 | Capture broadly, surface selectively | Aligned |
| 3 | Infer more than assert | Aligned |
| 4 | Trust > cleverness | Aligned |
| 5 | Live where work happens | Aligned |
| 6 | Commitment > task | Aligned |
| 7 | Small commitments matter | Aligned |
| 8 | Priority = consequence + burden | Aligned |
| 9 | Priority != confidence | Aligned |
| 10 | Preserve ambiguity | Aligned |
| 11 | "We" not a person | Aligned |
| 12 | Observe before interrupting | Aligned (D1) |
| 13 | Interruptions earn their place | Partial — no push system |
| 14 | Helpful not accusatory | Partial — depends on frontend language |
| 15 | Delivery != closure | Aligned |
| 16 | Later signals update, not erase | Aligned |
| 17 | External stricter | Aligned |
| 18 | Completion inferred from evidence | Aligned |
| 19 | Age gracefully from uncertainty | Aligned |
| 20 | User feels lighter | No direct measurement |

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 2.1 | **Push/notification system** — No push mechanism beyond daily digest. Brief says "interruptions rarer than in-app visibility" implying a push layer exists. | Medium |
| 2.2 | **Frontend tone audit** — Principles 3, 14 require suggestion language throughout UI. Not systematically applied. | Medium |

---

## Brief 3: Commitment Domain Model

### Built — Substantially Aligned
- Commitment object with full field set: ownership, timing, deliverable, lifecycle, confidence dimensions, evidence
- Owner model: `resolved_owner`, `owner_candidates`, `ownership_ambiguity`
- Timing model: `resolved_deadline`, `deadline_candidates`, `timing_ambiguity`, `due_precision`
- Signal roles: all 7 roles (origin, clarification, progress, delivery, closure, conflict, reopening)
- Ambiguity as first-class: `CommitmentAmbiguity` model
- Confidence dimensions: 6 separate fields

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 3.1 | **Explanation fields** — Brief specifies "why Rippled thinks it's a commitment" and "what's missing" as commitment fields. These exist implicitly through audit/clarification but not as first-class commitment fields. | Low |
| 3.2 | **Version history** — No explicit versioning beyond lifecycle transitions + signal history. | Low |

---

## Brief 4: Source Model

### Built — Aligned
- Three first-class sources: email (IMAP + webhook), Slack (Events API + threads), meetings (ReadAI)
- Cross-source signal linking to unified commitment
- Internal/external classification via `participant_classifier.py`
- D1 configurable observation windows per source type
- Slack thread enrichment, DMs/private channels in scope
- Email quoted text stripping
- Message edit handling

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 4.1 | **Cross-source merge logic** — Signal linking supports multi-source commitments, but no active heuristic automatically links a Slack "done" to a meeting-originated commitment about the same topic. Depends on ad-hoc matching rather than dedicated cross-source linker. | Medium |
| 4.2 | **Attachment content matching** — Basic metadata only. Brief 7 explicitly allows simplification here. | Low |

---

## Brief 5: Commitment Lifecycle

### Built — Aligned with Extension
- Six specified states present: proposed, needs_clarification, active, delivered, closed, discarded
- Flexible non-linear transitions supported
- Delivered != closed enforced
- Reversibility (delivered → active, closed → active)
- Full audit trail via `LifecycleTransition`

### Deviation
| # | Item | Severity |
|---|------|----------|
| 5.1 | **Additional lifecycle states** — Platform has `dormant`, `confirmed`, `in_progress`, `completed`, `canceled` beyond the 6 specified. Brief locks exactly 6 MVP states. | Medium — needs B3 classification |

---

## Brief 6: Surfacing & Prioritization

### Built — Aligned
- Three primary surfaces: Main, Shortlist, Clarifications
- Multi-dimensional priority scoring (externality, timing, consequence, confidence, actionability)
- D1 configurable observation windows before surfacing
- Surfacing audit trail
- Extended with `best-next-moves` and `internal` surfaces

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 6.1 | **Push notification layer** — Same as 2.1. No push mechanism. Digest is only outbound. | Medium |
| 6.2 | **Compact bundles** — Surfaces are lists, not prioritized "good catch" bundles. | Low |
| 6.3 | **Suggestion language** — Same as 1.1. Surfaces present items factually. | Medium |

---

## Brief 7: MVP Scope

### In-Scope Checklist
| # | Requirement | Status |
|---|-------------|--------|
| 1 | Three sources first-class | Done |
| 2 | Commitment intelligence pipeline | Done |
| 3 | Unified commitment model | Done |
| 4 | Commitment classes (big/small) | Done |
| 5 | Missing info & clarification | Done |
| 6 | Confidence model (structured) | Done |
| 7 | Lifecycle/state handling | Done (extended) |
| 8 | Completion/delivery detection | Done |
| 9 | Main/Shortlist/Clarifications views | Done |
| 10 | Suggestion-first language | Partial (backend yes, frontend gap) |
| 11 | Internal vs external strictness | Done |
| 12 | Traceability & auditability | Done |

### Out-of-Scope Items (properly excluded)
Task manager, multi-user workspace, enterprise permissions, native integration breadth, native bot, highly polished UI, heavy automation, large analytics, full attachment understanding. **All correctly excluded.**

### Intentional Scope Creep
| Feature | Rationale |
|---------|-----------|
| D4 feedback loops | Brief 7 marks "advanced learning/personalization" out of scope. D4 intentionally starts this early. |
| Google Calendar (D3) | Calendar not in original MVP brief scope. Added for calendar-as-evidence value. |
| Voice bridge | Exploratory, experimental. |
| Admin panel (C4) | Operational tooling not in briefs but operationally necessary. |

### MVP Reality Check
| Criterion | Verdict |
|-----------|---------|
| "I forgot fewer things" | Architecture supports — observation windows + surfacing |
| "Fewer 'oh shit I promised that' moments" | Supported — detection captures across 3 sources |
| "Didn't maintain another task system" | Achieved — no task management features |
| "Suggestions felt useful more than annoying" | Depends on frontend language gap (1.1) |

---

## Brief 8: Commitment Detection

### Built — Aligned
- Deterministic + model-assisted hybrid detection
- Explicit, implicit, delegated, small practical, client-facing, modifying, status signals
- Source-specific rules (Slack overlays, meeting LLM pipeline, email normalizer)
- Context windows stored per candidate
- Priority hints + commitment class hints
- Observation flags + re-analysis flags
- Seed pass for historical data
- Learning loop (D4)

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 8.1 | **14 detection categories completeness** — Brief lists 14 specific trigger classes. Most appear implemented but completeness needs pattern-level audit. | Low |
| 8.2 | **Re-analysis workflow** — `flag_reanalysis` column exists but no task/workflow consumes it. Flagged candidates sit unprocessed. | Medium |

---

## Brief 9: Clarification

### Built — Aligned
- Ambiguity type detection (multiple types)
- D1 configurable observation windows
- Clarifications surface + endpoint
- Suggested value generation
- Candidate promotion pipeline
- External commitments prioritized

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 9.1 | **Clarification object completeness** — Brief specifies `why_this_matters`, `observation_window_status`, `surface_recommendation`, `suggested_clarification_prompt`. Model likely partial. | Low |
| 9.2 | **4-tier escalation** — Brief defines do-nothing/internal/review/escalate as distinct behaviors. System may not implement full ladder. | Low-Medium |
| 9.3 | **Clarification bundling** — List not bundled by priority/urgency as "good catch" moments. | Low |

---

## Brief 10: Completion Detection

### Built — Aligned
- Evidence-based delivery inference pipeline (detector → matcher → scorer → updater)
- D2 configurable auto-close timing
- Reopening supported (delivered → active)
- D3 post-event resolution adds calendar-as-evidence
- External strictness in priority scoring

### Gaps
| # | Gap | Severity |
|---|-----|----------|
| 10.1 | **Cross-channel matching** — Brief describes rich matching (actor, recipient, deliverable, topic, time, thread). Cross-channel matching (email delivery matching meeting promise) may be shallow. | Medium |
| 10.2 | **Type-specific completion** — Brief defines 5 commitment types (send/reply/review/create/coordinate) with different detection difficulty. No evidence of type-specific scoring paths. | Low-Medium |

---

## Consolidated Gap Summary

### Recurring Theme: Frontend Suggestion Language (1.1 / 2.2 / 6.3 / 7.1)
The single most consistent gap across briefs. The backend correctly implements confidence scores and suggested values. The frontend does not systematically use tentative language ("looks like," "seems likely," "may need") when displaying commitments. This is a UX pass, not an architectural change.

### Medium Gaps Requiring Decision
| # | Gap | Action Needed |
|---|-----|---------------|
| 1.1 | Suggestion language in frontend | Frontend UX pass |
| 2.1 / 6.1 | Push/notification system | Architectural decision — build or defer? |
| 4.1 | Cross-source merge logic | Detection improvement |
| 5.1 | Extra lifecycle states | Classify: intentional or drift? |
| 8.2 | Re-analysis workflow | Wire up existing flag |
| 10.1 | Cross-channel completion matching | Detection improvement |

### Low Gaps (acceptable for MVP)
3.1, 3.2, 4.2, 6.2, 8.1, 9.1, 9.2, 9.3, 10.2

### Resolved Since Last Review
- Observation windows hardcoded → D1 made configurable
- Auto-close not configurable → D2 made configurable

---

*This delta is honest about gaps while acknowledging the platform substantially delivers on the vision across all 10 briefs. The remaining gaps are primarily UX-layer and detection-sophistication concerns, not architectural deficiencies.*
