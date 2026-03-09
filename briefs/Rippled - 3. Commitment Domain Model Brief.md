---
tags: [rippled, domain-model, commitment, data-model]
brief: "03 — Commitment Domain Model"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Commitment Domain Model Brief

## Purpose

Define the core domain model for Rippled’s commitment engine so product, design, and engineering share the same understanding of what the system is detecting, storing, updating, and surfacing.

This brief exists to reduce ambiguity around the central object of the platform: the commitment.

It should make clear:

- what a commitment is
- what is not a commitment
- how commitments differ from raw communication signals
- how commitments evolve over time
- how ambiguity, evidence, and confidence should be preserved
- how “big promises” and “small commitments” differ in the model

This is a product-domain brief, not a database schema spec. It defines the conceptual model that technical implementation should follow.

---

## Why this matters

Rippled only works if it models work commitments in a way that matches how people actually experience mental load.

The platform is not trying to become a general task manager. It is trying to reduce cognitive burden created by commitments that emerge naturally in communication and then risk being forgotten, delayed, or left unclear.

That means the domain model must support all of the following at once:

- soft and hard commitments
- explicit and implicit commitments
- internal and external expectations
- ambiguity without false certainty
- later clarification from new signals
- inferred delivery/completion without pretending proof is absolute

If the model is too narrow, Rippled will miss important commitments.  
If the model is too broad, Rippled will become noisy and untrustworthy.  
If the model is too rigid, it will fail to reflect how work actually happens across meetings, Slack, and email.

---

## Product context

Rippled is a communication-based commitment intelligence engine.

It ingests work communication across:

- meetings
- Slack
- email

Later, additional sources like calendar and task systems may be added.

Its job is to detect, unify, track, and surface likely commitments that matter to one user, while preserving uncertainty and reducing cognitive load.

The system should capture more than it shows, infer more than it asserts, and surface only what is likely to be useful.

---

# 1. Core domain concepts

## 1.1 Communication Signal

A communication signal is any raw or normalized unit of input from a source system that may contain information relevant to a commitment.

Examples:

- a Slack message
- a Slack thread reply
- an email message
- a meeting transcript segment
- a meeting action-item section
- an outbound email with an attachment
- a message saying “done” or “just sent it”

Signals are not commitments. They are evidence-bearing events from which commitments may be inferred, clarified, updated, or completed.

A signal may play one or more roles:

- commitment origin signal
- clarification signal
- progress signal
- delivery/completion signal
- conflict signal

Signals must always be preserved independently of the commitment objects derived from them.

---

## 1.2 Commitment Candidate

A commitment candidate is a provisional interpretation that one or more signals may imply a trackable future obligation, follow-up, or deliverable.

This is the system’s intermediate object before a commitment is fully shaped or surfaced.

A candidate may still be:

- ambiguous
- low confidence
- incomplete
- unresolved as to owner or deadline
- later discarded
- later merged into a stronger commitment record

Candidates are important because Rippled should optimize for recall internally before precision in what it surfaces.

Not every candidate becomes a surfaced commitment.

---

## 1.3 Commitment

A commitment is Rippled’s primary domain object.

A commitment represents a likely future-oriented work obligation, promise, follow-up, deliverable, or responsibility that emerged through communication and may require later tracking, clarification, delivery, review, or closure.

A commitment may be:

- explicit or implicit
- internal or external
- large or small
- clear or partially ambiguous
- active, delivered, closed, or reopened

A commitment is not merely a task. It is a richer object that preserves:

- evidence
- ambiguity
- inferred ownership
- inferred timing
- linked communication history
- evolving state over time

The commitment is the unified object that later signals should attach to and update.

---

## 1.4 Evidence

Evidence is the set of linked signals and interpreted references that support the existence, shape, progress, delivery, or closure of a commitment.

Evidence may support:

- that the commitment exists
- who likely owns it
- when it is likely due
- what the deliverable is
- whether it was delivered
- whether it was closed
- whether it was reopened
- whether conflicting information exists

Rippled should never rely on naked interpretation without preserved evidence references.

Every surfaced commitment should be traceable back to supporting evidence.

---

## 1.5 Ambiguity

Ambiguity is a first-class property of the domain.

A commitment may be ambiguous in:

- ownership
- timing
- deliverable
- target
- status
- whether it is truly a commitment at all

Ambiguity should not be erased just to make the data look cleaner.

The system should preserve ambiguity explicitly rather than forcing false resolution.

---

## 1.6 Suggested Value

A suggested value is a system-proposed interpretation of a missing or uncertain field that is useful enough to retain, but not certain enough to present as fact.

Examples:

- likely next step
- likely owner
- likely due date
- likely completion/delivery interpretation

Suggested values should be stored separately from resolved values where possible.

For MVP, suggested values are especially important because the system should help reduce cognitive load without overclaiming certainty.

---

# 2. What counts as a commitment

A statement or signal should count as a commitment when it plausibly implies that a future action, response, delivery, follow-up, handoff, or responsibility now exists and another person, group, or workflow is likely to rely on it being fulfilled.

This includes both explicit and implicit commitments.

## 2.1 Explicit commitments

Explicit commitments directly state future intent, responsibility, or delivery.

Examples:

- “I’ll send the proposal tomorrow.”
- “John will follow up with procurement.”
- “We’ll get that over by Friday.”
- “Let me look into that.”
- “I’ll review it tonight.”
- “I’ll reply after lunch.”

These are usually stronger candidates than implicit commitments.

---

## 2.2 Implicit commitments

Implicit commitments do not always sound like formal promises, but still create a reasonable expectation that work will be done.

Examples:

- “Next step is pricing from us.”
- “Can someone send the revised deck?”
- “We still need to update the proposal.”
- “I can take first pass.”
- “Let’s get that to the client this week.”
- “I’ll circle back once I confirm.”

Implicit commitments are especially common in:

- Slack
- internal meetings
- service delivery coordination
- founder/operator environments

Implicit commitments should be captured, but usually with lower certainty unless strengthened by later signals.

---

## 2.3 Commitment types included in scope

The model should include at least these categories:

- promise to send something
- promise to review something
- promise to reply or follow up
- promise to deliver work product
- promise to investigate or look into something
- promise to make an introduction
- promise to coordinate or arrange something
- promise to update or revise something
- delegated responsibility accepted by someone
- next step implied to belong to a person or group
- client-facing delivery commitment
- internal delivery/handoff commitment

The model should support later extension to more types, but should not overfit to a fixed closed list too early.

---

# 3. What is not a commitment

The following should not automatically become commitments unless additional context strengthens them.

## 3.1 Brainstorming without obligation

Examples:

- “We could maybe do that next quarter.”
- “It might make sense to revise pricing.”
- “One option is to send an overview.”

## 3.2 Historical statements

Examples:

- “We sent that last week.”
- “I already took care of that.”
- “We reviewed this yesterday.”

These may be evidence of completion or history, but not new commitments by themselves.

## 3.3 Pure discussion of possibilities

Examples:

- “Should we send a proposal?”
- “Do we want to follow up?”
- “Maybe someone can take this.”

These may become commitments if later accepted.

## 3.4 Requests without acceptance

Examples:

- “Can you send the proposal?”
- “Please follow up with the client.”
- “Can someone handle this?”

These are requests or obligations being introduced, but should usually not become resolved commitments until some acceptance, assignment, or clear responsibility implication exists. They may still become candidate obligations worth observing.

## 3.5 Status commentary without future obligation

Examples:

- “This is delayed.”
- “That was messy.”
- “We’re still waiting.”

These may add context to an existing commitment but are not necessarily commitments on their own.

---

# 4. Big promises vs small commitments

This distinction is part of the product model, not merely a UI choice.

Both big promises and small commitments matter.  
The difference is mainly how they should be prioritized and surfaced.

## 4.1 Big Promise

A big promise is a commitment more likely to belong in the main commitments list.

For MVP, classification priority should be:

1. external vs internal
2. explicit due date
3. business consequence

Typical examples:

- “I’ll send the proposal to the client by Friday.”
- “We’ll deliver revised numbers tomorrow.”
- “I’ll get legal the agreement today.”
- “We’ll follow up with the client Monday.”

Characteristics:

- more likely external/client-facing
- more likely tied to a due date
- more likely tied to a meaningful consequence if missed
- more likely to deserve faster surfacing/escalation

## 4.2 Small Commitment

A small commitment is still a real commitment, but more likely to belong in the shortlist than the main commitments list.

Examples:

- “Let me look into that.”
- “I’ll send that over later.”
- “I’ll check with ops.”
- “I’ll reply once I’m back at my desk.”
- “I’ll review that.”

Characteristics:

- often internal
- often less formal
- often missing hard deadlines
- may still create significant cognitive burden if forgotten
- important for trust and follow-through even if lower consequence

## 4.3 Important principle

Big vs small is not the same as confidence.

A small commitment may be high confidence and worth surfacing in the shortlist.  
A big promise may be low confidence and still require clarification.

Priority class and confidence must remain separate concepts.

# 5. Commitment structure

Each commitment should conceptually contain the following fields.

## 5.1 Identity and linkage

- commitment ID
- user ID / owner context
- unified commitment record
- linked candidate history
- linked source signals
- linked evidence references
- processing/version history

## 5.2 Meaning

- title
- description
- commitment text or normalized summary
- commitment type
- big promise vs small commitment classification
- internal vs external classification

## 5.3 Ownership

- owner candidates
- resolved owner
- ownership ambiguity flags
- likely owner suggestion

Important rule for MVP:

- collective references like “we” should not resolve to a person automatically
- likely owner may be suggested, but resolved owner should remain null unless supported clearly

## 5.4 Timing

- deadline candidates
- resolved deadline
- vague time phrases
- timing ambiguity flags
- likely due date suggestion

Important rule for MVP:

- vague time phrases such as “soon,” “later,” or “end of month” should not become precise resolved deadlines without explicit support
- they may remain as candidate or suggested timing interpretations

## 5.5 Deliverable / next step

- deliverable or intended action
- target object/entity if inferable
- likely next step suggestion
- deliverable ambiguity flags

Suggested values should be allowed here even when strict resolution is not possible.

## 5.6 Status / lifecycle

- active
- delivered
- closed
- reopened
- needs clarification
- discarded or suppressed, where relevant internally

The exact state machine is defined elsewhere, but the domain model must support non-linear transitions.

## 5.7 Confidence

Separate confidence dimensions should be supported:

- commitment confidence
- owner confidence
- deadline confidence
- delivery confidence
- closure confidence
- transcript/message clarity confidence where relevant
- overall actionability confidence

## 5.8 Evidence and explanation

- supporting evidence items
- supporting signals
- explanation of why Rippled thinks this is a commitment
- explanation of missing pieces
- explanation of why delivery/closure may be inferred

---

# 6. Source relationship model

A commitment should not belong to a single signal.  
It should be a unified object with many linked signals over time.

## 6.1 One commitment, many signals

Example:

- meeting creates the first commitment signal
- Slack later clarifies owner
- email later confirms delivery
- reply later requests revision
- commitment reopens

All of these should remain linked to one commitment where they describe the same underlying obligation.

## 6.2 Signals may play different roles

A signal may be categorized as:

- origin
- clarification
- progress
- delivery
- closure
- conflict
- reopening

## 6.3 Later signals update, but do not erase history

Later signals may:

- strengthen a field
- clarify a field
- contradict a field
- reopen a closed or delivered item
- move status forward or backward

But earlier evidence should remain visible and auditable.

## 6.4 Latest signal is not always truth

Later signals usually matter more, but not absolutely.

Examples:

- later explicit clarification should usually supersede earlier vagueness
- later vague or conflicting language may reduce certainty rather than cleanly replacing earlier values

The model must preserve conflict and ambiguity when needed.

---

# 7. Internal capture vs surfaced output

The domain model must support a difference between what Rippled captures and what Rippled surfaces.

## 7.1 Internal capture layer

Rippled should retain:

- more candidates
- more weak signals
- more ambiguity
- more suggested values
- more evidence
- more provisional states

This helps avoid missing meaningful commitments.

## 7.2 Surfaced output layer

Rippled should surface only the subset most likely to reduce cognitive load.

This includes:

- main commitments
- shortlist items
- clarification items

Not every captured commitment candidate deserves surfacing.

## 7.3 Important principle

The model should allow internal richness without requiring all of it to appear in the user-facing product.

---

# 8. Ownership model

Ownership is often the most fragile part of the commitment model.

## 8.1 Owner candidate

An owner candidate is any plausible person or group linked to the commitment by language, role, thread context, or interaction history.

## 8.2 Resolved owner

A resolved owner is the best current explicit or strongly supported owner interpretation.

For MVP:

- must generally be a named individual
- may remain null when unresolved
- should not default from “we”

## 8.3 Likely owner suggestion

This is a softer inference than resolved owner.

Examples:

- likely account rep
- likely founder
- likely assistant
- likely person who accepted request in thread

This may be useful in clarifications and internal ranking even when resolved owner remains null.

## 8.4 Ownership ambiguity states

Examples:

- missing owner
- vague collective owner
- multiple plausible owners
- conflicting owners across signals

These should be explicitly stored.

---

# 9. Timing model

Timing needs similar treatment.

## 9.1 Deadline candidate

Any detected or inferred time expectation connected to a commitment.

Examples:

- tomorrow
- Friday
- end of month
- after lunch
- next week

## 9.2 Resolved deadline

A normalized time expectation supported strongly enough to be treated as the best current operative due date.

## 9.3 Vague time

Some timing references should remain vague rather than falsely normalized.

Examples:

- soon
- later
- when I can
- sometime this week
- end of month without specific date context

## 9.4 Timing ambiguity states

Examples:

- missing deadline
- vague deadline
- conflicting deadlines
- changed deadline
- deadline inferred but weak

These should remain part of the commitment record.

---

# 10. Delivery, completion, and closure

These should be distinct in the model.

## 10.1 Delivered

Delivered means the promised output or action appears to have been performed or sent.

Examples:

- outbound email with promised attachment
- Slack “just sent it”
- evidence that proposal file was delivered
- reply with review/comments after promising review

Delivered does not necessarily mean the commitment is fully closed.

## 10.2 Closed

Closed means the commitment no longer appears to require ongoing attention from the user.

This may happen because:

- the deliverable was sent and no more action is expected
- the recipient acknowledged or the workflow moved on
- a configured waiting period elapsed after delivery
- the user or later signals indicate the loop is complete

## 10.3 Reopened

A commitment may reopen if:

- revision is requested
- follow-up is requested
- delivery failed
- a linked later signal implies the original obligation is still active
- new unresolved work emerges from the same commitment chain

## 10.4 Important principle

Delivered and closed should be reversible states where signals support it.  
The model should not assume a one-direction lifecycle.

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 4. Source Model Brief]] | How signals from each source populate this domain model |
| [[Rippled - 5. Commitment Lifecycle Brief]] | The full state machine for the lifecycle concepts defined here |
| [[Rippled - 6. Surfacing & Prioritization Brief]] | How the big promise / small commitment split maps to surfaces |
| [[Rippled - 8. Commitment Detection Brief]] | How raw signals become commitment candidates that feed this model |
| [[Rippled - 9. Clarification Brief]] | How ambiguity and suggested values in this model become clarification objects |
| [[Rippled - 10. Completion Detection Brief]] | How delivery and closure states in this model are inferred from evidence |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |

