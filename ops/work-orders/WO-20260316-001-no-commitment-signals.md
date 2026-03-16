# Work Order

## Title
Investigate and resolve missing commitment signals and commitments from source items

## Primary Type
Blocker / Observability Gap

## Priority
Critical

## Why This Matters
Despite 21 `source_items` being present, no downstream `commitment_signals`, `candidate_commitments`, or `final commitments` are being generated or surfaced. This prevents meaningful end-to-end testing, indicates a core pipeline failure after ingestion, and creates an observability gap preventing diagnosis of the root cause. This directly impacts Rippled's core MVP functionality.

## Problem Observed
The database shows 21 `source_items` for user `441f9c1f-9428-477e-a04f-fb8d5e654ec2`, but the counts for `commitment_signals`, `candidate_commitments`, and `commitments` are all 0. The browser UI's "Active" and "Commitments" tabs are empty, reflecting this lack of processed data.

## Desired Behavior
Upon ingestion of `source_items`, the system should correctly process them to generate `commitment_signals`, `candidate_commitments`, and ultimately `commitments` that are visible in the database and surfaced in the Rippled UI. The pipeline should have sufficient observability to identify where the processing is failing.

## Relevant Product Truth
- Rippled's prime objective is to continuously reduce the gap between intended MVP behavior and observed current behavior.
- The system must function as a trustworthy MVP by prioritizing work that unblocks real end-to-end testing.
- Observability and debuggability are critical.
- The core flow expectations include the detection, tracking, and surfacing of likely commitments.

## Scope
- Identify the exact stage in the pipeline where `source_items` are failing to convert into `commitment_signals` or `candidate_commitments`.
- Implement necessary fixes to ensure `source_items` are processed correctly through to `commitments`.
- Enhance logging or instrumentation to provide clear visibility into the data flow, especially around `source_items` to `commitment_signals` and `candidate_commitments` generation.
- Verify that the database counts for `commitment_signals`, `candidate_commitments`, and `commitments` increase after processing new `source_items`.

## Out of Scope
- Adding new source types.
- Major UI redesigns beyond surfacing existing commitments.
- Modifying the initial `source_item` ingestion process unless it is directly causing the downstream failure.

## Constraints
- Must align with current MVP scope and directional priorities (real live data flow, observability of signal ingestion and failure points).
- Solutions should be verifiable with clear acceptance criteria.

## Acceptance Criteria
- New `source_items` are successfully processed into `commitment_signals` and `candidate_commitments` (if applicable) within the expected timeframe.
- The `commitment_signals` and `commitments` tables show non-zero counts for the user `441f9c1f-9428-477e-a04f-fb8d5e654ec2` after new data is ingested.
- The Rippled UI (Active and Commitments tabs) correctly displays the processed commitments.
- Logs clearly indicate the status of `source_item` processing, highlighting any failures or bottlenecks in the pipeline.
- No regressions in existing `source_item` ingestion.

## Verification
### Automated
- Add or update unit/integration tests for the `source_item` to `commitment_signal` and `candidate_commitment` processing logic.

### Browser / Manual
- Manually trigger new `source_item` ingestion (if possible) and observe the Rippled UI for new commitments.
- Re-run the DB count script to verify increased counts in `commitment_signals`, `candidate_commitments`, and `commitments`.

### Observability
- Review application logs for evidence of `source_item` processing, successful `commitment_signal` generation, and `commitment` creation.
- Ensure specific error messages or warnings are present if processing fails at any stage.

## Approval Needed
No

## Escalate If
- The root cause is outside the existing architectural understanding or requires significant re-architecture.
- A product decision is required on how to handle ambiguous `source_items` that fail to generate signals.
- The fix requires changes to locked `product-truth.md` principles.

## Notes for Trinity
Focus on debugging the pipeline flow from `source_items` onward. Prioritize clear logging and immediate fixes to get basic end-to-end data flow working.
