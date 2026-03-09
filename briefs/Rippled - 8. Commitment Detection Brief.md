---
tags: [rippled, detection, engineering, pipeline]
brief: "08 — Commitment Detection"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Commitment Detection Brief

## Purpose

Define how Rippled should detect likely commitments from meetings, Slack, and email before those signals move into extraction, scoring, clarification, and surfacing.

This brief is about the **detection layer**, not final commitment truth. Its job is to cast a broad but disciplined net over communication and identify moments that are likely to contain a commitment, follow-up obligation, delegated action, or unresolved next step.

The goal is to avoid missing meaningful commitments while still preventing the system from turning every conversational action phrase into noise.

---

## Why this matters

If detection is too narrow, Rippled misses the exact small promises and practical follow-ups that create cognitive load when forgotten.

If detection is too broad, Rippled fills the pipeline with conversational debris, weak suggestions, and non-actionable chatter that increase noise downstream.

Detection therefore needs to optimize for:

- **high recall on real commitments**
- **controlled noise**
- **preserved ambiguity**
- **strong context capture**
- **channel-aware interpretation**

Detection is not where Rippled should try to be perfectly right. Detection is where Rippled should be good at saying:

> “This may matter. Keep it, contextualize it, and let later stages determine how real and usable it is.”

---

## Core principle

The detection layer should capture more than Rippled ultimately surfaces.

Detection should be:

- broader than final output
- more cautious than a task extractor
- structured enough for downstream scoring
- conservative about certainty
- generous about keeping evidence

---

## Scope

This brief covers:

- what should count as a detectable commitment signal
- what should not count
- explicit vs implicit detection
- source-specific rules for meetings, Slack, and email
- candidate span creation
- context window capture
- trigger classes
- priority hints at detection time
- when to mark a signal for re-analysis or observation

This brief does **not** define:

- final commitment object structure
- final confidence thresholds
- final clarification workflows
- final user-facing surfacing behavior
- completion detection
- merge/dedup logic across signals

---

## Detection objective

The detection layer should identify communication moments that plausibly imply one or more of the following:

- someone committed to do something
- someone accepted responsibility for a follow-up
- someone implied that work would happen
- someone delegated work to a person or group
- someone created an expectation that something would be delivered
- someone identified a next step that still requires ownership or timing
- someone changed, delayed, or reframed an existing commitment
- someone made a promise whose absence of follow-through would likely matter

---

## Detection outputs

Detection should not produce final commitments yet.

It should produce **candidate commitment signals** containing:

- source type
- source message/segment identifiers
- transcript/message/thread window
- trigger class
- trigger reason
- quoted trigger text or span
- surrounding context
- whether the signal appears explicit or implicit
- whether the signal appears new, clarifying, delaying, or status-related
- whether observation is recommended before clarification
- whether re-analysis is recommended
- initial priority hint
- initial confidence hint
- linked entities already detectable from source context

These are candidates for later stages, not asserted truths.

---

## What Rippled should detect

## 1. Explicit commitments

These are the clearest and highest-value cases.

Definition:

A statement where a person clearly indicates that they will perform an action, deliver something, follow up, respond, review, send, decide, or otherwise take responsibility for future work.

Examples:

- “I’ll send the revised deck tomorrow.”
- “John will follow up with procurement.”
- “I can get that proposal over by Monday.”
- “Let me review this and reply this afternoon.”
- “I’ll handle it.”
- “We’ll send pricing by end of day.”  
  Detect as explicit commitment signal, but ownership unresolved.

Detection rule:

- strong future-action language
- explicit ownership or collective ownership reference
- clear action implication
- not purely hypothetical or historical

---

## 2. Explicit delegated commitments

Definition:

A statement where work is assigned, requested, or accepted by another person in a way that creates a plausible obligation.

Examples:

- “Sarah, can you send that over today?”
- “Mark will update the proposal.”
- “Can you take this?”
- “Yes, I’ll do it.”
- “Let’s have Jake follow up.”

Detection rule:

- assignment language, request language, or acceptance language
- person or group referenced as actor or target
- future work implied
- capture both the request and the acceptance when available

Important:  
A request alone may be a detectable signal even before acceptance, but should be marked differently from an accepted commitment.

---

## 3. Implicit commitments

Definition:

A statement that does not cleanly say “I will,” but strongly implies that work is expected to happen.

Examples:

- “Next step is pricing from us.”
- “We still need to update the proposal.”
- “Someone needs to send the intro.”
- “The follow-up will come from our side.”
- “We should get that over to them.”
- “That still has to go out today.”

Detection rule:

- future action is implied
- expectation exists
- ownership and/or timing may be unclear
- not yet strong enough to be treated as final without downstream review

Implicit commitments matter because many cognitively costly obligations are expressed this way rather than as crisp task statements.

---

## 4. Small practical commitments

Definition:

Low-ceremony commitments that are easy to forget but create real expectation and cognitive load.

Examples:

- “I’ll look into that.”
- “I’ll check.”
- “Let me confirm.”
- “I’ll send that later.”
- “I’ll get back to you.”
- “I’ll ask them.”
- “I’ll take a look.”

Detection rule:

- modest action language still counts
- do not exclude because the commitment is small
- mark with lower priority hint unless context elevates it
- preserve because these are often central to Rippled’s value proposition

---

## 5. Client-facing promises

Definition:

Any commitment expressed in a client/external context that creates expectation toward an outside party.

Examples:

- “We’ll send the proposal tomorrow.”
- “I’ll follow up with the numbers.”
- “We’ll have this to you Monday.”
- “I’ll revise and resend.”
- “Let me get that over to you.”

Detection rule:

- external context should raise priority hint
- explicit due date should further raise priority hint
- collective ownership still remains unresolved, but the signal is important

---

## 6. Clarifying or modifying signals

Definition:

A later signal that appears to clarify, reschedule, narrow, broaden, or otherwise update a previously implied or detected commitment.

Examples:

- “Actually, I’ll handle that.”
- “Let’s move that to next week.”
- “I already sent it.”
- “That follow-up will come from Jess.”
- “We need to push the deadline to end of month.”

Detection rule:

- create a new candidate signal
- classify it as modifying/clarifying rather than purely new
- preserve linkage opportunity for downstream merge/update logic

---

## 7. Status-bearing signals relevant to a commitment

Definition:

A signal that suggests a commitment is in progress, delivered, blocked, delayed, or reopened.

Examples:

- “Sent.”
- “Just emailed it.”
- “Done.”
- “Still waiting on legal.”
- “I haven’t had time to do this yet.”
- “Client asked for revisions.”
- “I sent the proposal but haven’t heard back.”

Detection rule:

- detect these signals even if they are not new commitments
- mark them as status-related candidates
- preserve because they may update existing commitment state downstream

---

## What Rippled should not detect as commitments

Detection should avoid creating candidate signals for the following unless surrounding context clearly changes the meaning.

## 1. Pure hypotheticals

Examples:

- “We could do that.”
- “Maybe we should send something.”
- “It might make sense to revise pricing.”
- “We may want to follow up at some point.”

These may indicate ideas, not obligations.

Rule:

- detect only if surrounding context converts suggestion into implied expectation
- otherwise suppress or score extremely low at detection

---

## 2. Historical statements

Examples:

- “I sent that yesterday.”
- “We already reviewed the proposal.”
- “Last week we followed up.”
- “We handled that already.”

These are not new commitments, though they may matter later for completion logic.

Rule:

- do not treat as new commitment candidates
- may still be captured as status/context if linked to an existing commitment later

---

## 3. Pure discussion of work without obligation

Examples:

- “The proposal needs changes.”
- “Pricing is still off.”
- “That document has issues.”
- “We talked about following up.”

Rule:

- no candidate unless an action expectation is implied

---

## 4. Generic brainstorming

Examples:

- “What if we did X?”
- “One option is to send a follow-up.”
- “We might try another version.”
- “Should we maybe explore that?”

Rule:

- suppress unless the conversation clearly shifts into ownership or expectation

---

## 5. Courtesy / conversational fillers

Examples:

- “Let me know.”
- “Sounds good.”
- “Okay.”
- “Will do” without clear preceding context stored nearby may still need contextual interpretation

Rule:

- these are not standalone commitments unless surrounding context clearly supports it

---

## Detection categories

Every candidate signal should be tagged with one primary detection category.

Suggested categories:

- `explicit_self_commitment`
- `explicit_assigned_commitment`
- `explicit_collective_commitment`
- `request_for_action`
- `accepted_request`
- `implicit_next_step`
- `implicit_unresolved_obligation`
- `small_practical_commitment`
- `deadline_change`
- `owner_clarification`
- `status_update`
- `delivery_signal`
- `blocker_signal`
- `reopen_signal`

A candidate may later be reclassified downstream, but detection should always provide an initial category.

---

## Explicit vs implicit detection rules

## Explicit

Use when:

- future action is directly stated
- actor is named or strongly implied in grammar
- commitment language is direct

Typical markers:

- “I’ll”
- “I can”
- “I will”
- “I’ll handle”
- “I’ll send”
- “we’ll”
- “can you”
- “will you”
- “X will”
- “let me”
- “I’ll take care of it”

---

## Implicit

Use when:

- future work is expected
- actor or due date is missing or weak
- the sentence implies unresolved follow-through

Typical markers:

- “next step”
- “needs to”
- “still needs”
- “from our side”
- “someone should”
- “that has to go out”
- “we should get that over”
- “follow-up from us”

Important:  
Implicit detection should be intentionally allowed because many real commitments are expressed without formal task language.

---

## Source-specific detection rules

# Meetings

Meetings are rich in implied commitments, shared language, and vague ownership.

Detection priorities in meetings:

- explicit promises
- implied next steps
- collective commitments
- ownership gaps
- deadline hints
- follow-up statements
- “we should / next step / from our side” language

Meeting-specific rules:

- preserve surrounding speaker turns
- capture attribution uncertainty if speaker labels are weak
- allow broader implicit detection than in email
- collective language should not block detection
- mark ambiguous transcript spans for re-analysis if wording materially affects commitment meaning

Examples to detect:

- “I’ll send that over tomorrow.”
- “Next step is pricing from us.”
- “Can someone own the follow-up?”
- “We should get legal a new version.”
- “I’ll review and circle back.”
- “Let’s have Ben send the intro.”

Examples to suppress unless strengthened by context:

- “Maybe we could try that.”
- “One thing we discussed was sending something.”
- “We talked about updating it.”

---

# Slack

Slack is a primary source of small practical commitments, clarifications, and progress updates.

Detection priorities in Slack:

- accepted requests
- follow-up language
- quick practical commitments
- thread-based clarification
- delivery/status updates
- delays and blockers

Slack-specific rules:

- thread replies are first-class context
- short messages require contextual reading
- DMs and private channels are in scope
- message edits may update interpretation
- reactions alone should not create commitments for MVP
- a short phrase like “I’ll do it” is meaningful if thread context makes the object clear

Examples to detect:

- “I’ll check.”
- “Let me look into that.”
- “I’ll send it after lunch.”
- “Can you take this today?”
- “Yep, I’ll handle it.”
- “Done, sent.”
- “Still waiting on them.”
- “I’ll reply to the client.”

Examples to suppress:

- “Maybe.”
- “Could be.”
- “Interesting.”
- “Let’s discuss later” unless it clearly creates a follow-up expectation

Slack-specific note:  
Small commitments should not be filtered out merely because the language is casual.

---

# Email

Email tends to carry more formal, externally consequential commitments and clearer deliverable expectations.

Detection priorities in email:

- client-facing promises
- follow-up timing
- delivery statements
- revision promises
- review/response obligations
- delayed or renegotiated timing

Email-specific rules:

- quoted historical email text should not be re-detected as fresh commitment content
- outbound vs inbound direction matters
- external recipients increase priority hint
- attachments and subject lines may strengthen context but should not alone create commitment candidates
- a reply that confirms or delays a promise should be captured as a modifying signal

Examples to detect:

- “I’ll send the revised proposal tomorrow.”
- “We’ll get that over by Monday.”
- “Let me review and revert.”
- “I’ll circle back after I check with legal.”
- “Attached is the draft.”
- “We need to move this to next week.”

Examples to suppress:

- email quote text from prior chain
- “Thanks”
- “Received”
- “Looks good” unless it changes state of an existing commitment downstream

---

## Context window rules

Detection must never rely only on the trigger sentence in isolation when surrounding context is available.

For every candidate signal, Rippled should store a context window.

## Meetings

Store:

- triggering segment(s)
- preceding and following speaker turns
- enough transcript window to interpret ownership and object
- speaker metadata and timestamps

Default guideline:

- at least 1 to 3 turns before and after, or bounded time range around the trigger

## Slack

Store:

- parent message if in thread
- immediate neighboring replies
- linked request if the detected message is an acceptance
- channel/DM metadata
- sender and mentions

## Email

Store:

- current message body excluding quoted historical text
- thread metadata
- sender/recipient roles
- prior immediate email in thread if needed for object resolution

Context matters especially for:

- “I’ll do it”
- “sent”
- “will do”
- “let me check”
- “next week works”
- “I can take this”

---

## Detection triggers

Detection can begin from one or more of the following trigger types.

### 1. Ownership/action trigger

Examples:

- “I’ll send”
- “I’ll handle”
- “Sarah will”
- “can you review”

### 2. Obligation trigger

Examples:

- “needs to”
- “still needs”
- “has to”
- “should get sent”

### 3. Timing trigger

Examples:

- “tomorrow”
- “by Monday”
- “later today”
- “next week”
- “end of month”

Timing alone is not enough, but timing attached to action language is important.

### 4. Delivery/progress trigger

Examples:

- “sent”
- “done”
- “handled”
- “waiting on”
- “revised and attached”

### 5. Clarification/change trigger

Examples:

- “actually”
- “instead”
- “moving this to”
- “I’ll take that”
- “that’s on me”

---

## Candidate creation rules

A detection candidate should be created when:

1. There is plausible future work, follow-up, ownership, delivery, or obligation implied.  
2. The signal is not purely historical, hypothetical, or conversational filler.  
3. There is enough local context to preserve meaning, even if not enough to fully resolve the commitment.  
4. The signal could matter if forgotten, delayed, or left unassigned.

Important:

Candidate creation should favor preservation over premature rejection in cases of:

- explicit commitment language
- external/client-facing expectation
- practical small follow-ups
- accepted requests
- unresolved next steps

---

## Initial priority hints at detection time

Detection should not decide final surfacing, but it should assign a lightweight priority hint for downstream use.

Suggested values:

- `high`
- `medium`
- `low`

Priority hint factors:

1. external vs internal  
2. explicit due date present  
3. business consequence cues  
4. explicit delivery promise  
5. client-facing context  
6. repeated unresolved follow-up language  
7. small practical commitment without broader consequence usually lower, but still captured

Examples:

### High

- “I’ll send the proposal to the client by Friday.”
- “We’ll have the revised contract over tomorrow.”

### Medium

- “I’ll look into this and reply later today.”
- “Can you send the intro after this?”

### Low

- “I’ll check.”
- “Let me take a look.”  
  Still capture, especially in Slack.

---

## Big promise vs small commitment hints

Detection should assign a preliminary class hint:

- `big_promise`
- `small_commitment`
- `unknown`

Default classification priority:

1. external vs internal  
2. explicit due date  
3. business consequence

Examples:

### Big promise

- external email promising a proposal tomorrow
- client meeting promise with explicit delivery timing
- internal commitment with serious business consequence and due date

### Small commitment

- Slack “I’ll check”
- “I’ll send that over later”
- “let me confirm”
- DM acceptance of a practical follow-up

Important:  
This is only a hint. Final classification may be refined later.

---

## Observation flags

Some detected signals should not immediately trigger clarification or strong surfacing.

Detection should be able to mark a candidate as suitable for **silent observation**.

Mark for observation when:

- ownership may resolve naturally in follow-up messages
- timing is vague but likely to become clearer soon
- message is short and context may develop
- thread is still active
- external follow-up timing window has not yet elapsed
- the signal is real enough to keep, but not yet intrusive enough to surface prominently

Default source-aware observation guidance:

- Slack internal: up to 2 working hours
- internal email: 1 working day
- external email: 2 to 3 working days
- internal meeting-derived signals: 1 to 2 working days
- external meeting-derived signals: 2 to 3 working days

These are default assumptions and should later be configurable.

---

## Re-analysis flags

Detection should be able to recommend re-analysis when the wording is too ambiguous or transcript quality may materially change meaning.

Mark for re-analysis when:

- speaker attribution seems uncertain
- due date wording appears misheard
- the difference between suggestion and commitment is unclear
- overlapping speech affects ownership interpretation
- a key action verb is garbled or incomplete
- a meeting segment appears materially ambiguous

For MVP:

- meetings are the primary place where re-analysis flags matter
- Slack/email usually do not need re-analysis beyond contextual interpretation

---

## Detection heuristics

The detection layer should combine deterministic heuristics with model assistance.

## Deterministic heuristics should be used for:

- common future-action phrases
- assignee patterns
- timing phrase extraction
- thread/request-acceptance patterns
- quoted email stripping
- message direction metadata
- explicit delivery verbs
- basic negative pattern suppression

## Model assistance should be used for:

- implicit obligation interpretation
- differentiating suggestion vs commitment in ambiguous cases
- understanding short Slack replies in thread context
- interpreting collective language
- evaluating whether something creates real expectation
- identifying likely object/deliverable when text is compressed

Important:  
Rippled should not rely purely on prompts for business logic. Detection must be backed by schema-driven outputs and deterministic validation.

---

## Channel-specific examples

## Meetings

### Detect

> “I’ll send the revised deck tomorrow.”

Reason:

- explicit self-commitment
- due date present
- likely high-priority if external

### Detect

> “Next step is pricing from us.”

Reason:

- implicit next step
- ownership unresolved
- high value for clarification later

### Detect

> “Can someone send the recap after this?”

Reason:

- request for action
- no owner yet
- candidate worth preserving

### Suppress

> “Maybe we could send a different version.”

Reason:

- hypothetical only

---

## Slack

### Detect

> “I’ll check.”

Reason:

- small practical commitment
- high cognitive-load relevance even if small

### Detect

> “Yep, I’ll handle it.”

Reason:

- accepted request in thread context

### Detect

> “Done, just sent.”

Reason:

- delivery/status signal for existing or recent commitment

### Suppress

> “Interesting”

Reason:

- no obligation implied

---

## Email

### Detect

> “I’ll send the revised proposal by Monday.”

Reason:

- explicit external promise
- due date present
- strong delivery expectation

### Detect

> “We need to move this to next week.”

Reason:

- commitment modification / deadline change

### Detect

> “Attached is the updated version.”

Reason:

- likely delivery signal

### Suppress

Quoted chain text containing:

> “I’ll send the revised proposal by Monday.”

Reason:

- historical quoted content, not a fresh signal

---

## Edge cases

### 1. “Will do”

Rule:

- detect only if nearby context makes the action object clear

### 2. “Let me know”

Rule:

- not a commitment by itself

### 3. “I’ll try”

Rule:

- detect, but lower initial confidence hint due to hedging

### 4. “We’ll send”

Rule:

- detect strongly, but mark unresolved owner

### 5. “Can you…?”

Rule:

- detect as request-for-action even before acceptance
- downstream can decide whether accepted obligation was formed

### 6. “Someone should…”

Rule:

- detect as unresolved obligation, not resolved commitment

### 7. “Sent”

Rule:

- detect as delivery/status only if context exists

---

## Locked decisions

- Meetings, Slack, and email are all first-class detection sources.
- Small practical commitments are in scope and should not be filtered out merely for being small.
- External/client-facing commitments should receive higher priority hints.
- “We” should not resolve ownership at detection time.
- Detection should preserve ambiguity rather than force interpretation.
- Detection should support silent observation rather than immediate clarification by default.
- Slack threads and email threads are first-class context.
- Quoted email text should be excluded from fresh detection.
- DMs and private Slack channels are in scope if accessible.
- Detection should distinguish candidate signals from final commitments.

---

## Default MVP rules

- Prioritize high recall for explicit commitments.
- Allow implicit commitment detection, especially in meetings.
- Capture small Slack follow-ups as valid candidate signals.
- Detect requests and acceptances separately when possible.
- Mark external promises with higher priority hints.
- Use context windows for all detections.
- Preserve status-bearing signals like sent/done/delayed.
- Assign initial `big_promise` / `small_commitment` hints.
- Mark ambiguous meeting segments for potential re-analysis.
- Prefer observation before clarification where natural follow-up may still resolve ambiguity.

---

## Open questions for later evolution

These do not need to block MVP, but should remain open:

- whether reaction patterns in Slack should ever count as weak status signals
- whether calendars should contribute to detection of implicit commitments later
- whether user-specific relationship heuristics should influence likely owner suggestions
- whether some internal roles should have stronger implied ownership patterns
- whether business consequence can be inferred automatically with sufficient trust

---

## Implications for downstream systems

### For extraction

Detection must preserve enough context that extraction can distinguish:

- real commitment
- unresolved next step
- suggestion
- delivery
- blocker
- clarification

### For scoring

Detection should provide useful but lightweight hints, not authoritative scores.

### For clarification

Detection should mark ambiguity types early, especially:

- unresolved owner
- unresolved deadline
- unclear object
- uncertain commitment strength

### For surfacing

Detection should not decide what gets shown, but it should preserve the signals needed to support:

- main commitments
- shortlist items
- clarification queue

---

## Success criteria

This brief is successfully implemented when the detection layer can reliably do the following across meetings, Slack, and email:

- capture explicit commitments with high recall
- preserve small practical commitments that matter cognitively
- identify implicit next steps without turning all discussion into noise
- detect modifying and delivery-related signals
- preserve enough context for downstream interpretation
- treat external promises as higher-priority candidates
- avoid obvious false positives like hypotheticals and quoted email text
- produce structured candidate signals rather than brittle freeform output

---

## Summary

Rippled’s detection layer should behave like an attentive assistant, not a task factory.

It should notice the moments that could matter, especially the small ones people forget, without pretending those moments are already fully understood. Its job is to capture likely commitment signals across meetings, Slack, and email, preserve their context and ambiguity, and hand them off cleanly for later interpretation, scoring, clarification, and surfacing.

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 3. Commitment Domain Model Brief]] | The model that detection candidates feed into |
| [[Rippled - 4. Source Model Brief]] | Source-specific signal quality and detection context rules |
| [[Rippled - 5. Commitment Lifecycle Brief]] | How detected candidates map to lifecycle states (proposed, active) |
| [[Rippled - 9. Clarification Brief]] | What happens to detected signals that lack owner/deadline/deliverable |
| [[Rippled - 10. Completion Detection Brief]] | Delivery and status signals detected in the same pipeline |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |