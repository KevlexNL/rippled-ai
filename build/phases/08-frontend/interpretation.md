# Phase 08 — Frontend Interpretation

**Stage:** STAGE 2 — INTERPRET
**Date:** 2026-03-13
**Author:** Claude (for Trinity review)

---

## Summary

Phase 08 builds the user-facing web application for Rippled. The design reference shows a mobile-first, 4-screen app centered on a source-grouped dashboard (not tab navigation). The backend is fully built — surfacing, scoring, lifecycle, and signals are all live. The frontend's job is to present commitment intelligence with the right tone: supportive, tentative, low-friction.

---

## 1. UI Reference Analysis

Four screens are shown in `ui-reference.jpg`. They flow left to right: Dashboard → Review → Log → Commitment detail.

### Screen 1 — Ripples Dashboard

The entry point. Shows commitments **grouped by source event**, not by surfaced priority class.

- Header: user name + notification + cloud icons
- Three source groups, each with count + status dot + arrow:
  - "From today's meeting @ 2pm" — 3 things to confirm (yellow dot)
  - "From Slack today" — 2 things for review (green dot)
  - "From your email" — 2 new commitments to track (red dot)
- `+ Log commitment` manual entry button
- Bottom action strip: **Overview / Quick revert / Talk it through / Start session**

**Status dot semantics (inferred):**
- 🔴 Red = needs immediate attention (external, overdue, or ambiguous on critical field)
- 🟡 Yellow = uncertain / needs check (proposed state, unresolved ambiguity)
- 🟢 Green = good / tracking cleanly

### Screen 2 — Ripple Review

Drill-down into one source group. Shows the commitments from that batch, **grouped by project/topic**.

- Title: "From today's meeting @ 2pm"
- Two project groups visible: **Branding Guidelines (KRS)** and **AI Sales Trainer (Stephen)**
- Each commitment item: title + ✓ checkmark
- Each item has a sub-row showing one key dimension: `Deadline` or `Responsible` + colored dot + note text
- Bottom: "Share update" | "Approve all" | "13 more ripples logged" link

The `Deadline` sub-row shows: `Finalize draft of branding guidelines by Wed Mar 4th` (yellow dot)
The `Responsible` sub-row shows: `Assign "Add brand samples..." to Allyson` (green dot)

### Screen 3 — Ripple Log

The evidence-annotated version of Ripple Review. Same commitments, but the status annotations reveal the AI's reasoning.

- Attribution at top: "Pulled from Rippl.ai"
- Ambiguity annotations inline:
  - `Deadline (red dot) — Unclear from transcript (Check)`
  - `Responsible (red dot) — No assignee mentioned in transcript (Ruby)`
  - `Completed (yellow dot) — Sam didn't reply back for 3 days (Check)`
  - `Completed (green dot) — Confirmed via email by Stephen`
- Some commitments show an arrow → to drill further

This screen exposes the backend's `CommitmentAmbiguity` records and the AI's `missing_pieces_explanation`/`commitment_explanation` fields directly. It's the "why did Rippled flag this?" layer.

### Screen 4 — Ripple Commitment

Individual commitment detail. Shows the full record with sub-task breakdown.

- Small header: "Tasks tracked in Notion" (external tracker integration label)
- Commitment title: "AI Sales Trainer (Stephen)"
- Quote block: original `commitment_text` from the source transcript
- Sub-tasks with headings: "Create first version", "Review with Sam", "Make part of weekly team schedule"
- Each sub-task has: status badge (Deadline/Responsible/Completed/In progress) + colored dot + description text
- Bottom: "Go back" | "Approve all"

**Note:** The sub-task structure (Create first version / Review with Sam / etc.) does **not** map directly to any current backend entity. This is addressed in Open Questions below.

---

## 2. Backend API Inventory

### Available endpoints

| Endpoint | Returns | Used by screen |
|---|---|---|
| `GET /surface/main` | Up to 10 commitments with surfaced_as=main | Dashboard (meeting/email external items) |
| `GET /surface/shortlist` | Up to 10 commitments with surfaced_as=shortlist | Dashboard (Slack/internal items) |
| `GET /surface/clarifications` | Up to 10 commitments needing clarification | Dashboard (red-dot items) |
| `GET /commitments` | All commitments with filters | Review, Log |
| `GET /commitments/{id}` | Single commitment, full schema | Commitment detail |
| `PATCH /commitments/{id}` | Update lifecycle_state, owner, deadline, etc. | Approve, discard, edit |
| `DELETE /commitments/{id}` | Discard a commitment | Revert |
| `GET /commitments/{id}/signals` | Linked source signals | Log screen evidence |
| `GET /commitments/{id}/ambiguities` | Unresolved ambiguity records | Log screen annotations |
| `GET /sources` | Connected source accounts | Dashboard header/settings |

### Key fields on `CommitmentRead` used by the UI

| Field | Where used |
|---|---|
| `title` | All screens — primary text |
| `commitment_text` | Commitment detail — original quote block |
| `context_type` | Dashboard — source grouping (meeting/slack/email) |
| `lifecycle_state` | Status dot color mapping |
| `surfaced_as` | Priority ordering within groups |
| `priority_score` | Sort order within a source group |
| `resolved_owner`, `suggested_owner`, `ownership_ambiguity` | Responsible sub-row |
| `resolved_deadline`, `vague_time_phrase`, `suggested_due_date`, `timing_ambiguity` | Deadline sub-row |
| `target_entity` | Project grouping label within Review screen |
| `commitment_explanation` | Log screen — AI reasoning |
| `missing_pieces_explanation` | Log screen — why flagged |
| `confidence_commitment` | Status dot color calibration |
| `surfacing_reason` | Log screen annotation context |

### Auth

The backend uses a simple `X-User-ID` header, not a JWT. For MVP, the frontend should:
1. Use Supabase Auth (already in the stack via `supabase_url` / `supabase_anon_key`)
2. After auth, extract the user UUID from the Supabase session
3. Pass it as `X-User-ID` with every API request

This requires no backend changes — it aligns with the existing single-user MVP model.

---

## 3. Screen → API Mapping

### Dashboard

Fetch in parallel on mount:
```
GET /surface/main
GET /surface/shortlist
GET /surface/clarifications
```

Group the merged result by `context_type` (meeting / slack / email) and further by date. Sort groups by `priority_score` descending. Compute group-level status dot by scanning the worst lifecycle/ambiguity state in the group.

**Gap identified:** The design shows "From today's meeting @ 2pm" — a specific session label. The backend only has `context_type`, not a session name. For MVP, use `context_type` + today's date to produce readable labels:
- `meeting` → "From today's meeting" (or "From [N] meetings today" if multiple)
- `slack` → "From Slack today"
- `email` → "From your email"

This is a reasonable MVP simplification. The exact session timestamp ("@ 2pm") can come from a future `source_item` enrichment endpoint.

### Ripple Review

When user taps a source group arrow:
```
GET /commitments?lifecycle_state=active&limit=50  (filter by context_type client-side)
```

Or (cleaner): add `context_type` filter to `/surface/main` + `/surface/shortlist` responses and merge for the selected source.

Group by `target_entity` to produce project buckets. If `target_entity` is null, group under "Other".

For each commitment row, show the most important ambiguity dimension as the sub-row:
- If `timing_ambiguity` is present and unresolved → show Deadline row
- Else if `ownership_ambiguity` is present and unresolved → show Responsible row
- Else if `lifecycle_state == "delivered"` → show Completed row
- Else → show nothing

### Ripple Log

Same data as Review but shows the AI reasoning layer. Fetch:
```
GET /commitments/{id}/ambiguities  (for each visible commitment)
```

Use `ambiguity_type` + `description` from `CommitmentAmbiguityRead` to render the annotation text. Map `ambiguity_type` to dot color:
- `owner_missing`, `timing_missing`, `deliverable_unclear` → red (needs input)
- `timing_vague`, `owner_vague_collective` → yellow (uncertain)
- All resolved ambiguities → green

### Ripple Commitment

```
GET /commitments/{id}
GET /commitments/{id}/signals
GET /commitments/{id}/ambiguities
```

Display:
- `commitment_text` as the quote block
- Signals grouped by `signal_role` (origin / clarification / delivery / closure) as evidence trail
- Ambiguities as the annotated dimension rows

**Gap identified:** Screen 4 shows hierarchical sub-tasks (Create first version / Review with Sam). These don't exist in the backend. My recommendation for MVP: render the `signals` list as the "evidence trail" instead of sub-tasks. The sub-task hierarchy is a product vision for a future phase; it likely requires a `commitment_sub_task` table that doesn't exist yet.

---

## 4. Frontend Architecture

### Recommended stack

**React 18 + TypeScript + Vite + TailwindCSS + TanStack Query v5 + React Router v6**

Rationale:
- **React + TypeScript**: standard, well-suited to the component structure
- **Vite**: fast dev server, minimal config, no SSR needed
- **TailwindCSS**: rapid mobile-first styling, matches the clean monochrome + dot-color design language
- **TanStack Query**: handles the multi-endpoint fetching, caching, and background refresh the dashboard needs
- **React Router**: 4 screens = 4 routes; no complex routing needed

No Next.js: this is a SPA with no SEO or SSR requirements. No Redux: TanStack Query handles server state. No component library: the design is custom enough that a library would fight more than help.

### Project structure

```
frontend/
  src/
    api/          # typed fetch functions wrapping each endpoint
    components/   # shared UI: StatusDot, CommitmentRow, SourceGroup, BottomBar
    screens/      # Dashboard, Review, Log, CommitmentDetail
    hooks/        # useCommitments, useSurface, useCommitmentDetail
    lib/          # apiClient (sets X-User-ID header), auth helpers
    types/        # TypeScript types mirroring backend schemas
    App.tsx
    main.tsx
  index.html
  vite.config.ts
  tailwind.config.ts
```

### Routing

```
/                     → Dashboard (Ripples Dashboard)
/source/:sourceType   → Review (Ripple Review for a source group)
/source/:sourceType/log → Log (Ripple Log — evidence view)
/commitment/:id       → CommitmentDetail (Ripple Commitment)
```

### API client

A single `apiClient` module that:
- Reads user_id from Supabase session on init
- Injects `X-User-ID` header on every request
- Exposes typed functions: `getSurface(type)`, `getCommitment(id)`, `patchCommitment(id, body)`, etc.
- Base URL configured via `VITE_API_BASE_URL` env var

### Status dot logic

```typescript
function getStatusDot(c: CommitmentRead): 'red' | 'yellow' | 'green' {
  if (c.lifecycle_state === 'needs_clarification') return 'red'
  if (c.ownership_ambiguity === 'missing' || c.timing_ambiguity === 'missing') return 'red'
  if (c.lifecycle_state === 'proposed') return 'yellow'
  if (c.ownership_ambiguity || c.timing_ambiguity) return 'yellow'
  if (c.confidence_commitment && c.confidence_commitment < 0.5) return 'yellow'
  return 'green'
}
```

Group-level dot: the worst dot color of any commitment in the group.

---

## 5. "Approve all" Action

The design shows "Approve all" as a bottom action on Review and Log screens. My interpretation:

**Approve = transition all `proposed` commitments in the current group to `active`.**

This calls `PATCH /commitments/{id}` with `{ lifecycle_state: "active" }` for each `proposed` commitment visible in the current view. This is a batch operation done in parallel from the client.

The "Quick revert" action on the Dashboard bottom bar = undo the most recent approve action (restore commitments to `proposed`). For MVP, this can be a locally-cached undo that re-PATCHes the reverted items back to `proposed`.

---

## 6. What the Bottom Bar Actions Mean

From the Dashboard:

| Action | Interpretation | Implementation |
|---|---|---|
| Overview | Possibly a summary/stats view showing counts by surface | New screen or modal: counts from /surface/main, /surface/shortlist, /surface/clarifications |
| Quick revert | Undo the last approve-all | Client-side undo with re-PATCH |
| Talk it through | Voice/AI session to discuss commitments | Out of scope for MVP build — placeholder button |
| Start session | Begin a review session (step through clarifications one by one) | Out of scope for MVP — placeholder button |

**Recommendation:** Implement Overview (simple counts) and Quick revert (undo buffer). Leave Talk it through and Start session as disabled/placeholder UI for MVP.

---

## 7. Open Questions with Recommendations

### Q1: What frontend framework / stack?
**Recommendation:** React + TypeScript + Vite + TailwindCSS + TanStack Query + React Router, deployed as a static SPA.

### Q2: How to group Dashboard by source session (e.g., "@ 2pm")?
The backend has `context_type` (meeting/slack/email) but not a session timestamp label. **Recommendation:** Use `context_type` + `created_at` date for MVP grouping labels. Exact session labels (meeting at 2pm) require a future source enrichment endpoint — acceptable to defer.

### Q3: How to group commitments by project in Ripple Review?
Use `target_entity` field from `CommitmentRead`. **Recommendation:** group by `target_entity`, null entities go under an "Other" bucket.

### Q4: What are the sub-tasks in Screen 4 (Ripple Commitment)?
These don't map to any current backend entity. They appear to be a product vision for future hierarchical commitment decomposition. **Recommendation:** MVP simplification — render the `signals` array (from `GET /commitments/{id}/signals`) as the evidence trail, displayed with role labels (origin / clarification / delivery). Do not implement sub-tasks for Phase 08.

### Q5: Does "Log commitment" (the + button) need a backend endpoint?
It needs `POST /commitments` — which doesn't exist yet in the routes (only GET/PATCH/DELETE). However, the `CommitmentCreate` schema exists in schemas.py. **Recommendation:** add a `POST /commitments` route as a small Phase 08 backend addition, or defer manual logging for MVP and make the button a placeholder.

### Q6: Mobile vs desktop?
The design reference is clearly mobile-first. **Recommendation:** responsive web app, mobile-first breakpoints (375px base). No native app. No PWA manifest required for MVP.

### Q7: Where does auth happen?
Supabase Auth is already configured in the backend config. **Recommendation:** use `@supabase/supabase-js` on the frontend for auth, extract `user.id` from session, pass as `X-User-ID` header. No backend changes needed.

### Q8: Is the `/surface/` data sufficient for the Dashboard, or do we need a new grouped endpoint?
The three `/surface/` endpoints return flat lists up to 10 items each. For the Dashboard they're fetched together and grouped client-side by `context_type`. **Recommendation:** sufficient for MVP. If the 10-item limit becomes a constraint, adjust the limit parameter.

---

## 8. What Is Not In Scope for Phase 08

- "Talk it through" (voice AI session)
- "Start session" (step-through clarification flow)
- Notion/task tracker integration (shown in Screen 4 header "Tasks tracked in Notion")
- Sub-task hierarchy within a commitment
- Settings / source management UI
- Notification/push system
- Advanced filtering or search

---

## 9. Suggested Phase 08 Deliverables

1. **Frontend project scaffold** — Vite + React + TypeScript + Tailwind + TanStack Query
2. **API client module** — typed, X-User-ID injected, base URL from env
3. **Supabase auth integration** — login screen → session → user_id header
4. **Screen: Dashboard** — source-grouped, status dots, counts, navigation
5. **Screen: Ripple Review** — target_entity-grouped commitments, sub-row dimensions, Approve all
6. **Screen: Ripple Log** — same as Review + ambiguity annotations layer
7. **Screen: Ripple Commitment** — full commitment detail + signals evidence trail
8. **Bottom bar** — Overview (counts modal) + Quick revert (undo buffer)
9. **PATCH lifecycle flow** — approve, discard actions wired to backend
10. **Minor backend addition** — `POST /commitments` route for "Log commitment" button (optional for MVP)

---

## 10. Principle Check

Every screen must pass the product's core test: **does this make the user feel lighter, not more managed?**

Frontend implications:
- No dense lists — max ~5 items visible before scroll
- Suggestion language everywhere — "Looks like", "Likely", not "You must"
- Ambiguity dots explain themselves without demanding action
- "Approve all" exists so the user can move fast when everything looks right
- The Log screen is opt-in — users who want to understand the AI's reasoning can tap into it; others don't have to

---

*Awaiting Trinity review and approval before BUILD stage begins.*
