# Rippled OpenClaw Foundation Pack

This pack contains the minimum operating documents needed to fuel an ongoing OpenClaw -> Trinity cycle for Rippled.

## Files
- `directive.md` — the standing operating directive for continuous improvement
- `product-truth.md` — the locked product truth OpenClaw and Trinity should align to
- `work-order-template.md` — the schema for all emitted work orders
- `inspection-cycle.md` — the repeating inspection loop and output requirements
- `approval-matrix.md` — what can be dispatched autonomously vs what needs Kevin's approval

## Intended Use
1. Put these files somewhere stable in the Rippled repo, such as `/ops` or `/product`.
2. Have OpenClaw read them before generating work orders.
3. Run the inspection cycle daily or at session start.
4. Emit 1-3 bounded work orders at a time.
5. Use short escalation questions whenever product ambiguity appears.

## Suggested Next Work Orders
Based on the current context, likely early candidates are:
- diagnose why the dashboard is empty and add the missing observability
- implement realistic Slack integration setup for DM-capable testing
- replace Google app-password style setup with OAuth-based connection
- clean up the integrations flow to remove mixed old/new UI states
