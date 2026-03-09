---
tags: [rippled, lifecycle, states, commitment, domain-model]
brief: "05 — Commitment Lifecycle"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Commitment Lifecycle Brief

## Purpose

Define the lifecycle of a commitment inside Rippled so the platform can represent work faithfully without pretending certainty, without collapsing everything into a simple task checkbox, and without increasing cognitive load.

This brief specifies:

- the states a commitment can occupy
- what those states mean
- how commitments move between them
- what evidence or ambiguity drives transitions
- how delivered and closed differ
- how commitments can reopen
- what Rippled should surface vs quietly track

This lifecycle should work across commitments derived from meetings, Slack, and email.

---

## Why this matters

A traditional task lifecycle is too simplistic for Rippled.

Rippled is not trying to model only “to do” and “done.” It is trying to model the reality of work commitments, where:

- something can be promised but still unclear
- something can be delivered but not yet accepted
- something can appear complete and then come back for revision
- something can quietly expire or close without explicit confirmation
- something can stay ambiguous for a while without needing immediate interruption

The lifecycle must therefore support:

- uncertainty
- evidence accumulation
- low-noise surfacing
- reversible interpretation
- channel-linked reality rather than rigid task logic

---

## Core lifecycle philosophy

The lifecycle should follow these product principles:

1. **Do not confuse detection with truth**  
   A detected commitment is not automatically a fully trusted obligation.

2. **Do not confuse delivery with closure**  
   Sending or delivering something does not always mean the loop is closed.

3. **Do not assume linear progress**  
   Work often reopens, changes, or becomes active again.

4. **Prefer evidence over assumption**  
   State transitions should be supported by signals, not optimistic guesses.

5. **Track more internally than you surface**  
   The lifecycle may contain more nuance than the user sees in primary views.

6. **Avoid forcing unnecessary review**  
   Not every ambiguous or incomplete item deserves immediate interruption.

---

## Lifecycle levels

There are two related but distinct concepts Rippled must track:

### 1. Commitment existence / trust

Is this a real commitment worth treating as a trackable object?

### 2. Commitment progress / status

Assuming it is real enough to track, where is it in the work lifecycle?

Both matter. A commitment can be:

- high-confidence and active
- low-confidence and proposed
- delivered but still unresolved
- closed and later reopened

---

## Primary lifecycle states

For MVP, Rippled should support the following commitment states:

1. **proposed**
2. **needs_clarification**
3. **active**
4. **delivered**
5. **closed**
6. **discarded**

These are the canonical states.

---

## State definitions

## 1. Proposed

### Meaning

Rippled has enough evidence to believe a commitment may exist, but not enough confidence or completeness to treat it as an active tracked commitment yet.

### Typical characteristics

- likely commitment detected
- some missing or weak fields
- may still be clarified by future signals
- not yet strong enough to fully surface as active
- may still become active, need clarification, or be discarded

### Typical examples

- “Let me look into that”
- “We should get that over to them”
- “Next step is pricing from us”
- “I’ll send that” with weak context and no clear target

### Use in product

- may remain internal for a short observation period
- may appear in shortlist or clarification workflows depending on confidence and importance
- should not be presented as established fact

---

## 2. Needs Clarification

### Meaning

Rippled believes there is a meaningful commitment signal worth tracking, but key details remain too weak, missing, or conflicting to proceed confidently without clarification or further evidence.

### Typical reasons

- owner unresolved
- timing too vague
- deliverable unclear
- later signals conflict
- commitment is plausible but not yet actionable enough
- a vague later update weakens certainty rather than resolving it

### Typical examples

- “We’ll send the proposal tomorrow” with no named owner
- “I’ll get this done soon”
- meeting says Friday, later email suggests end of month
- “Can someone take this?” followed by partial acknowledgement

### Use in product

- belongs in Clarifications view when worth surfacing
- may remain quietly observed before surfacing
- should include suggested values where safe
- should prefer suggestion language, never certainty language

---

## 3. Active

### Meaning

Rippled considers the commitment sufficiently real and sufficiently trackable to be treated as an in-progress obligation.

### Typical characteristics

- commitment is credible enough to track
- action or deliverable is reasonably clear
- owner may be resolved or still suggested depending on policy
- due date may be resolved, suggested, or absent
- not yet delivered

### Important nuance

A commitment can be active even if it lacks a hard deadline, provided it is still meaningful to track and likely to create expectation or cognitive burden.

### Typical examples

- “I’ll send the revised deck this afternoon”
- “I’ll follow up with the client”
- “Let me look into that” once context and responsibility are sufficiently clear
- external email promise to send something later

### Use in product

- may appear in Main or Shortlist depending on priority class
- should represent current tracked work
- should remain linked to evolving evidence

---

## 4. Delivered

### Meaning

Rippled has evidence that the promised work, handoff, response, or artifact has been delivered or performed, but the commitment loop may not yet be fully closed.

### Typical characteristics

- a send/done/handled signal exists
- outbound email may match promised delivery
- Slack may indicate completion
- attachment or artifact may support delivery
- feedback, approval, acceptance, or inactivity resolution may still be pending

### Typical examples

- promised proposal was emailed
- promised intro email was sent
- “Done, just sent it”
- “Handled” in Slack with supporting context
- draft shared for review

### Why this is distinct from closed

Many commitments create an expectation beyond raw delivery:

- review may still be pending
- revision may still be requested
- client may still be waiting to respond
- internal handoff may still need onward delivery to the client

### Use in product

- may still remain visible
- may later auto-close after configured inactivity window
- may return to active if revision or rejection signals appear

---

## 5. Closed

### Meaning

Rippled considers the commitment cycle complete enough that it no longer requires active attention.

### Typical paths to closed

- explicit approval or acceptance
- explicit acknowledgement of completion
- no follow-up after configurable time window following delivery
- downstream evidence indicates the loop is effectively done
- user manually confirms closure

### Important nuance

Closed does not mean Rippled knows with absolute certainty that all value exchange is complete. It means the item no longer deserves active cognitive space under current evidence and rules.

### Typical examples

- client confirms receipt and approval
- user marks item as no longer relevant
- delivered proposal receives no response and auto-closes after configured period
- internal request was fulfilled and no further follow-up emerges

### Use in product

- generally removed from active attention surfaces
- preserved in history and evidence trail
- can reopen if later signals justify it

---

## 6. Discarded

### Meaning

Rippled no longer believes the detected signal should be treated as a commitment worth tracking.

### Typical reasons

- false positive
- hypothetical language
- discussion of already-completed work
- conversational noise
- weak signal never strengthened during observation window
- later evidence contradicts commitment interpretation

### Typical examples

- “We could maybe look into that later”
- “Last week I sent that over”
- brainstorming with no implied ownership or expectation
- weak candidate that never resolves into real obligation

### Use in product

- should remain auditable internally
- generally should not surface to the user
- useful for debugging, tuning, and learning

---

## State model overview

The lifecycle should be treated as a flexible state machine, not a one-way pipeline.

A commitment may move:

- proposed → active
- proposed → needs_clarification
- proposed → discarded
- needs_clarification → active
- needs_clarification → discarded
- active → delivered
- active → closed
- active → needs_clarification
- delivered → closed
- delivered → active
- closed → active
- closed → delivered in rare evidence-reconstruction cases only
- any non-discarded state → discarded only when clearly invalidated or merged away by policy

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 3. Commitment Domain Model Brief]] | The domain objects whose states this lifecycle governs |
| [[Rippled - 4. Source Model Brief]] | How source signals trigger lifecycle transitions |
| [[Rippled - 6. Surfacing & Prioritization Brief]] | Which lifecycle states map to which surfaced views |
| [[Rippled - 9. Clarification Brief]] | The `needs_clarification` state and how it's managed |
| [[Rippled - 10. Completion Detection Brief]] | How delivered and closed states are inferred from evidence |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |