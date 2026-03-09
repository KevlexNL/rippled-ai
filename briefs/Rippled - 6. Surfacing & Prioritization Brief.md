
---
tags: [rippled, surfacing, prioritization, ux, product]
brief: "06 — Surfacing & Prioritization"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Surfacing & Prioritization Brief

## Purpose

Define what Rippled should surface to the user, what it should keep internal, how surfaced items should be prioritized, and how to present commitments in a way that reduces cognitive load rather than increasing it.

This brief exists to ensure Rippled does not become a noisy feed of AI guesses. The system should capture broadly, interpret carefully, and surface selectively.

## Why this matters

Rippled’s value is not in detecting the maximum number of commitments. Its value is in helping the user feel like they forgot fewer things without needing to think too hard about what to track.

A system that captures many commitments but surfaces too much creates the same cognitive burden it is meant to remove. A system that surfaces too little fails to prevent forgotten commitments. Surfacing and prioritization are therefore central product behaviors, not just UI concerns.

## Core product rule

Rippled should surface the smallest useful set of commitment-related items that meaningfully reduces the user’s mental overhead.

This means:

- broad internal capture is acceptable
- broad user-facing surfacing is not
- suggestions should feel timely, lightweight, and valuable
- surfaced items should help the user remember, clarify, or close loops
- the user should rarely feel flooded, interrupted, or forced into admin work

## Non-negotiable principles

### 1. Capture more than you show

Rippled may internally retain more commitment signals than it actively surfaces.

Not every detected commitment candidate belongs in the user’s main view. Some items should remain quietly observed until they become more actionable, more certain, or more relevant.

### 2. Surface only when there is likely user value

Surfacing should happen when there is a plausible reduction in cognitive load, such as:

- reminding the user of a likely commitment they may forget
- clarifying an unclear owner or due date
- signaling likely delivery or completion
- highlighting an externally meaningful promise
- bringing attention to a small but cognitively costly loose end

### 3. Do not treat surfaced items as facts

Surfaced items must be presented as suggestions, interpretations, or likely commitments. Rippled should not present its outputs as hard truth.

### 4. Main surface should stay small

The main commitments surface should contain a deliberately constrained set of items. It should not become a long list of everything Rippled has detected.

### 5. Interruptions should be rarer than in-app visibility

Rippled may retain and show more items in-app than it actively pushes through notifications or messages. Push-like communication should be sparse and high-value.

### 6. Internal and external commitments should not be treated equally

External commitments generally deserve faster surfacing, stricter tracking, and higher urgency than internal ones, because their consequences and cognitive weight are usually higher.

---

# Surface model

Rippled should use three primary surfaced views.

## 1. Main tab

This is the user’s primary commitment view.

It should contain:

- bigger promises
- more consequential commitments
- externally meaningful commitments
- items with stronger evidence of ownership and deliverable
- items where missing or delayed follow-through is likely to matter

The main tab is not a full backlog. It is a focused working set.

## 2. Shortlist tab

This is the lighter-weight queue for small commitments.

It should contain:

- smaller internal commitments
- promises that are easy to forget
- low-friction follow-ups
- “I’ll send that,” “I’ll look into it,” “I’ll reply,” “I’ll handle it” type commitments
- items that may be low in business consequence but high in cognitive burden if forgotten

The shortlist exists because many small promises materially contribute to mental load even if they do not belong in the main commitment set.

## 3. Clarifications view

This is a separate review surface for items that likely matter but still require clarification.

It should contain items where Rippled believes there is meaningful value in resolving ambiguity, such as:

- missing owner
- vague owner
- missing due date where timing likely matters
- conflicting later signals
- unclear deliverable
- uncertain whether a statement is truly a commitment

This view should be separate from the main commitment surfaces so ambiguity does not clutter the user’s primary working view.

---

# Surfacing layers

Rippled should distinguish between internal system states and surfaced user states.

## Internal capture layer

This layer may contain:

- weak signals
- early commitment candidates
- observed but unsurfaced items
- low-confidence interpretations
- possible completion signals
- possible clarification opportunities

These items should remain available for reasoning and linking, but many should not yet be shown.

## Surfaced layer

This layer contains only items that meet the threshold for meaningful user value.

An item should be surfaced only when Rippled believes one of the following is true:

- the user is likely to benefit from remembering it now
- the item has become more concrete or actionable
- the item appears externally important
- the item risks being forgotten
- the item needs clarification and that clarification is worth asking for
- there is likely delivery/completion worth reflecting back

---

# Commitment classes for surfacing

For MVP, Rippled should classify surfaced items into two priority classes.

## Big promises

These belong primarily in the Main tab.

Priority criteria, in order:

1. external vs internal  
2. explicit due date  
3. business consequence  

Typical characteristics:

- client-facing or externally visible
- explicit promise or delivery expectation
- concrete deliverable
- explicit timing
- higher consequence if missed
- stronger expectation on the part of another person

Examples:

- “I’ll send the proposal by Friday”
- “We’ll get the revised contract over by Monday”
- “I’ll follow up with the client tomorrow”
- “I’ll send updated pricing this afternoon”

## Small commitments

These belong primarily in the Shortlist tab.

Typical characteristics:

- internal
- lower business consequence
- lighter-weight follow-up
- often easy to forget
- often more conversational
- may lack exact due date but still create real expectation

Examples:

- “Let me look into that”
- “I’ll send you that doc”
- “I’ll reply after lunch”
- “I’ll handle that”
- “I’ll check with ops”

Important: small does not mean unimportant. It means lighter-weight, lower-consequence, or less formal than a big promise.

---

# Priority dimensions

Surfacing priority should not rely on a single score. Rippled should prioritize items based on several dimensions.

## 1. Externality

External commitments should usually surface faster and more prominently than internal ones.

Externality includes:

- client-facing email commitments
- promises made to external stakeholders
- external meeting follow-ups
- deliverables owed outside the organization

## 2. Timing strength

Items with explicit due dates or strong time expectations should surface more readily than timeless or vague commitments.

Examples of stronger timing:

- “by Friday”
- “tomorrow”
- “this afternoon”
- “before the call”

Examples of weaker timing:

- “soon”
- “later”
- “at some point”

## 3. Business consequence

Higher-consequence commitments should surface more prominently, especially if delay or failure would meaningfully affect revenue, trust, client outcomes, or reputation.

## 4. Cognitive burden

Some items are not strategically large but are mentally costly to keep track of. Rippled should give weight to commitments likely to generate “don’t forget this” burden.

This is especially important for:

- multiple small promises across channels
- founder/executive overload
- service-delivery follow-ups
- handoffs between contractor, assistant, account rep, or founder

## 5. Confidence

Surfacing should be influenced by confidence, but confidence should not fully determine surfacing. A real explicit commitment with moderate confidence may still be worth surfacing, especially if external.

## 6. Actionability

Items with clear owner and next step should surface more readily than vague conversational fragments.

## 7. Staleness or unresolved duration

A likely commitment that has remained unresolved past its expected observation window may deserve increased surfacing priority.

---

# Priority rules for MVP

Default prioritization should follow this rough logic.

## Highest priority

- external big promises
- explicit promises with due dates
- high-consequence commitments
- externally visible delivery obligations
- items likely delivered but not yet reflected cleanly
- items likely forgotten and now time-sensitive

## Medium priority

- internal commitments with explicit ownership
- small commitments that appear easy to forget
- likely commitments that have persisted without resolution
- important items needing clarification

## Lower surfaced priority

- weak implicit signals
- low-confidence candidate commitments
- vague internal conversational next steps
- items likely to self-resolve within observation window
- commitments with little evidence of expectation or consequence

Lower-priority items may still be retained internally.

---

# Observation before surfacing

Rippled should not immediately surface every detected commitment. It should often allow a silent observation window for later signals to clarify ownership, timing, or completion.

## Default observation windows

These should be based on working hours and later made configurable.

For MVP:

- Slack internal: up to 2 working hours
- Email internal: 1 working day
- Email external: 2 to 3 working days
- Meetings internal: 1 to 2 working days
- Meetings external: 2 to 3 working days, provisional default

During the observation window, Rippled may:

- watch for clearer owner assignment
- watch for a deadline clarification
- watch for delivery/completion evidence
- merge later signals into the same commitment
- suppress premature clarification prompts

Exception: highly consequential external promises may surface earlier even before the observation window completes.

---

# Clarification surfacing rules

Not every ambiguity should become a surfaced clarification.

A clarification should be surfaced only if:

- the commitment likely matters
- waiting longer is unlikely to resolve it
- the missing field materially affects usefulness
- asking is likely to help more than it interrupts

Clarifications should be deprioritized when:

- later signals are likely to resolve them naturally
- the commitment itself is weak or low-confidence
- the ambiguity is non-critical
- the user would experience the request as unnecessary admin

## Critical clarification cases

More likely to surface:

- unclear owner on important commitment
- conflicting dates for external promise
- likely real commitment with no clear deliverable
- unresolved external follow-up with expectation attached

## Non-critical clarification cases

More likely to remain unsurfaced for now:

- weak internal timing ambiguity
- minor target ambiguity
- low-confidence implicit ownership guess
- small internal commitment likely to self-resolve

---

# External vs internal surfacing behavior

External/client-facing commitments should:

- surface faster
- be scored more strictly
- be escalated sooner if unresolved
- remain more visible for longer
- be more likely to appear in the Main tab

Internal commitments should:

- tolerate more ambiguity
- rely more on silent observation first
- more often appear in the Shortlist tab
- be less likely to trigger interruption unless useful

---

# Confidence vs priority

Confidence and priority must remain separate.

A big promise may be high priority but still low confidence, in which case it may go to Clarifications rather than Main.

A small commitment may be lower business priority but high cognitive relevance and high confidence, in which case it may be appropriate for the Shortlist.

Rippled should avoid hiding high-value items solely because certainty is imperfect. It should also avoid surfacing low-value items merely because certainty is high.

---

# Surfacing thresholds

For MVP, Rippled should use three user-facing surfacing thresholds.

## 1. Main threshold

An item belongs in Main when it is likely a big promise and likely useful to keep visible now.

Typical conditions:

- external or otherwise high consequence
- meaningful commitment confidence
- enough evidence to be actionable
- not blocked mainly by major ambiguity unless the ambiguity itself is central

## 2. Shortlist threshold

An item belongs in Shortlist when it is likely real, likely easy to forget, and likely useful to keep lightly visible without crowding Main.

Typical conditions:

- smaller internal commitment
- moderate to high commitment confidence
- some evidence of ownership or implied responsibility
- meaningful cognitive burden if forgotten
- not important enough for Main

## 3. Clarification threshold

An item belongs in Clarifications when it likely matters but is not yet clean enough to track confidently without user input or more evidence.

Typical conditions:

- likely real commitment
- important ambiguity persists
- waiting longer is unlikely to help
- clarification would materially improve usefulness

---

# Interruptions and bundles

Push-like surfacing should be stricter than in-app surfacing.

Rippled should prefer:

- compact bundles
- short lists
- a sense of “good catch”
- low frequency
- high usefulness density

It should avoid:

- large batches
- frequent pings
- exhaustive review prompts
- pushing weak signals

## Bundling principles

When communicating outside the main app view:

- group related items
- keep bundles short
- favor highest-value items first
- separate reminders from clarifications when possible
- do not turn the product into a stream of chores

The intended feel is a quick, manageable cleanup moment, not a new inbox.

---

# User-visible framing

Surface language should always reflect uncertainty appropriately.

Examples:

- “Likely commitment”
- “Looks like you said you’d send pricing”
- “Might need clarification on owner”
- “This seems likely delivered”
- “You may want to keep an eye on this”

Avoid:

- “You committed to...”
- “This is due...”
- “Owner is...” when certainty is not high enough

---

# What should never happen

Rippled should not:

- surface everything it detects
- mix clarifications into the main list so heavily that the main list becomes messy
- flood the user with minor items
- hide all small commitments just because they seem individually unimportant
- treat high-confidence low-value items as more important than lower-confidence high-value external promises
- turn its internal candidate list into a user-facing backlog
- use absolute language for ambiguous items

---

# MVP defaults

For MVP, default behavior should be:

- maintain a broader internal capture set than surfaced set
- use Main, Shortlist, and Clarifications as separate surfaced destinations
- classify big vs small primarily by externality, explicit due date, and business consequence
- prefer silent observation before surfacing, especially for internal items
- surface external/client-facing items faster
- keep push-like communication stricter than in-app visibility
- use suggestion language throughout
- preserve unresolved ownership where ownership is collective or vague
- allow later signals to update surfaced status while preserving signal history

---

# Open questions / future extension

These do not need to be locked for MVP but should be designed for future flexibility:

- user-configurable surfacing sensitivity
- user-specific definitions of big vs small
- role-aware prioritization rules
- relationship-aware likely owner suggestions
- adaptive bundle sizing based on user behavior
- learning from approvals, dismissals, and corrections
- different surfacing behavior by time of day, work mode, or current load
- calendar-aware prioritization

---

# Implications for engineering

The system should support:

- internal retention of unsurfaced candidates
- separate surfaced-state assignment from raw detection
- configurable observation windows
- unified commitment objects with linked multi-source evidence
- separate priority class and confidence dimensions
- separate in-app vs push surfacing thresholds
- auditable reasons for why an item was surfaced, held back, moved between tabs, or escalated for clarification

---

# Success criteria

This brief is successful if Rippled behaves such that:

- the user sees fewer, more useful surfaced items
- forgotten small promises are more often caught
- important external commitments are visible early
- clarification requests are infrequent but valuable
- the product feels assistive rather than burdensome
- the user increasingly trusts that Rippled will surface the right things without making them manage everything

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 2. Product Principles Brief]] | Principles 2, 8, 13, 17 directly govern surfacing behavior |
| [[Rippled - 3. Commitment Domain Model Brief]] | Big promise vs small commitment classification defined here |
| [[Rippled - 5. Commitment Lifecycle Brief]] | Active/delivered/closed states determine what belongs in which surface |
| [[Rippled - 7. MVP Scope Brief]] | MVP surface model (Main / Shortlist / Clarifications) |
| [[Rippled - 9. Clarification Brief]] | What gets routed to the Clarifications surface and when |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |