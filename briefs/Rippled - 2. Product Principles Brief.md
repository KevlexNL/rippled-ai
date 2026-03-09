---
tags: [rippled, strategy, principles, product]
brief: "02 — Product Principles"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Product Principles Brief

## Purpose

This document defines the non-negotiable product principles that should guide Rippled’s product decisions, system behavior, UX, copy, and prioritization.

Rippled is not meant to become another task manager, notification machine, or AI system that confidently invents certainty where none exists. Its value depends on reducing cognitive load while preserving trust.

These principles should be used as decision filters when designing features, workflows, interfaces, ranking logic, and AI-assisted suggestions.

---

## Why this matters

The platform will operate in an area where small mistakes have outsized impact.

If Rippled is too passive, it misses real commitments and becomes forgettable.  
If Rippled is too noisy, it becomes another source of cognitive fatigue.  
If Rippled sounds too certain, it breaks trust.  
If Rippled tries to manage everything, it becomes the very burden it is supposed to relieve.

These principles exist to keep the product aligned with its actual job:

> Help users forget fewer commitments, remember important follow-through, and reduce mental overhead without forcing them into a new system of maintenance.

---

## Product thesis

Rippled should function as an intelligent support layer across communication, not as a destination task system.

It should observe work where it already happens, detect meaningful commitments, preserve ambiguity when needed, and surface only what is likely to help.

Its role is not to declare truth. Its role is to make useful suggestions, identify likely gaps, and help the user avoid avoidable drop-offs in follow-through.

---

## Core principles

## 1. Reduce cognitive load, not just missed deadlines

Rippled exists to reduce the mental burden of keeping track of promises, follow-ups, and unresolved work.

This includes major external commitments, but it also includes the many smaller promises that create background stress:

- “I’ll look into it”
- “I’ll send that over”
- “Let me get back to you”
- “We should follow up on that”

A product decision is good if it reduces:

- “oh shit, I forgot”
- “who was supposed to handle this?”
- “when did I say I’d do that?”
- “did we ever send that?”
- “is someone waiting on me?”

A product decision is bad if it creates:

- more checking
- more triage
- more list maintenance
- more notifications
- more doubt about what matters

**Implication:** Rippled should care about both big promises and small commitments, because both affect mental load, even if they are surfaced differently.

---

## 2. Capture broadly, surface selectively

The system should be allowed to notice more than it shows.

Internally, Rippled may retain a broader set of candidate commitments, weak signals, clarifications, and evidence.  
Externally, it should surface only the subset most likely to reduce burden or prevent a miss.

This distinction is critical.

If Rippled only captures what it is already certain about, it will miss too many real commitments.  
If Rippled surfaces everything it captures, it will become noisy and unusable.

**Principle:** broader internal recall, narrower surfaced precision.

**Implication:** the platform should separate:

- captured signals
- unified commitment records
- surfaced commitments
- clarification-worthy items
- notification-worthy items

Not every captured item deserves user attention.

---

## 3. Infer more than you assert

Rippled should be comfortable making internal inferences, but cautious in how it presents them.

The product can infer:

- likely owner
- likely next step
- likely due timing
- likely completion
- likely relation between signals

But it should not present those inferences as facts unless evidence is strong enough.

The system should favor language like:

- “Likely follow-up”
- “Seems unresolved”
- “May still need an owner”
- “Looks like this was delivered”
- “Possibly related to…”

Over language like:

- “This is due Friday”
- “John owns this”
- “This was completed”
- “This definitely came from…”

unless confidence is genuinely high and the evidence is clear.

**Implication:** product language, scoring, UI labels, and automation thresholds should all reflect probabilistic support, not certainty theater.

---

## 4. Trust is more important than cleverness

A clever system that overreaches will fail faster than a modest system that remains trustworthy.

Rippled should avoid:

- pretending to know more than it does
- over-resolving ambiguous ownership
- inventing deadlines
- flattening vague signals into false precision
- auto-promoting weak commitments as if they are settled truth

Users should feel:

- “this catches useful things”
- “this is careful”
- “this helps me think less”
- “this doesn’t bullshit me”

They should not feel:

- “this keeps confidently guessing”
- “this creates work”
- “this says things as if they’re certain when they’re not”

**Implication:** whenever there is tension between impressiveness and trustworthiness, trust wins.

---

## 5. The product should live where work already happens

Rippled should work through the communication streams where commitments actually emerge:

- meetings
- Slack
- email
- later: calendar and adjacent systems

The product should not require users to recreate work in a separate manual structure just to benefit from it.

Its intelligence should come from observing communication and linked evidence, not from asking the user to maintain yet another workflow.

**Implication:** Rippled should be communication-native, not task-manager-native.

---

## 6. A commitment is more important than a task

Rippled is not built around generic tasks. It is built around commitments.

A commitment carries relational weight:

- someone is expecting something
- a promise has been implied or made
- work is now socially or operationally owed
- forgetting it creates stress, disappointment, or delay

This is why small commitments matter so much.  
They are often not “important enough” for task systems, but still important enough to weigh on people.

**Implication:** the core object model should center on commitment records linked to signals and evidence, not generic task items.

---

## 7. Small commitments matter because cognitive burden is cumulative

The product should not focus only on high-consequence commitments.

Many users remember the biggest promises because those are already salient.  
The burden often comes from the accumulation of smaller obligations that are easy to forget but hard to mentally release.

Examples:

- “I’ll reply later”
- “I’ll review that”
- “I’ll send the invoice”
- “I’ll check with X”
- “I’ll make the intro”

Each may be small in isolation. In aggregate, they create a constant background load.

**Implication:** Rippled should distinguish between bigger promises and smaller commitments, but should not dismiss the latter as noise.

---

## 8. Prioritization should reflect consequence and burden

Not all commitments should be surfaced the same way.

Rippled should distinguish between:

- **big promises** — more consequential, more visible, often external, often deadline-bearing
- **small commitments** — lighter-weight but cognitively costly when forgotten

For MVP, priority should be shaped primarily by:

1. external vs internal
2. explicit due date
3. business consequence

This allows the product to preserve both relevance and mental relief.

**Implication:** different classes of commitments should surface differently:

- main commitments
- shortlist
- clarification queue

Priority should not be confused with certainty.

---

## 9. Priority and confidence are separate concepts

A commitment can be:

- high priority and low confidence
- low priority and high confidence
- high burden and low consequence
- high consequence and low clarity

Rippled should not collapse all of that into one score.

Priority answers:

- how much this matters
- how prominently it should surface

Confidence answers:

- how sure we are about what it is
- how sure we are who owns it
- how sure we are when it is due
- how sure we are whether it was delivered

**Implication:** the product should keep these concepts separate in logic and presentation.

---

## 10. Preserve ambiguity instead of fabricating clarity

Ambiguity is not a product failure. False clarity is.

If ownership is unclear, Rippled should preserve that.  
If timing is vague, Rippled should preserve that.  
If a statement may or may not be a true commitment, Rippled should preserve that.

Examples:

- “We’ll send that tomorrow” should not resolve to a named owner unless supported.
- “Soon” should not become a precise due date.
- “We should probably do that” should not be treated like a committed deliverable without stronger evidence.

**Implication:** preserve evidence, candidate values, and ambiguity markers rather than forcing false resolution.

---

## 11. “We” is not a person

Collective language should not automatically resolve to an individual.

Statements like:

- “we’ll send it”
- “we need to follow up”
- “let’s update this”
- “someone should handle that”

may still matter a lot, but they are not the same as named ownership.

Rippled may suggest likely ownership when patterns are strong, but it should not silently convert group language into certainty.

**Implication:** likely owner suggestions may exist, but unresolved ownership should remain unresolved until supported.

---

## 12. Observe before interrupting

Rippled should prefer silent observation before requesting clarification or escalating a commitment more prominently.

Many ambiguities resolve naturally through subsequent work:

- someone claims ownership in Slack
- a date gets clarified by email
- an attachment is sent
- a follow-up thread makes the action explicit

This means the product should often wait briefly before acting, based on source and context.

Default principle:

- allow time for natural resolution
- interrupt only when the interruption is likely to help

**Implication:** silent observation windows should be source-aware, context-aware, and working-hours-aware.

---

## 13. Interruptions must earn their place

Every notification, prompt, clarification request, or surfaced suggestion competes with the user’s attention.

Rippled should not interrupt merely because it has detected something.  
It should interrupt when doing so is likely to reduce burden, prevent a miss, or create a meaningful “good catch.”

The product should bias toward:

- compact bundles
- low volume
- high usefulness
- timely nudges
- reviewable queues inside the product

It should avoid:

- long lists
- alert spam
- low-confidence prompts
- repeated nudging without added value

**Implication:** the internal system may know many things; the interruption layer must remain much stricter.

---

## 14. Suggestions should feel helpful, not accusatory

Rippled should support the user, not police them.

Its tone should feel like:

- an attentive assistant
- a careful second brain
- a “good catch” system

It should not feel like:

- surveillance
- nagging
- a scolding manager
- a brittle compliance engine

This is especially important when the system is uncertain or when the user is overloaded.

**Implication:** copy and UX should emphasize support, usefulness, and optionality.

---

## 15. Delivery and closure are not the same thing

A commitment being delivered is not always the same as it being closed.

Examples:

- proposal sent, awaiting feedback
- document delivered, pending approval
- intro email made, awaiting response
- revision sent, may come back with comments

Rippled should distinguish:

- **active** — work still in progress
- **delivered** — the user likely fulfilled the commitment
- **closed** — the loop is reasonably complete for now

These states may reopen.

**Implication:** lifecycle design should reflect real work loops, not simplistic one-way completion.

---

## 16. Later signals should update, not erase history

Commitments should become more accurate over time as more signals arrive:

- meetings may create them
- Slack may clarify ownership
- email may clarify due timing
- outbound messages may indicate delivery
- replies may signal closure or reopening

The commitment object should update as signals accumulate, but the evidence trail should remain visible and linked.

**Implication:** Rippled should maintain one evolving commitment record with linked signal history, not isolated per-channel items.

---

## 17. External commitments deserve stricter treatment

External or client-facing commitments generally carry more consequence and often more cognitive weight.

They should usually:

- surface faster
- be scored more strictly
- escalate sooner when still unresolved
- receive greater emphasis in the main view

Internal commitments still matter, especially for background cognitive load, but external obligations typically justify stronger handling.

**Implication:** internal and external commitments should not be treated identically by ranking, surfacing, or escalation logic.

---

## 18. Completion can be inferred from evidence, not just explicit confirmation

Many real commitments are not formally marked complete.  
Completion often appears through traces:

- outbound email with the promised file
- attachment sent to the expected recipient
- Slack message saying “done” or “sent”
- follow-up reply with the requested info
- linked artifact matching the deliverable

Rippled should use these as signals of likely delivery while preserving confidence and uncertainty appropriately.

**Implication:** the system should treat completion as an evidence-based inference problem, not only a declared status.

---

## 19. The system should age gracefully from uncertainty to usefulness

Rippled will not be perfect from day one.  
Its value should come from being useful early while becoming more precise over time through better linking, scoring, and user feedback.

This means the product should be designed so that:

- imperfect capture is acceptable internally
- uncertainty is preserved honestly
- user corrections improve behavior
- thresholds can tighten over time
- volume can remain controlled even as intelligence improves

**Implication:** the product should support learning and tuning without making early trust sacrifices.

---

## 20. The user should feel lighter, not more managed

This is the final test for every feature.

After using Rippled, the user should feel:

- more reassured
- less mentally overloaded
- less reliant on memory
- less likely to drop follow-through
- more supported in the background

If a feature increases checking, maintaining, triaging, or second-guessing, it is probably violating the product’s purpose.

**Implication:** the measure of success is not how much Rippled can detect. It is how much useful mental burden it removes.

---

## Product behavior rules derived from these principles

These rules should guide implementation and design decisions.

### Rippled should:

- observe work across meetings, Slack, and email
- capture more than it surfaces
- preserve evidence and ambiguity
- surface compact, useful suggestions
- distinguish big promises from small commitments
- separate confidence from priority
- use suggestion language instead of certainty language
- allow later signals to clarify or update commitments
- distinguish active, delivered, and closed
- use silent observation before clarification where possible
- favor trust over aggressive automation

### Rippled should not:

- become a general-purpose task manager
- force users to maintain another system
- treat every possible action as equally worth surfacing
- invent owners, due dates, or closure without support
- collapse uncertainty into fake precision
- spam users with prompts or notifications
- speak as if AI interpretations are ground truth
- lose history when later signals change the picture

---

## Decision filter

When evaluating a feature, behavior, or UX choice, ask:

1. Does this reduce cognitive load or increase it?
2. Does this help the user forget fewer things without creating more maintenance?
3. Are we capturing more than we show?
4. Are we preserving ambiguity honestly?
5. Are we being more assertive internally than externally?
6. Would this feel supportive, or intrusive?
7. Does this increase trust, or undermine it?
8. Does this surface only what is useful now?
9. Are we respecting the difference between priority and confidence?
10. Would the user feel lighter after this, or more managed?

If the answer trends in the wrong direction, the feature should be reworked.

---

## MVP implications

For MVP, these principles imply:

- meetings, Slack, and email should all be first-class sources
- the system should maintain unified commitments with linked evidence
- surfaced output should be separated into:
  - main commitments
  - shortlist
  - clarifications
- “we” should remain unresolved by default
- suggestions should be phrased carefully
- silent observation windows should exist before clarification
- external commitments should receive stricter handling
- commitment lifecycle should include active, delivered, and closed
- completion can be inferred from evidence with confidence
- the product should optimize for usefulness, not exhaustiveness

---

## Future extensions

These principles should remain stable even as the product expands into:

- calendar signals
- document analysis
- task system sync
- relationship heuristics
- configurable rules
- personalized thresholds
- richer completion evidence
- stronger feedback loops

The mechanics may evolve, but these principles should remain the anchor.

---

## Final statement

Rippled should capture more than it says, infer more than it asserts, and surface only what meaningfully reduces mental overhead.

Its value will not come from acting certain.  
Its value will come from being careful, useful, and trusted.

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 1. Product Vision]] | The vision these principles protect and operationalize |
| [[Rippled - 3. Commitment Domain Model Brief]] | Where principles like "preserve ambiguity" become field-level design |
| [[Rippled - 6. Surfacing & Prioritization Brief]] | Principles 2, 3, 8, 13 directly shape surfacing rules |
| [[Rippled - 7. MVP Scope Brief]] | MVP implications derived directly from these principles |
| [[Rippled - 9. Clarification Brief]] | Where principles 12 and 13 (observe before interrupting) take mechanical form |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |