# Index — Rippled Platform & MVP Brief

> **Project:** Rippled (commitment intelligence engine)
> **Status:** Brief set complete — ready for build
> **Purpose:** Canonical reference for all product and technical decisions

---

## What This Is

This folder contains the complete product and engineering briefing for **Rippled** — a personal commitment intelligence engine that helps people forget fewer work commitments by quietly observing their communication and surfacing what matters, without becoming another task system.

This brief set is the **single source of truth** for all future product and technical decisions. Consult it when designing features, evaluating scope, writing technical specs, and onboarding Claude Code or other AI agents to the project.

---

## How to Read This

**If you're new — read in this order:**

1. [[Rippled - 1. Product Vision]] — What is Rippled, why it exists, what success looks like.
2. [[Rippled - 2. Product Principles Brief]] — The non-negotiable rules that govern every decision.
3. [[Rippled - 3. Commitment Domain Model Brief]] — The core data model: what a commitment is, how it's structured, how ambiguity is preserved.
4. [[Rippled - 4. Source Model Brief]] — How meetings, Slack, and email form one connected commitment fabric.
5. [[Rippled - 5. Commitment Lifecycle Brief]] — The states a commitment can occupy and how it moves between them.
6. [[Rippled - 6. Surfacing & Prioritization Brief]] — What gets shown to the user, when, and why.
7. [[Rippled - 7. MVP Scope Brief]] — Exactly what's in and out of scope for the first version.
8. [[Rippled - 8. Commitment Detection Brief]] — How Rippled identifies commitment signals from raw communication.
9. [[Rippled - 9. Clarification Brief]] — When and how Rippled resolves ambiguity or asks for input.
10. [[Rippled - 10. Completion Detection Brief]] — How Rippled infers that a commitment has been delivered or closed.

---

## Document Map

| # | Document | Layer | Key Topics |
|---|----------|-------|------------|
| 1 | [[Rippled - 1. Product Vision]] | Strategy | Vision, thesis, target user, non-negotiables |
| 2 | [[Rippled - 2. Product Principles Brief]] | Strategy | 20 product principles, decision filters, behavior rules |
| 3 | [[Rippled - 3. Commitment Domain Model Brief]] | Domain | Commitment object, evidence, ambiguity, confidence dimensions |
| 4 | [[Rippled - 4. Source Model Brief]] | Domain | Signal roles per source, cross-source model, internal vs external |
| 5 | [[Rippled - 5. Commitment Lifecycle Brief]] | Domain | States, transitions, reversibility, evidence-based progression |
| 6 | [[Rippled - 6. Surfacing & Prioritization Brief]] | Product | Main/Shortlist/Clarifications, priority dimensions, observation windows |
| 7 | [[Rippled - 7. MVP Scope Brief]] | Scope | In/out of scope, must-work items, failure conditions, success criteria |
| 8 | [[Rippled - 8. Commitment Detection Brief]] | Engineering | Detection layer, trigger classes, candidate signals, channel rules |
| 9 | [[Rippled - 9. Clarification Brief]] | Engineering | Clarification workflow, ambiguity types, observation policy, suggested values |
| 10 | [[Rippled - 10. Completion Detection Brief]] | Engineering | Completion evidence, confidence model, channel rules, auto-close |

---

## Architecture Layers

```
STRATEGY LAYER
  ├── Product Vision              [[Rippled - 1. Product Vision]]
  └── Product Principles          [[Rippled - 2. Product Principles Brief]]

DOMAIN LAYER
  ├── Commitment Domain Model     [[Rippled - 3. Commitment Domain Model Brief]]
  ├── Source Model                [[Rippled - 4. Source Model Brief]]
  └── Commitment Lifecycle        [[Rippled - 5. Commitment Lifecycle Brief]]

PRODUCT LAYER
  ├── Surfacing & Prioritization  [[Rippled - 6. Surfacing & Prioritization Brief]]
  └── MVP Scope                   [[Rippled - 7. MVP Scope Brief]]

ENGINEERING LAYER
  ├── Commitment Detection        [[Rippled - 8. Commitment Detection Brief]]
  ├── Clarification               [[Rippled - 9. Clarification Brief]]
  └── Completion Detection        [[Rippled - 10. Completion Detection Brief]]
```

---

## Key Concepts at a Glance

### The Core Object
The **commitment** is Rippled's primary domain object. It is not a task — it carries relational weight, linked evidence, preserved ambiguity, and a full lifecycle history.
→ [[Rippled - 3. Commitment Domain Model Brief]]

### The Three Sources
**Meetings**, **Slack**, and **Email** are the three first-class sources. Each can act as origin, clarification, progress, delivery, or closure evidence for any single commitment. One unified object links signals across all three.
→ [[Rippled - 4. Source Model Brief]]

### Two Commitment Classes
- **Big promises** → Main view (external/client-facing, explicit due date, higher consequence)
- **Small commitments** → Shortlist view (internal, easy to forget, cognitively costly when missed)

→ [[Rippled - 6. Surfacing & Prioritization Brief]], [[Rippled - 3. Commitment Domain Model Brief]]

### Three Surfaces
- **Main** — bigger, consequential commitments
- **Shortlist** — smaller but cognitively meaningful ones
- **Clarifications** — items needing resolution before they're fully actionable

→ [[Rippled - 6. Surfacing & Prioritization Brief]]

### Six Lifecycle States
`proposed` → `needs_clarification` → `active` → `delivered` → `closed` — plus `discarded`.
All transitions are reversible where supported by evidence.
→ [[Rippled - 5. Commitment Lifecycle Brief]]

### Capture Broadly, Surface Selectively
The most important operating principle: Rippled retains more internally than it shows. Surfaced output must earn its place.
→ [[Rippled - 2. Product Principles Brief]]

### "We" Is Not a Person
Collective ownership language must never resolve to a specific person automatically. Resolved owner stays null until clearly supported.
→ [[Rippled - 3. Commitment Domain Model Brief]], [[Rippled - 9. Clarification Brief]]

### Priority ≠ Confidence
A high-priority item can have low confidence (goes to Clarifications). A high-confidence item can be low priority (goes to Shortlist). These are always separate dimensions.
→ [[Rippled - 6. Surfacing & Prioritization Brief]], [[Rippled - 3. Commitment Domain Model Brief]]

### Observe Before Interrupting
Rippled defaults to silent observation before surfacing or asking for clarification. Ambiguity often resolves naturally. 

Default windows:
- Slack internal: up to 2 working hours
- Email internal: 1 working day
- Email external: 2–3 working days
- Meetings internal: 1–2 working days
- Meetings external: 2–3 working days

→ [[Rippled - 4. Source Model Brief]], [[Rippled - 9. Clarification Brief]]

---

## Locked MVP Decisions

These are settled and not up for redesign during the current build phase:

- **Primary user:** single person (founder/operator/service professional) — not a team workspace
- **First-class sources:** meetings, Slack, email
- **Core object:** `commitment` (not task, not note)
- **Ownership rule:** "we" never resolves automatically
- **Lifecycle:** proposed → needs_clarification → active → delivered → closed — plus `discarded`
- **Surfaces:** Main / Shortlist / Clarifications
- **Delivery ≠ Closure:** distinct states with distinct thresholds
- **Default behavior:** silent observation before surfacing or clarifying

**Out of scope for MVP:**
- Full task manager / kanban
- Multi-user team workspaces
- Native meeting bot / recorder
- Large-scale analytics
- Heavy automation or autonomous actions
- Advanced personalization/learning

→ [[Rippled - 7. MVP Scope Brief]]

---

## For Claude Code

When using this brief set to implement Rippled:

1. **Start here** — this index is your navigation hub
2. [[Rippled - 7. MVP Scope Brief]] defines exactly what must work in the first version
3. [[Rippled - 3. Commitment Domain Model Brief]] is your data model spec — use it to design schemas
4. [[Rippled - 8. Commitment Detection Brief]] defines the detection pipeline and candidate output structure
5. [[Rippled - 9. Clarification Brief]] defines the clarification object model (includes a JSON example)
6. [[Rippled - 10. Completion Detection Brief]] defines state transitions and evidence-based completion inference
7. [[Rippled - 5. Commitment Lifecycle Brief]] defines allowed state machine transitions
8. When making judgment calls about behavior — check [[Rippled - 2. Product Principles Brief]] first
9. If a brief says **"locked"** — it is. Do not redesign those decisions
10. If a brief says **"open question"** — defer it; do not implement unless explicitly scoped
11. The goal is always: **reduce cognitive burden without creating new burden**. When in doubt, do less and suggest more.

