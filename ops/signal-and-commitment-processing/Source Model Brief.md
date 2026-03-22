
### Purpose

Define the communication sources Rippled can ingest, what role each source plays in commitment intelligence, and how all sources map into one shared commitment engine.

### Why this matters

Rippled should not behave like a different product for each channel. The user experience should feel unified even when the evidence comes from email, Slack, or meetings. This brief creates that shared truth before channel-specific rules harden. That aligns with your view that the source model is a foundational doc and that not every downstream feature should be over-specified before the first real pipeline exists.  

### Locked decisions

* Rippled uses **one shared commitment engine** across sources.
* Sources do **not** create separate commitment object types.
* Each source contributes **signals**, not truth.
* Commitment objects are resolved from one or more signals.
* Sources may differ in:

  * how commitments originate
  * how ownership is inferred
  * how progress is expressed
  * how completion is evidenced
  * how ambiguity should be handled
* MVP source priority:

  1. Email
  2. Slack
  3. Meetings
  4. Calendar/task systems later
* Source-specific logic may shape extraction and confidence, but not lifecycle enums or final outcome types.
* Rippled should capture more than it surfaces and infer more than it asserts.  

### Default MVP rules

#### 1. Shared source contract

Every source adapter must output a normalized signal with the same minimum fields:

```text
NormalizedSignal
- signal_id
- source_type
- source_account_id
- source_thread_id            // nullable
- source_message_id           // nullable for non-message items
- occurred_at
- authored_at
- actor_participants[]
- addressed_participants[]
- visible_participants[]
- latest_authored_text
- prior_context_text          // bounded, nullable
- attachments[]
- links[]
- source_metadata{}
```

#### 2. Shared commitment engine stages

All signals flow through the same stages:

1. ingest
2. normalize
3. candidate extraction
4. speech-act classification
5. owner / deliverable / due resolution
6. lifecycle linking
7. confidence scoring
8. routing

#### 3. Shared outcome set

All sources must resolve to the same bounded outcomes:

* ignore / no commitment
* observe only
* create new commitment
* create multiple commitments
* update existing commitment
* reassign owner
* update due date / scope / conditions
* mark in progress
* mark delivered
* mark completed
* cancel / decline / not proceeding
* reopen
* needs clarification
* unresolved, do not surface

#### 4. Shared hard rules

* No source can create a lifecycle state outside the shared enum.
* Quoted / historical / contextual text may support interpretation, but should not automatically create a current commitment candidate.
* Confidence and priority stay separate.
* Unresolved is a valid outcome.
* Silence is better than false certainty.

---

### Source-by-source model

## A. Email

### Primary role

High-value source for external asks, explicit promises, confirmations, delivery evidence, due dates, and ownership handoffs.

### How commitments originate

* direct requests
* self-commitments
* acceptances / confirmations
* replies confirming prior asks
* deadline-setting messages
* multi-part emails with several asks/promises

### How clarification happens

Usually through reply context, named addressees, or recipient structure.

### How progress/completion is detected

* explicit status language
* outbound replies
* attachments / links
* “done / sent / attached / here it is” language
* recipient acknowledgement later

### Caveats

* quoted history can mislead
* multi-recipient ownership is often ambiguous
* polite language can look like commitment language
* one email often contains multiple candidate actions

## B. Slack

### Primary role

Fast-moving internal coordination source for lightweight asks, handoffs, clarifications, updates, and “soft commitments.”

### How commitments originate

* direct asks in channels or DMs
* thread replies
* lightweight commitments (“I’ll handle it”)
* follow-up nudges
* internal tasking language

### How clarification happens

Often immediately through back-and-forth in the same thread.

### How progress/completion is detected

* status replies
* emoji-supported acknowledgements later if useful
* “done / handled / pushed / shipped / sent”
* linked docs or screenshots

### Caveats

* casual language is much noisier
* multiple interleaved subtopics in one thread
* reactions are weak evidence
* thread context matters more than in email

## C. Meetings

### Primary role

High-volume source of implicit commitments, decisions, next steps, and ownership signals that are often not explicitly phrased as tasks.

### How commitments originate

* action items
* decisions with implied owners
* commitments spoken in discussion
* recap segments
* end-of-meeting “next step” statements

### How clarification happens

Often requires summary synthesis rather than direct explicit phrasing.

### How progress/completion is detected

Usually not in the meeting source itself; more often through later Slack/email evidence.

### Caveats

* speaker diarization quality matters
* ownership is often implied, not stated
* transcription noise can lower confidence
* completion detection usually requires cross-source linking

## D. Calendar / task systems later

### Primary role

Supporting evidence, timing context, and stronger completion scaffolding, not primary commitment creation in MVP.

### How commitments originate

* event commitments later, if product decides to support them
* existing task systems may reflect confirmed work rather than generate it

### Caveats

* risk of duplicating rather than discovering commitments
* not needed for initial truth layer

---

### Source interaction rules

* A commitment may be born in one source and completed in another.
* Cross-source deduplication is allowed only through explicit merge logic.
* Source trust varies by field:

  * Email is stronger for explicit ask/promise/delivery.
  * Slack is stronger for iterative clarification and in-progress status.
  * Meetings are stronger for implied commitments and decision context.
* Completion may require different evidence thresholds by source.

---

### Examples

#### Example 1

Meeting: “John will send the revised deck tomorrow.”
Later email: John sends attachment.
Result:

* meeting creates likely commitment candidate
* email confirms deliverable and marks delivered/completed

#### Example 2

Slack: “Can someone take this?”
No owner resolved.
Later thread reply: “I’ll do it.”
Result:

* first signal observed
* second signal creates / resolves owner

#### Example 3

Email: client asks for proposal by Friday.
Slack: teammate says “I’m on it.”
Result:

* email creates external commitment
* Slack may resolve internal owner or add evidence

---

### Open questions / future extension

* When should source-specific trust weights vary by user preference?
* Should meetings create lower default surfacing thresholds but higher clarification thresholds?
* When should reactions in Slack count as supporting evidence?
* How should calendar/task sources influence lifecycle without duplicating commitments?

### Implications for engineering / UX

* Engineering needs one canonical normalized signal contract and one shared outcome enum.
* UX should present unified commitments with source evidence, not separate channel views as separate truths.
* Cross-source evidence trails should be visible, but the primary surface should stay commitment-centric.

---

