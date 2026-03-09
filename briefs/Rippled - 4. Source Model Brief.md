---
tags: [rippled, sources, meetings, slack, email, domain-model]
brief: "04 - Source Model"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Source Model Brief

## Purpose

Define the communication sources Rippled ingests, the role each source plays in commitment intelligence, and the rules for turning raw source activity into usable commitment signals.

This brief exists to ensure the product and engineering teams treat meetings, Slack, and email as parts of one unified system rather than separate feature tracks.

The goal is not to mirror each source exactly as-is. The goal is to normalize them into a shared model that helps Rippled answer:

- What commitments were made?
- Who appears responsible?
- When does it seem due?
- What later signals clarify, progress, deliver, or close that commitment?

---

## Why this matters

Rippled is not a meeting notes product, a Slack assistant, or an email copilot in isolation.

It is a communication-based commitment intelligence layer.

That means the source model must support three truths:

1. **Commitments happen across channels**
   A commitment may originate in a meeting, get clarified in Slack, and get delivered by email.

2. **Different channels have different signal quality**
   Email is often more explicit and formal. Slack is often faster, more implicit, and more conversational. Meetings often contain the earliest or broadest form of a commitment.

3. **The system must unify, not fragment**
   Rippled should maintain one commitment record linked to multiple supporting signals, not separate commitment universes per source.

---

## Core principle

Every source should be modeled in terms of what role it can play in the lifecycle of a commitment, not just what data it provides.

Each source can contribute to one or more of these roles:

- **origin** - where a commitment first appears
- **clarification** - where owner, deadline, or deliverable becomes clearer
- **progress** - where work appears to be underway
- **delivery** - where the promised output appears to have been sent or completed
- **closure** - where the commitment appears finished, accepted, or aged out
- **reopening** - where the commitment becomes active again due to revision, follow-up, or rejection

---

## In-scope sources for MVP

### 1. Meetings
Includes meeting transcripts and related metadata from meeting/transcription providers.

### 2. Slack
Includes channels, private channels, group conversations, direct messages, and threads.

### 3. Email
Includes inbound and outbound email threads, message direction, recipients, and attachment metadata.

---

## Out of scope for this brief

This brief does not yet define:

- calendar logic in detail
- task management system syncing
- CRM as a primary commitment source
- file storage systems as primary sources
- browser activity or documents as primary activity streams

Those may later become supporting evidence sources, but are not first-class communication sources in the MVP source model.

---

# Source roles by channel

## Meetings

### What meetings are good at

Meetings are especially valuable for:

- early identification of commitments
- capturing verbal promises before they are written elsewhere
- identifying unresolved next steps
- detecting vague ownership or vague deadlines
- surfacing group assumptions that may later need clarification

### Common meeting-originated commitment patterns

Examples:

- "I'll send that tomorrow."
- "We'll follow up with pricing."
- "Can someone take that?"
- "Next step is to update the proposal."
- "Let's make sure the client gets this by Friday."

### Typical meeting weaknesses

Meetings often contain:

- vague ownership ("we", "someone", "the team")
- vague timing ("soon", "next week", "after this")
- overlapping speakers
- misheard transcript segments
- discussion that sounds action-oriented but is not actually a commitment

### Meeting role in Rippled

Meetings should be treated as:

- a major **origin source**
- a strong **clarification-needed source**
- a moderate **progress source**
- a weaker **delivery/closure source** unless later confirmed elsewhere

### Default interpretation stance

Meeting-derived candidates should often be captured early, but not over-promoted without later support when ownership, deadline, or deliverable remains vague.

---

## Slack

## What Slack is good at

Slack is a first-class source because much day-to-day work happens there.

Slack is especially valuable for:

- small commitments
- accepted requests
- delegated follow-ups
- fast clarifications
- progress updates
- informal completion signals

### Common Slack-originated commitment patterns

Examples:

- "I'll look into that."
- "Let me handle it."
- "I'll send it over."
- "I'll reply to them."
- "I'll push the update today."
- "Done."
- "Just sent it."
- "Handled."
- "Can you take this?" / "Yep."

### Typical Slack strengths

Slack often provides:

- clearer ownership than meetings
- strong thread context
- later clarifications to earlier meeting commitments
- fast status signals
- lightweight evidence of completion

### Typical Slack weaknesses

Slack also contains high noise because it includes:

- brainstorming
- passing thoughts
- social chatter
- half-formed ideas
- weak promises with low consequence
- context that is highly dependent on thread history

### Slack role in Rippled

Slack should be treated as:

- a major **origin source**
- a major **clarification source**
- a major **progress source**
- a meaningful **delivery/completion source**
- a meaningful **reopening source**

### Slack-specific MVP scope

Slack source coverage should include:

- public channels
- private channels
- direct messages
- group messages
- thread replies
- message edits
- mentions
- file/link metadata
- timestamps
- sender identity
- message permalinks or source references

### Slack-specific product rules

- Thread replies are first-class context.
- DMs are in scope.
- Private channels are in scope if permissions allow.
- Message edits may change interpretation and should be reflected in source processing.
- Reactions are not primary commitment signals in MVP, but may later become supporting indicators.
- Slack signals are especially important for small commitments and informal progress/completion.

---

## Email

## What email is good at

Email is often the most formal communication source and should be treated accordingly.

It is especially valuable for:

- client-facing commitments
- explicit delivery promises
- timeline commitments
- follow-up obligations
- evidence of actual sending/delivery
- formal replies that clarify or revise prior commitments

### Common email-originated commitment patterns

Examples:

- "I'll send the proposal by Friday."
- "We'll follow up next week."
- "I'll revise this and get it back to you."
- "I'll introduce you both."
- "We'll send pricing Monday."
- "Attached is the deck we discussed."

### Typical email strengths

Email often provides:

- higher explicitness
- higher business consequence
- stronger deadline cues
- clearer external expectations
- better delivery evidence, especially for send-type commitments

### Typical email weaknesses

Email may still contain:

- quoted prior text that can create duplicates
- formal but non-committal language
- forwarded or copied context that does not imply ownership
- thread complexity around internal handoff vs external delivery

### Email role in Rippled

Email should be treated as:

- a major **origin source**
- a major **clarification source**
- a strong **delivery/completion source**
- a strong **reopening source**
- a moderate **progress source**

### Email-specific MVP scope

Email source coverage should include:

- full thread structure
- inbound vs outbound direction
- sender and recipients
- internal vs external participant classification
- subject
- body
- timestamps
- attachment metadata
- thread/message identifiers

### Email-specific product rules

- Outbound email is strong completion evidence for send-type commitments.
- External/client-facing email commitments should be treated more strictly than internal commitments.
- Quoted prior email text should be excluded from fresh extraction to avoid duplication.
- Reply chains should be preserved for context and clarification.
- Internal email is in scope, not only external email.
- The model should support cases where internal delivery happens first, but client delivery remains the likely next commitment.

---

# Shared source concepts

## Source item

A source item is the smallest directly ingested communication unit.

Examples:

- one meeting transcript segment
- one Slack message
- one email message

A source item is not yet a commitment.

It is raw or normalized evidence that may contribute to commitment intelligence.

## Source thread or context unit

A source thread is the higher-level context grouping used to interpret a source item.

Examples:

- a meeting
- a Slack thread or channel conversation window
- an email thread

The source thread helps determine:

- what the commitment is about
- whether ownership is already implied or later clarified
- whether a later message resolves an earlier vague statement
- whether completion evidence relates to the same commitment

## Commitment signal

A commitment signal is a source-derived interpretation that suggests one or more of:

- a new commitment may exist
- an existing commitment became clearer
- an existing commitment appears in progress
- an existing commitment appears delivered
- an existing commitment appears closed
- an existing commitment appears reopened

Signals may come from any source and should be linkable to one unified commitment object.

---

# Cross-source model

## One unified commitment object

Rippled should maintain one unified commitment object that can accumulate evidence from multiple sources.

Example:

- Meeting: "We'll send pricing tomorrow."
- Slack later: "John, can you send that pricing doc?"
- Slack reply: "Yep, I'll handle it."
- Email later: "Attached is the pricing overview."

This should not create four separate commitments.

It should create or maintain one commitment with linked signals that progressively improve understanding of:

- action
- owner
- timing
- progress
- delivery
- closure

## Signal linkage rules

Signals from different sources may do one of several things:

- create a new commitment candidate
- strengthen an existing commitment
- clarify an existing commitment
- mark likely progress
- mark likely delivery
- reopen a previously delivered or closed commitment
- create ambiguity or conflict requiring clarification

## Cross-source priority principle

The source model should not encode a rigid truth hierarchy such as "email always wins" or "latest always wins."

Instead:

- later signals should usually update the current understanding
- more explicit signals should usually be weighted more heavily
- vague later signals should not overwrite clearer earlier evidence cleanly
- conflicting signals should lower certainty and may trigger clarification rather than replacement

---

# Internal vs external context

This distinction is central to source modeling.

## Internal context

Internal context generally means communication among teammates, contractors, assistants, or collaborators inside the user's operating environment.

Internal commitments are more likely to be:

- implicit
- conversational
- rapidly changing
- loosely timed
- clarified through Slack
- operationally lightweight but cognitively costly when forgotten

## External context

External context generally means communication involving clients, prospects, partners, vendors, or other outside parties.

External commitments are more likely to be:

- explicit
- formal
- consequence-heavy
- deadline-bound
- emotionally heavier for the user
- better candidates for main commitment surfacing

## Product implications

External commitments should generally:

- surface faster
- be scored more strictly
- escalate sooner when unresolved
- weigh more heavily in big vs small classification

Internal commitments should generally:

- tolerate more ambiguity initially
- benefit more from silent observation
- produce more shortlist-type items
- rely more on conversational clarification

---

# Big promises vs small commitments

This classification is not source-exclusive, but the source model must support it.

## Big promises

More likely when:

- external/client-facing
- explicit due date present
- higher business consequence
- explicit deliverable or obligation
- formal expectation created

Common examples:

- "I'll send the proposal by Friday."
- "We'll get the pricing to the client tomorrow."
- "I'll introduce you by email this afternoon."

## Small commitments

More likely when:

- internal
- operational
- lighter scope
- weakly formalized
- small but cognitively burdensome if forgotten

Common examples:

- "I'll look into that."
- "I'll reply in a bit."
- "Let me handle that."
- "I'll send it over."

## Priority order for classification

For MVP, big vs small should be determined in this order:

1. external vs internal
2. explicit due date
3. business consequence

This classification affects surfacing, not truth.

A small commitment can still be high-confidence and worth surfacing in the shortlist.

---

# Silent observation windows by source

The source model must support the idea that Rippled should sometimes wait before surfacing or asking for clarification.

The system should prefer to observe first when future signals are likely to resolve ambiguity naturally.

## Default working-hours-based observation windows for MVP

### Slack
- up to 2 working hours

Use because Slack often resolves quickly through thread replies or follow-up messages.

### Internal email
- 1 working day

Use because internal email usually moves slower than Slack but faster than client-facing email.

### External email
- 2 to 3 working days

Use because client communication and formal follow-ups often take longer.

### Internal meetings
- 1 to 2 working days

Use because post-meeting Slack/email often clarifies ownership and next steps.

### External meetings
- 2 to 3 working days, provisional default

Use because follow-up email may formalize commitments after the meeting.

These defaults should be configurable later.

---

# Suggested values by source

When the system cannot resolve a field with confidence, it may generate suggested values.

For MVP, the safest order of suggested-value generation is:

1. likely next step
2. likely owner
3. likely due date
4. likely completion

## Why this ordering

- Next step is often the safest useful inference.
- Owner can sometimes be reasonably inferred from context, but should remain separate from resolved ownership.
- Due date is more risky and should be suggested carefully.
- Completion inference can be strong in some source types but should remain evidence-based.

## Source implications

- Meetings are often good for suggesting next step.
- Slack is often good for suggesting likely owner.
- Email is often good for suggesting due date or confirming delivery.
- None of these suggestions should be presented as hard truth without supporting evidence.

---

# Source-specific evidence patterns

## Meetings - evidence patterns

Strong for:

- verbal promise
- stated next step
- group assumption
- initial due language

Weak for:

- confirmed delivery
- confirmed closure

## Slack - evidence patterns

Strong for:

- accepted ownership
- operational follow-up
- progress updates
- informal done/handled/sent language

Moderate for:

- actual delivery evidence unless artifact or external send is linked

## Email - evidence patterns

Strong for:

- formal promise
- timeline commitment
- actual sending
- recipient-visible delivery
- attachment-backed completion

Weakness to watch:

- quoted historical text
- CCs implying presence, not ownership

---

# Edge-case rules

## Internal handoff vs external delivery

The source model must support commitments that move through internal and external stages.

Example:

- Internal email: "I finished the proposal draft."
- That does not necessarily close "send proposal to client."
- It may instead complete one internal step and strengthen the next likely commitment.

This is important because bottlenecks often happen between internal completion and external delivery.

## Reopening

Later source activity may reopen a commitment.

Examples:

- "Can you revise this?"
- "This still needs to go out."
- "Client had feedback."
- "We need another version."

The source model must support reopening from later linked signals.

## Ambiguity persistence

If the source model sees:

- vague ownership
- vague timing
- conflicting dates
- unclear deliverable

it should preserve ambiguity rather than collapsing too early into false precision.

---

# Locked MVP decisions

These decisions should be treated as fixed for the current phase:

- Meetings, Slack, and email are first-class sources.
- Each source can act as origin, clarification, progress, and completion evidence.
- Slack DMs and private channels are in scope.
- Email includes both internal and external threads.
- Outbound email is strong completion evidence for send-type commitments.
- Quoted email text should be excluded from fresh extraction.
- One unified commitment object should link signals across sources.
- External/client-facing commitments should be treated more strictly.
- Silent observation should exist by default.
- "We" should remain unresolved by default, even if a likely owner can be suggested.

---

# Open questions for later phases

These should not block MVP but are natural future extensions:

- calendar as a source of due/progress/completion evidence
- document/file content analysis for stronger delivery detection
- reaction-based Slack inference
- source weighting personalization by user/team
- richer organizational relationship heuristics
- channel-specific trust tuning based on user feedback
- attachment semantic classification

---

# Implications for engineering

The source model implies the system should support:

- provider-specific ingestion with source-native metadata
- a normalized communication schema
- cross-source identity linking where possible
- thread/context preservation
- signal-to-commitment linking
- non-destructive updates when later source signals appear
- source references/permalinks for evidence trails
- handling of edits, quoted text, and message direction
- observation windows that vary by source and internal/external status

---

# Implications for product and UX

The source model implies:

- the user should not have to think in channels
- commitment detail should show linked evidence across sources
- Slack/email/meeting origin should be visible when useful
- main surfacing should prioritize clarity and consequence, not raw source volume
- clarifications should often be delayed until natural follow-up windows pass
- the system should speak in suggestions and evidence-backed interpretations, not absolute claims

---

## Summary

Rippled should treat meetings, Slack, and email as one connected communication fabric.

The source model exists to ensure the system can:

- capture commitments wherever they happen
- link clarifying and completion signals across channels
- preserve ambiguity when needed
- distinguish internal vs external expectations
- support big promises and small commitments differently
- reduce cognitive load without forcing the user to maintain another task system

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 3. Commitment Domain Model Brief]] | The domain model that source signals feed into |
| [[Rippled - 5. Commitment Lifecycle Brief]] | How cross-source signals drive lifecycle transitions |
| [[Rippled - 8. Commitment Detection Brief]] | Source-specific detection rules in the pipeline layer |
| [[Rippled - 9. Clarification Brief]] | Source-aware observation windows before clarification triggers |
| [[Rippled - 10. Completion Detection Brief]] | Source-specific completion evidence rules |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |