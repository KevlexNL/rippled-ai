# Work Order

## Title
Clean up integrations UI — remove mixed old/new views from setup flow

## Primary Type
Product Debt

## Priority
Medium

## Why This Matters
The integrations setup flow currently mixes old and new UI states, making the product feel inconsistent and untrustworthy in a core flow users must navigate to even begin using Rippled. This is product debt in a gating path — if setup feels muddy, users won't trust what comes after it.

## Problem Observed
- Integrations flow has inconsistent visual patterns between old and new views
- Some setup screens use outdated components or layouts that don't match the current design system
- The flow feels incomplete/patchy in places

## Desired Behavior
- Integrations setup flow is visually consistent end-to-end
- No obsolete views or components visible to the user
- Setup flow clearly reflects the current design system
- Each source (email, Slack, meeting) has a consistent connect/disconnect/status UI

## Relevant Product Truth
- Product Debt type in directive.md
- §12 What Good MVP Progress Looks Like: "the system behaves consistently across core flows"
- Product Principle §5.5: "Trust beats cleverness"

## Scope
- Audit integrations setup flow in browser — document every screen/state
- Identify which components/views are old vs current design system
- Remove or replace obsolete views with current equivalents
- Ensure email, Slack, and meeting sources each have consistent connect/status/disconnect states
- Verify no regressions in integration functionality

## Out of Scope
- New integration types
- OAuth flow changes (covered in WO-002)
- Any changes to backend integration logic

## Constraints
- Do not remove any functional states — only visual/UX debt
- Must not break existing source connections

## Acceptance Criteria
- [ ] Browser audit shows no mixed old/new UI components in integration flow
- [ ] All three source types (email, Slack, meeting) have consistent visual treatment
- [ ] Existing connected sources still display their connected state correctly

## Verification
- Browser walkthrough of full integrations flow with screenshot comparison before/after
- Existing integration sources still show correct connected state in UI
- No visual regressions in setup or status screens

## Escalate to Mero if
- Audit reveals product decisions are needed (e.g. what a "partially configured" state should show)

## Requires Approval
No — this is core-flow product debt cleanup with no product direction changes.
