# Phase 08 — Frontend Complete

**Date:** 2026-03-13
**Stage:** STAGE 3 — BUILD complete

---

## Screens built

- **Dashboard** (`/`) — Source-grouped commitment list (meeting/slack/email), status dots, parallel surface fetches, Overview modal, Quick revert undo buffer, Log commitment form
- **Review** (`/source/:sourceType`) — Target-entity-grouped commitments, Approve all batch PATCH, Share update placeholder
- **Log** (`/source/:sourceType/log`) — Same as Review + AI reasoning annotations (commitment_explanation, ambiguity rows per commitment with colored dots)
- **CommitmentDetail** (`/commitment/:id`) — Full commitment + signals evidence trail grouped by signal_role + ambiguity rows + Approve/Go back actions
- **LoginScreen** (`/login`) — Supabase email+password auth, redirects to / on success

## Components built

- `StatusDot` — red/yellow/green colored dot, size prop
- `SourceBadge` — meeting/slack/email label
- `CommitmentRow` — title + status dot + most-critical sub-row (Deadline/Responsible/Completed) + optional reasoning display
- `SourceGroup` — group header with count + worst-dot + arrow + commitment rows
- `BottomBar` — fixed bottom bar with Overview, Quick revert, Talk it through (disabled), Start session (disabled)
- `LoadingSpinner`, `ErrorBanner`

## Utility modules

- `src/utils/grouping.ts` — dedupById, groupByContextType, groupByTargetEntity, getSourceLabel, status color helpers
- `src/utils/approveAll.ts` — approveAll (proposed-only batch PATCH), revertApproval (undo buffer)

## Test count

- **Frontend:** 45 tests across 4 files (Vitest)
  - test_status_dot.test.ts — 14 tests (status dot logic, group worst-dot)
  - test_api_client.test.ts — 9 tests (header injection, base URL, error handling)
  - test_dashboard_grouping.test.ts — 15 tests (grouping, dedup, labels, status aggregation)
  - test_approve_all.test.ts — 7 tests (proposed-only filter, undo buffer, revert)
- **Backend:** 1 new test file — tests/api/test_commitments_post.py (4 tests, 324 total passing)

## Backend additions

- `POST /commitments` added to `app/api/routes/commitments.py` — creates commitment with lifecycle_state=proposed
- `app/main.py` — StaticFiles mount + SPA fallback (`/{full_path:path}` → index.html), gated on api/public/ directory existing

## Build output

Frontend built with Vite → `api/public/` (served by FastAPI StaticFiles). SPA fallback handles all non-API routes.

## New env vars required

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend API base URL (empty string if co-hosted) |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon public key |

## Decisions made during implementation

- Grouping logic extracted to `src/utils/grouping.ts` so Dashboard, Review, and tests all import from one place
- approveAll utility is pure (accepts patchFn as dependency) — makes testing trivial
- Log screen fetches ambiguities per commitment in parallel via useQueries, gated on parent query completing
- SPA fallback in main.py is conditional (only mounts if api/public/ exists) to avoid startup errors during development
- tsconfig.json required `"types": ["vite/client"]` to resolve import.meta.env TypeScript errors
- Undo buffer uses React ref (not state) to avoid re-renders on approve
- frontend/.gitignore excludes node_modules/ and dist/
