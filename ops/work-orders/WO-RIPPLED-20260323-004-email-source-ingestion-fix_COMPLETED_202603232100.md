# Work Order

## Title
Investigate and Resolve Failing Email Source Ingestion

## Primary Type
Integration Readiness

## Priority
High

## Why This Matters
The failure of an email source to ingest data directly impacts Rippled's ability to detect commitments from a critical communication stream. This hinders realistic MVP testing, undermines trust in data integrity, and prevents the system from performing its core function for email-based inputs.

## Problem Observed
Trinity's `build/state.json` notes "One email source (imap.example.com) failing — likely placeholder credentials." This indicates a failure in the ingestion pipeline for at least one email source.

## Desired Behavior
All configured email sources should successfully ingest data, and any failures should be clearly identifiable, diagnosed, and resolvable. The `imap.example.com` source, if still active and intended, should be ingesting data correctly or be properly configured/removed.

## Relevant Product Truth
- Resolving integration limitations that prevent realistic usage is a prime objective (directive.md, Prime Objective #3)
- First-wave integrations that are incomplete in realistic usage are a current heuristic (inspection-cycle.md, Current Heuristics #2)

## Scope
- Investigate the specific `imap.example.com` email source configuration and its current status.
- Access relevant logs (ingestion, Celery worker) to diagnose the exact cause of the failure (e.g., credential issue, connection problem, parsing error).
- Determine if the `imap.example.com` entry is a placeholder that needs to be removed/updated or a real source that requires troubleshooting.
- If it's a real source, propose steps to fix the ingestion failure.

## Out of Scope
- Implementing new email source connectors or features.
- Broad refactoring of the entire ingestion pipeline unless directly identified as the root cause.
- Fixing other unrelated source integration issues not specifically mentioned.

## Constraints
- Investigation should be non-invasive and not cause further disruption to ingestion.
- Must not expose sensitive credentials or user data in logs unnecessarily.

## Acceptance Criteria
- The cause of the `imap.example.com` email source failure is identified and documented.
- If it's a placeholder, it's either removed or updated to a non-failing state.
- If it's a real source, a clear plan for resolution is provided, or the issue is resolved.
- Relevant logs confirm the diagnosis and any proposed fix.

## Verification
### Automated
- N/A for initial investigation, but new tests might be warranted for a fix.

### Browser / Manual
- If a UI exists for source configuration, verify its state. Check logs for ingestion activity.

### Observability
- Review ingestion pipeline logs and Celery worker logs for error messages related to `imap.example.com`.

## Approval Needed
No

## Escalate If
- The issue points to a deeper architectural problem with the ingestion pipeline.
- Resolution requires significant product decisions regarding source management or error handling.
- Cannot access necessary logs or configuration to diagnose the problem.

## Notes for Trinity
Focus on a targeted diagnosis of the `imap.example.com` source. Determine its purpose (placeholder vs. active) and why it's failing. Provide clear steps for resolution or escalation.