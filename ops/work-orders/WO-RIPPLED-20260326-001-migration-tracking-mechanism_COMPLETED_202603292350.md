# Work Order

## Title
Implement Migration Tracking Mechanism

## Primary Type
Observability Gap

## Priority
High

## Why This Matters
The absence of a migration tracking system makes it impossible to reliably apply database schema changes, leading to potential data corruption or application errors. This hinders safe development and deployment.

## Problem Observed
There is no mechanism to determine which `.sql` files in `~/projects/rippled-ai/supabase/migrations/` have been applied to the database, preventing safe and idempotent application of pending migrations.

## Desired Behavior
A `schema_migrations` table exists in the database, accurately tracking all applied migration files, allowing for reliable identification and application of pending migrations.

## Relevant Product Truth
- Rippled should increase observability and debuggability (directive.md, Prime Objective #4)
- Lack of observability in ingestion and commitment creation is a current heuristic (inspection-cycle.md, Current Heuristics #4)

## Scope
- Create a `schema_migrations` table if it does not exist, with columns `version` (TEXT, PK) and `applied_at` (TIMESTAMP DEFAULT NOW()).
- Implement a Python script or function that:
    - Reads all `.sql` files in `~/projects/rippled-ai/supabase/migrations/`.
    - Checks the `schema_migrations` table to see which migrations have already been applied.
    - Applies only the pending `.sql` migration files in order (e.g., numerically or by timestamp prefix).
    - Records each successfully applied migration in the `schema_migrations` table.

## Out of Scope
- Rewriting existing migration files.
- Implementing an advanced migration framework (e.g., Alembic for Python ORMs). The focus is a basic tracking and application mechanism.

## Constraints
- The solution must be idempotent; running the script multiple times should not cause errors for already applied migrations.
- Must not cause data loss or downtime.

## Acceptance Criteria
- A `schema_migrations` table exists in the database with `version` and `applied_at` columns.
- The implemented script can identify and apply pending migrations.
- Running the script twice with no new migration files results in no changes to the database and no errors.
- The `schema_migrations` table accurately reflects all applied migrations.

## Verification
### Automated
- Add unit tests for the migration application logic.
- Add an integration test that simulates applying new migrations and verifies tracking.

### Browser / Manual
- N/A

### Observability
- Database inspection confirms the `schema_migrations` table and its contents. Logs show successful application of migrations.

## Approval Needed
No

## Escalate If
- There are unforeseen complexities in creating the `schema_migrations` table or managing its state.
- Existing processes conflict with the proposed migration application mechanism.

## Notes for Trinity
Focus on a simple, robust Python-based solution for tracking and applying migrations using `psycopg2`.
