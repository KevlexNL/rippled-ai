# Work Order

## Title
Connect ChatGPT LLM API Token in Settings

## Primary Type
Integration Readiness / Safe Expansion

## Priority
Medium

## Why This Matters
ChatGPT is listed as "Not connected" in the LLM API Token settings. Connecting it provides an alternative LLM provider for Rippled's commitment detection, offering flexibility and resilience in LLM usage. This is a safe expansion that directly supports the MVP by ensuring multiple LLM options are available.

## Problem Observed
The Rippled application's "Settings" page shows ChatGPT as "Not connected" under "LLM API Token". This means the system cannot currently leverage ChatGPT for commitment detection.

## Desired Behavior
ChatGPT should be connected as an available LLM provider, allowing Rippled to utilize it for commitment detection as an alternative to Claude. The "Settings" page should reflect a "Connected" status for ChatGPT.

## Relevant Product Truth
- The system must function as a trustworthy MVP.
- Safe expansions with direct MVP payoff are prioritized.
- Integration readiness in first-wave sources is a high priority.

## Scope
- Obtain a valid ChatGPT API key.
- Input the API key into the designated field in the Rippled "Settings" UI.
- Save the API key.
- Verify that ChatGPT's status changes to "Connected".

## Out of Scope
- Changing the primary LLM provider preference (Claude vs. ChatGPT).
- Modifying commitment detection logic to specifically favor ChatGPT over Claude.
- Adding new LLM providers beyond ChatGPT.

## Constraints
- The API key must be securely handled and stored.
- The connection process should be user-friendly through the existing UI.

## Acceptance Criteria
- The ChatGPT LLM API token is successfully entered and saved.
- The "Settings" UI displays "Connected" next to ChatGPT.
- Rippled can successfully make calls to ChatGPT for commitment detection (requires internal verification or a test function).

## Verification
### Automated
- If applicable, add a health check or integration test to verify connectivity with ChatGPT.

### Browser / Manual
- Navigate to the "Settings" page and confirm that ChatGPT shows as "Connected".
- Optionally, if a test mechanism exists, verify that commitment detection can utilize ChatGPT.

### Observability
- Logs should indicate successful connection to ChatGPT API.
- Any failures during API key saving or connection attempts should be logged.

## Approval Needed
No

## Escalate If
- There are unexpected technical challenges in connecting to the ChatGPT API through the existing infrastructure.
- A policy decision is needed regarding the usage of multiple LLM providers or cost implications.

## Notes for Trinity
This is a straightforward UI interaction and API key storage task. Ensure the API key handling is secure.
