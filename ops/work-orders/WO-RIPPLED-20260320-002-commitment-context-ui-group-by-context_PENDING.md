# Work Order

## Title
Improve Commitment Context UI by Grouping by Context

## Primary Type
Product Debt

## Priority
Medium

## Why This Matters
Commitments are surfacing, but the context feature (grouping by context_id) is underutilized (0.00% usage). This indicates a usability gap in a core feature designed to reduce cognitive load and organize commitments. Improving this will enhance the user's ability to make sense of their commitments, aligning with Rippled's prime objective.

## Problem Observed
Commitments are being surfaced, but the `context_id` is rarely used or displayed effectively in the UI, resulting in 0.00% context usage. This suggests users are not leveraging or even aware of the context grouping feature.

## Desired Behavior
The UI should effectively group commitments by their `context_id` where available, making the context feature intuitive and easy to use. This could involve automatically assigning contexts or making manual assignment more discoverable and lower friction. `context_id` usage should increase.

## Relevant Product Truth
- Rippled aims to reduce cognitive load (directive.md, Prime Objective)
- Commitment-assistant behavior, trust, and suggestion-based interaction (inspection-cycle.md, Compare to Product Truth #5)
- Cleanup of muddy integration UX in core setup flows (directive.md, Current Directional Priorities #4) - this extends to core UI.

## Scope
- Investigate current UI implementation of commitment display and identify areas where `context_id` could be more prominently used for grouping.
- Propose and implement UI changes to present commitments grouped by `context_id`.
- If applicable, explore and implement a mechanism for auto-assigning contexts from topic classification to new commitments.

## Out of Scope
- Major redesigns of the entire dashboard.
- Changes to the underlying commitment detection or signal processing logic.

## Constraints
- Changes should be minimal to achieve the desired outcome and not disrupt core flows.
- Must not introduce new, unresolved product decisions.

## Acceptance Criteria
- Commitments in the UI are visibly grouped by their `context_id` when a context is assigned.
- The context grouping is intuitive for the user.
- Evidence of increased `context_id` usage in `commitments` table over time. (Requires monitoring after deployment).

## Verification
### Automated
- Add UI tests to verify the presence and functionality of context grouping.

### Browser / Manual
- Manually review the UI to confirm commitments are grouped by context and the feature is clear.

### Observability
- Monitor `context_id` usage in the `commitments` table post-deployment to confirm increased adoption.

## Approval Needed
No

## Escalate If
- Significant UI redesign is required that falls outside the scope of minor product debt cleanup.
- Implementing context auto-assignment requires complex new LLM logic or data models.

## Notes for Trinity
Focus on improving the visibility and usability of the existing `context_id` in the UI. Prioritize simple, impactful changes.
