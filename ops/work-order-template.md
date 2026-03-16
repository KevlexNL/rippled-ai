# Rippled Work Order Template

Use this template for all OpenClaw-generated work orders sent to Trinity.

The goal is to produce work that is:
- bounded
- testable
- aligned with product truth
- easy to approve or reject
- easy to escalate when ambiguity is discovered

---

## File Naming Convention
`WO-YYYYMMDD-###-short-slug.md`

Example:
`WO-20260316-001-slack-oauth-install-flow.md`

---

## Template

```md
# Work Order

## Title
[Clear implementation-ready title]

## Primary Type
[Blocker | Product Debt | Integration Readiness | Observability Gap | Safe Expansion]

## Priority
[Critical | High | Medium | Low]

## Why This Matters
[1 short paragraph explaining why this matters for MVP readiness, trust, or testing]

## Problem Observed
[What is happening right now]

## Desired Behavior
[What should be true after this work is complete]

## Relevant Product Truth
[Reference the applicable sections in product-truth.md]

## Scope
- [specific change 1]
- [specific change 2]
- [specific change 3]

## Out of Scope
- [explicit non-goal 1]
- [explicit non-goal 2]

## Constraints
- [technical or product constraint 1]
- [technical or product constraint 2]

## Acceptance Criteria
- [observable behavior outcome]
- [UI or data requirement]
- [test or verification requirement]
- [no regressions in adjacent flow]

## Verification
### Automated
- [tests to add or run]

### Browser / Manual
- [manual verification path]

### Observability
- [log, trace, replay, or instrumentation evidence expected]

## Approval Needed
[Yes | No]

## Escalate If
- [condition 1]
- [condition 2]

## Notes for Trinity
[implementation hints only if helpful]
```

---

## Work Order Rules
Every work order must:
1. map to exactly one primary type
2. be narrow enough to complete and verify cleanly
3. state a real observed problem, not an abstract improvement wish
4. reference `product-truth.md`
5. state what is explicitly out of scope
6. define a verification path
7. declare whether it needs approval before execution

If any of those are missing, the work order is not ready.

---

## Approval Rules
### Approval not needed when:
- the task is a clear blocker fix
- the task improves observability or debuggability
- the task cleans up product debt in a locked core flow without changing product direction
- the task improves realism in an already chosen integration path
- the task is a low-risk safe expansion and remains inside MVP boundaries

### Approval needed when:
- the task changes the product promise
- the task introduces a new source or major workflow
- the task changes permissions, privacy posture, or marketplace strategy
- the task adds a new persistent surface beyond the current MVP core
- the task changes how Rippled speaks to users in a way that affects trust positioning
- the task depends on a product decision not already locked

---

## Escalation Format
If Trinity hits ambiguity, the escalation must be short and decision-shaped.

Use this exact structure:

```md
## Escalation
**Question:** [one yes/no or forced-choice question]
**Why blocked:** [one sentence]
**Options:** [A / B / C]
**Default recommendation:** [one line]
**Impact if unanswered:** [one line]
```

Avoid long explanation unless requested.

---

## Example Work Order

```md
# Work Order

## Title
Replace Gmail app-password setup with OAuth-based connection flow

## Primary Type
Integration Readiness

## Priority
High

## Why This Matters
The current app-password approach is an MVP shortcut that makes the integration feel untrustworthy and does not reflect the likely long-term connection model for a real app.

## Problem Observed
Google account connection currently relies on an app-password style setup, which creates friction and does not match the product quality expected in a real integration flow.

## Desired Behavior
Users can connect a Google account through an OAuth flow with a clearer and more realistic setup experience.

## Relevant Product Truth
- Rippled should improve trust in core flows
- first-wave sources should be realistic enough for meaningful MVP testing
- the product should avoid shortcuts that hide true integration limitations

## Scope
- implement Google OAuth connection flow for the existing integration setup
- update the setup UI to guide the user through the connection
- preserve any existing downstream signal ingestion expectations where possible

## Out of Scope
- adding new Google-derived product surfaces
- redesigning the entire integrations area
- changing downstream detection logic

## Constraints
- must remain compatible with current MVP source priorities
- must not introduce unrelated account model changes

## Acceptance Criteria
- a user can initiate and complete Google connection through OAuth
- the integrations flow no longer instructs the user to use app-password style setup
- the connected state is visible in the integrations UI
- the flow is verifiable in browser testing

## Verification
### Automated
- add or update tests covering connection state handling

### Browser / Manual
- complete the flow through the integrations page in a browser session

### Observability
- connection success and failure states are logged clearly enough to diagnose setup problems

## Approval Needed
No

## Escalate If
- Google OAuth requires a product or marketplace decision outside the existing MVP direction
- the current auth architecture cannot support the flow without account model changes

## Notes for Trinity
Prefer minimal UI changes outside the integration setup area.
```
