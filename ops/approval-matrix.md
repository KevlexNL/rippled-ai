# Rippled Approval Matrix

## Purpose
This matrix defines what OpenClaw can autonomously dispatch to Trinity and what must be approved by Kevin first.

This exists to prevent drift while preserving useful autonomy.

---

## Auto-Approve Categories
OpenClaw may dispatch without approval when all of the following are true:
- the work is aligned with `product-truth.md`
- the work is bounded and testable
- the work fits one of the approved types below
- the work does not change product direction

### Approved without approval
#### 1. Blocker fixes
Examples:
- fix broken ingestion step
- restore dashboard rendering when backed by existing data
- repair setup flow regressions

#### 2. Observability improvements
Examples:
- add stage-level logs
- add replay/debug visibility
- expose failed pipeline state for diagnosis

#### 3. Integration readiness fixes inside existing source strategy
Examples:
- implement proper OAuth for already-selected sources
- fix permissions/scopes in existing integrations
- improve connection-state handling in current setup flows

#### 4. Product debt cleanup in locked core flows
Examples:
- remove obsolete views from integrations flow
- unify inconsistent setup UI patterns
- fix confusing empty-state messaging in current MVP surfaces

#### 5. Safe expansions with low strategy risk
Examples:
- backfill recent source history for current integrations
- small usability improvements that do not change product model
- instrumentation dashboards for internal debugging

---

## Approval Required Categories
Approval is required before dispatch when the work would:

### 1. Change product direction
Examples:
- make Rippled behave like a full task manager
- add major workflow surfaces beyond the current MVP core
- shift from suggestion language to assertive system claims

### 2. Expand source scope materially
Examples:
- add a new provider family not already in first-wave or clearly planned next-wave scope
- add calendar/task platform integrations before first-wave sources are functioning meaningfully

### 3. Introduce permission or privacy posture changes
Examples:
- broaden data retention behavior
- introduce access to sources or scopes not clearly implied by current strategy
- trigger marketplace or compliance decisions

### 4. Change account, billing, or org model
Examples:
- multi-user org structures
- plans, entitlements, usage tiers
- role-based workspace permissions

### 5. Resolve product ambiguity by invention
Examples:
- invent new commitment states not grounded in current product logic
- create a new review surface because the current one feels insufficient
- define notification behavior not yet anchored in product truth

---

## Decision Shortcut
Use this test:

### Dispatch automatically if the task changes:
- quality
- reliability
- realism
- observability
- consistency

### Ask for approval if the task changes:
- product meaning
- user mental model
- strategic scope
- privacy posture
- source scope

---

## Escalation Standard
When approval is required, OpenClaw must emit a short decision request using this format:

```md
## Escalation
**Question:** [one yes/no or forced-choice question]
**Why blocked:** [one sentence]
**Options:** [A / B / C]
**Default recommendation:** [one line]
**Impact if unanswered:** [one line]
```

---

## Current Default Recommendations
Until replaced, default recommendations should lean toward:
- realism over temporary hacks when a hack distorts MVP learning
- fixing blockers before adding breadth
- improving first-wave sources before adding new ones
- improving trust in core flows before polishing edge flows
