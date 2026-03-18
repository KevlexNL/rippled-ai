# Rippled Inspection Cycle

## Purpose
This document defines the repeating inspection cycle OpenClaw should run to generate high-quality candidate work orders for Trinity.

This is the ongoing fuel source for the autonomous pipeline.

---

## Cadence
Run the inspection cycle:
- once daily on active development days, or
- at the start of any implementation session, or
- after any completed work order that may have created follow-up work

If multiple runs happen in one day, prefer deltas over full re-analysis.

---

## Inputs
The inspection cycle should gather evidence from:
- current app behavior in browser
- integration flows
- dashboard state and empty states
- logs and instrumentation
- failing tests or missing tests
- recent repo changes
- unresolved escalations
- known product truth in `product-truth.md`
- governing rules in `directive.md`

---

## Cycle Steps

### 0. Ground Visual Findings in Code
Before treating any visual finding as confirmed, verify it against the codebase:
- Is the UI element wired to a real backend route?
- Does the route actually execute the expected logic, or is it a stub?
- Are scheduled tasks (Celery, cron) actually deployed and running?
- Are environment variables required by the code actually set in production?
Do not report a UI state as broken or working without confirming the backend reality.

### 1. Inspect Current Product State
Review the app for:
- broken flows
- muddy UX in core paths
- stale or conflicting screens
- empty data states
- connection failures
- mismatches between setup flow and intended product quality

### 2. Inspect Data Flow
Check:
- whether live data is entering the system
- whether normalized signals are being created
- whether commitments are being derived
- whether surfaced states reflect actual downstream processing

If a dashboard is empty, determine whether the failure is:
- no source connected
- no ingestion happening
- ingestion happening but normalization failing
- normalization happening but persistence failing
- persistence happening but UI not surfacing data
- observability too weak to tell

### 3. Inspect Integration Readiness
Check first-wave integrations for:
- realistic setup method
- proper permission model
- usable connection state
- obvious testing blockers
- UX clarity in install/connect flows

### 4. Inspect Observability
Check whether it is easy to answer:
- what data got ingested
- what failed
- where it failed
- whether replay or debugging is possible

### 5. Compare to Product Truth
Reject candidate work that does not clearly support:
- commitment-assistant behavior
- cognitive load reduction
- trust and suggestion-based interaction
- realistic MVP testing
- the current source priorities

### 6. Generate Candidate Issues
For each issue, record:
- title
- evidence
- primary type
- impact
- confidence
- whether approval is likely needed

### 7. Rank Candidates
Use this default ranking sequence:
1. blockers
2. observability gaps tied to blockers
3. integration readiness in first-wave sources
4. product debt in core flows
5. safe expansions with direct MVP payoff

### 8. Emit Work Orders
Convert the top 1 to 3 items into full work orders using `work-order-template.md`.

### 9. Review Escalations
If an item is blocked by a product decision, emit a lightweight escalation instead of a fuzzy work order.

---

## Required Output Format
At the end of the inspection cycle, OpenClaw should produce:

### A. Candidate summary
A short ranked list of findings.

### B. Work orders
One or more `.md` files in the work-order format.

### C. Escalations
Only when needed, and always in the lightweight format.

### D. Deferred items
Lower-priority candidates intentionally not emitted this cycle.

---

## Suggested Candidate Summary Format

```md
# Candidate Summary

## 1. [Title]
- Type: [type]
- Priority: [priority]
- Why now: [one sentence]

## 2. [Title]
- Type: [type]
- Priority: [priority]
- Why now: [one sentence]
```

---

## Current Heuristics for Rippled
Until replaced by new direction, the cycle should treat the following as especially important:
- empty dashboard states when real data is expected
- first-wave integrations that are incomplete in realistic usage
- setup flows mixing obsolete and current UI
- lack of observability in ingestion and commitment creation
- any issue preventing meaningful end-to-end testing

---

## Example Cron Intent
This is an example operational intent, not a required implementation:

```bash
# Every weekday at 09:00 local
0 9 * * 1-5 run-openclaw-inspection-cycle
```

If the system is session-driven rather than time-driven, run it at session start instead.

---

## Stop Conditions
The cycle should not emit more work just to stay busy.

Do not emit a new work order when:
- no candidate is clearly aligned with product truth
- the remaining candidates require unresolved product decisions
- the current blockers make downstream work premature
- the likely work is too broad to verify cleanly

In those cases, emit either:
- no-op with rationale, or
- a lightweight escalation
