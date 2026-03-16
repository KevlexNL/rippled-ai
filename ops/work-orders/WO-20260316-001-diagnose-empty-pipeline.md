# Work Order

## Title
Diagnose and fix empty ingestion pipeline for Kevin's account

## Primary Type
Blocker

## Priority
Critical

## Why This Matters
Kevin's account has 4 active sources configured (email ×2, Slack, meeting) but zero source_items and zero commitment_signals in the database. All 8 existing commitments are test fixtures seeded against other users. The dashboard being empty is not a UI problem — it's a pipeline problem. Until real data flows, MVP testing is meaningless.

## Problem Observed
- `source_items` table: 0 rows, `last ingested: None`
- `commitment_signals` table: 0 rows
- `candidate_commitments` table: 0 rows
- Sources registered: email (kevin.beeftink@gmail.com, active), Slack (Kevlex Academy, active), meeting (active)
- Credentials are present and encrypted in sources table
- No evidence the ingestor has ever run for Kevin's user

## Desired Behavior
- At least one source (email is lowest-friction to verify) successfully ingests source items
- `source_items` table contains rows with Kevin's user_id
- Pipeline continues through normalization → commitment_signals → candidate_commitments
- Dashboard shows real commitment candidates for Kevin's account

## Relevant Product Truth
- MVP Goal §7: "If the product is not processing real data, the MVP is not being tested meaningfully"
- Observability §4 in inspection-cycle.md: determine where in the chain the break is

## Scope
- Identify whether the ingestor is configured to run (cron/celery/manual trigger)
- Trace the pipeline for Kevin's email source end-to-end
- Fix the specific failure point (misconfiguration, unstarted worker, missing trigger, credential decrypt failure, etc.)
- Add a log entry or observable state that confirms successful ingestion
- Verify at least one source_item appears for kevin.beeftink@gmail.com

## Out of Scope
- Fixing Slack DM limitations (separate WO)
- Meeting source (lower priority until email is proven)
- UI changes
- Changing credential storage method

## Constraints
- Credentials are Fernet-encrypted in the DB — verify decrypt works in current environment
- Do not alter Kevin's source config or credentials without confirming they still work

## Acceptance Criteria
- [ ] `source_items` contains at least 1 row for Kevin's user_id after trigger
- [ ] Pipeline continues: at least 1 `commitment_signals` row derived from that source_item
- [ ] Trinity can describe exactly where the chain was broken and what fixed it

## Verification
- Direct DB query: `SELECT COUNT(*) FROM source_items WHERE user_id = '441f9c1f-9428-477e-a04f-fb8d5e654ec2'`
- Pipeline log trace shows successful ingest → normalize → signal steps
- Dashboard shows at least one commitment candidate for Kevin

## Escalate to Mero if
- Credential decryption fails and requires a credential refresh from Kevin
- The ingestor requires a running Celery worker that is not deployed on Railway
- Source config is structurally broken and requires Kevin to reconnect the integration

## Requires Approval
No — this is a blocker fix aligned with existing source strategy.
