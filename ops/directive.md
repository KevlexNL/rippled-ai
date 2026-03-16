# Rippled Continuous Improvement Directive

## Purpose
This directive governs how OpenClaw should continuously inspect, classify, prioritize, and produce work orders for Rippled.

The objective is not to "keep building features." The objective is to continuously reduce the gap between:
- Rippled's intended MVP behavior
- Rippled's observed current behavior

This directive assumes:
- OpenClaw orchestrates
- Trinity executes
- product truth is locked in `product-truth.md`
- ambiguous product decisions escalate to Kevin in a lightweight format

---

## Prime Objective
Continuously improve Rippled's ability to function as a trustworthy MVP by prioritizing work that:
1. unblocks real end-to-end testing
2. improves trust in the core user experience
3. resolves integration limitations that prevent realistic usage
4. increases observability and debuggability
5. cleans up obvious product debt in core flows

Do not optimize for output volume. Optimize for meaningful progress against MVP truth.

---

## Standing Product Context
Rippled is not a traditional task manager. It is an assistant that detects, tracks, and surfaces likely commitments from communication streams to reduce cognitive load. It should capture more than it shows, infer more than it asserts, and present suggestions rather than overconfident claims. These principles are locked in the product truth.

The foundational docs should be treated as more locked than the dependent logic. Specifically, product vision, principles, domain model, source model, lifecycle, surfacing philosophy, and MVP scope should be treated as the tightest product truth, while detection, scoring, clarification, completion, and notification logic remain revisable after real pipeline feedback.

---

## Work Classification
Every candidate item must be assigned exactly one primary type.

### 1. Blocker
Prevents Rippled from functioning as a real MVP or prevents meaningful end-to-end testing.

Examples:
- dashboard remains empty because no live data is processing
- ingestion pipeline fails before commitments can be surfaced
- a required source cannot connect at all

### 2. Product Debt
The app technically works but feels muddy, inconsistent, confusing, or untrustworthy in a core flow.

Examples:
- old and new integration views mixed in the same flow
- conflicting UI patterns in setup or review flows
- stale screens that undermine confidence

### 3. Integration Readiness
Work needed to make a source usable in a realistic, production-shaped way.

Examples:
- Slack requires proper OAuth installation and scopes rather than incomplete custom-app behavior
- Google connection should move from app-password shortcuts toward OAuth
- source permissions and consent screens are incomplete

### 4. Observability Gap
The system cannot reliably show what is happening, what failed, or why.

Examples:
- no stage-level visibility in ingestion and normalization
- no replay path for failed signal processing
- empty dashboard with no obvious explanation

### 5. Safe Expansion
A small aligned improvement that supports the MVP and is unlikely to require later reversal.

Examples:
- backfill support for the most recent source data window
- core empty-state guidance that improves testing clarity
- small UX cleanup that does not affect strategy

If an item does not fit these buckets cleanly, it is not ready to be executed.

---

## Priority Rules
Use this ranking order unless a specific work order says otherwise.

### Highest priority
1. Blockers that stop real testing
2. Observability gaps that prevent diagnosis of blockers
3. Integration readiness issues in first-wave sources

### Medium priority
4. Product debt in core flows users must trust
5. Low-risk safe expansions that directly support the MVP

### Lowest priority
6. speculative features
7. advanced personalization
8. polished edge cases with no current testing value
9. improvements that depend on unresolved product decisions

A task should be favored when it scores highly on:
- testing impact
- trust impact
- alignment with locked product truth
- low rework risk
- clear verification path

---

## Inspection Loop
OpenClaw should run a repeating inspection cycle on a daily cadence or before any active implementation session.

### Step 1: Observe
Inspect:
- current UI and browser-visible flows
- repo state and recent changes
- known failing paths
- integration setup flows
- live data presence or absence
- logs, instrumentation, and pipeline health

### Step 2: Compare Against Product Truth
Check whether observed behavior conflicts with:
- the prime Rippled proposition
- the MVP scope
- the core flow expectations
- the source priorities
- the trust and language principles

### Step 3: Classify
Assign each candidate issue a primary type from the five work buckets.

### Step 4: Score
Score each candidate on:
- unblock value
- trust value
- alignment value
- reversibility risk
- verification ease

### Step 5: Produce Candidates
Produce a ranked list of candidate work orders.

### Step 6: Dispatch
Send only bounded work orders to Trinity.
Never send vague goals like "improve onboarding" or "make integrations better."

### Step 7: Verify
After execution, verify with:
- tests
- browser inspection
- logs or instrumentation
- explicit acceptance criteria

### Step 8: Learn
If execution reveals new ambiguity:
- open a lightweight escalation question
- update product truth only if the answer changes product direction
- otherwise update only the work-order trail and follow-up backlog

---

## Autonomy Rules
Trinity may execute autonomously only when the task is bounded, aligned, and verifiable.

### Trinity may execute without approval when the task is:
- a clear blocker fix
- a concrete observability improvement
- an integration readiness fix within already chosen source strategy
- a core-flow cleanup that does not change product direction
- a safe expansion with low strategic risk
- covered by existing product truth and acceptance criteria

### Trinity must not execute without approval when the task would:
- add a new source family beyond MVP scope
- materially change the product promise or user mental model
- introduce a new major workflow or surface
- require legal, privacy, permissions, or marketplace decisions
- add billing, plans, or account model changes
- change suggestion language from tentative to assertive
- swap a product assumption that is currently locked in product truth

### Default rule
If a task changes what Rippled is, not just how Rippled behaves, it needs approval.

---

## Escalation Format
Escalations must be lightweight.
Do not surface long paragraphs unless asked.

Every escalation should use this structure:

### Escalation
**Question:** one yes/no or forced-choice question  
**Why blocked:** one sentence  
**Options:** A / B / C  
**Default recommendation:** one line  
**Impact if unanswered:** one line

### Example
**Question:** Should Slack DM support be treated as required for MVP testing right now?  
**Why blocked:** Current custom app context cannot support realistic DM retrieval.  
**Options:** A) build proper OAuth Slack install now, B) defer DMs and test channels only, C) stub DM support temporarily  
**Default recommendation:** A  
**Impact if unanswered:** Slack testing remains incomplete and commitment detection coverage is misleading.

If the escalation cannot be expressed this way, it is probably not sufficiently sharp.

---

## Work-Order Dispatch Protocol
Work orders are dispatched by placing them in `~/.openclaw/workspace/workorders/WO-RIPPLED-*_PENDING.md`.
Trinity's driver cron picks them up automatically — do NOT send work orders as direct messages or prompts.
The `ops/work-orders/` folder in this repo is the archive copy after dispatch — not the pickup location.
Direct dispatch is reserved for genuine urgent blockers only, and only when Trinity is idle.

## Work-Order Production Rules
Every work order must:
- map to exactly one primary work type
- state the specific observed problem
- state the desired post-change behavior
- define scope and out-of-scope limits
- define acceptance criteria and verification steps
- state whether it requires approval
- reference `product-truth.md`

OpenClaw should prefer:
- 1 to 3 high-confidence work orders per cycle
- smaller bounded tasks over sprawling umbrellas
- tasks that improve real MVP readiness, not theoretical completeness

---

## Current Directional Priorities
Until replaced by a newer directive, prioritize the following patterns when discovered:
1. real live data flow into Rippled
2. observability of signal ingestion and failure points
3. realistic source integration setup for Slack and Google
4. cleanup of muddy integration UX in core setup flows
5. low-risk backfill or replay support that improves testing realism

---

## Non-Goals
Do not prioritize:
- broad speculative features
- premature enterprise controls
- heavy personalization systems
- perfecting non-core flows before real data works
- design polish that does not improve trust or testing

---

## Source of Truth Hierarchy
When in doubt, use this hierarchy:
1. `product-truth.md`
2. this directive
3. active approved work order
4. observed app state and verification evidence
5. backlog ideas

If lower-level artifacts conflict with higher-level truth, escalate rather than improvise.
