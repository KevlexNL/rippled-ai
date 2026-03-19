# Context UX Fix — Research Findings

## Current State

- `commitment_contexts` table exists with pre-seeded contexts per user
- `Commitment.context_id` FK exists, PATCH endpoint supports updating it
- 0/64 surfaced commitments have `context_id` assigned
- Seed detector (`_create_commitment_and_signal`) never sets `context_id`
- Surfacing runner has no context assignment step
- Frontend has "Group by Context" mode but it's empty since no commitments have contexts

## Root Cause

Two gaps:
1. **No auto-assignment**: Neither seed detection nor surfacing assigns contexts
2. **No manual UI**: Frontend `patchCommitment` doesn't expose `context_id` field

## Chosen Approach: Option C (Auto + Manual)

### Auto-assignment (primary)
- Add `assign_contexts()` step in `run_surfacing_sweep()`
- Match commitment `counterparty_name` against existing `commitment_contexts.name` (fuzzy)
- Also match keywords in `title` against context names
- Only assign if no `context_id` already set (don't override manual assignments)

### Manual override (secondary)
- Update frontend `patchCommitment` to include `context_id`
- Add inline context selector to commitment detail or row (stretch)

### Why this order
- Auto-assignment requires no UI changes and instantly populates the context grouping
- Manual override is a small API+frontend tweak for user control
