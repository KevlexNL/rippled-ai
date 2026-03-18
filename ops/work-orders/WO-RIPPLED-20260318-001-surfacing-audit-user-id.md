# Work Order

## Title
Add `user_id` column to `surfacing_audit` table

## Primary Type
Observability Gap

## Priority
Medium

## Why This Matters
The `surfacing_audit` table currently lacks a `user_id` column, preventing per-user analysis and auditing of commitment surfacing events. This limits observability into a core aspect of Rippled's functionality and hinders debugging or understanding user-specific behavior.

## Problem Observed
The `surfacing_audit` table in the database does not include a `user_id` column, making it impossible to filter or analyze surfacing events for individual users.

## Desired Behavior
The `surfacing_audit` table should include a `user_id` column (UUID, non-nullable, foreign key to `users.id`) to enable user-specific auditing of surfaced commitments.

## Relevant Product Truth
- Rippled should increase observability and debuggability (directive.md, Prime Objective #4)
- Lack of observability in ingestion and commitment creation is a current heuristic (inspection-cycle.md, Current Heuristics #4)

## Scope
- Add a `user_id` column of type UUID to the `surfacing_audit` table.
- Make the `user_id` column `NOT NULL`.
- Add a foreign key constraint linking `surfacing_audit.user_id` to `users.id` with `ON DELETE CASCADE`.

## Out of Scope
- Backfilling existing `surfacing_audit` rows with a `user_id`. This will be a separate task if deemed necessary.
- Changes to how data is written to the `surfacing_audit` table (i.e., ensuring `user_id` is populated for new entries). This is an upstream change and a follow-up.

## Constraints
- The schema change must be idempotent and safely runnable as a migration.
- Must not cause downtime or data loss.

## Acceptance Criteria
- The `surfacing_audit` table has a `user_id` column.
- The `user_id` column is a UUID, non-nullable, and has a foreign key to `users.id` with `ON DELETE CASCADE`.
- A schema inspection confirms the presence and correct definition of the new column.

## Verification
### Automated
- Add a schema test to verify the existence and properties of the `user_id` column in `surfacing_audit`.

### Browser / Manual
- N/A for this backend schema change.

### Observability
- N/A for this backend schema change directly, but it enables future observability.

## Approval Needed
No

## Escalate If
- Adding `user_id` as NOT NULL poses significant challenges for existing data or future writes that cannot be easily resolved.
- There's a conflict with an existing column or data model that wasn't apparent.

## Notes for Trinity
This task focuses solely on adding the column and its constraints via a migration. Upstream changes to populate this column for new data, or backfilling existing data, are considered separate follow-up tasks.
