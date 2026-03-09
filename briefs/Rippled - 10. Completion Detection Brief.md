---
tags: [rippled, completion, delivery, engineering]
brief: "10 — Completion Detection"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Completion Detection Brief

## Purpose

Define how Rippled should detect that a commitment has likely been delivered, fulfilled, or otherwise completed, using signals from meetings, Slack, email, and later other work artifacts.

This brief exists to make completion handling trustworthy, low-noise, and useful for reducing cognitive load.

Rippled should help the user feel:

- “I probably already handled this.”
- “This looks delivered, even if nobody explicitly said ‘done.’”
- “This may still need follow-up.”
- “This was delivered, but not necessarily closed.”

It should not pretend to know completion with certainty when the evidence is weak.

---

## Why this matters

A commitment system that only detects promises creates a new burden if it cannot also detect when things were actually handled.

For Rippled, completion detection is essential because:

- many real commitments are fulfilled implicitly, not explicitly
- users often do the work but do not mark it anywhere
- email and Slack often contain delivery proof
- cognitive load comes not only from forgetting commitments, but from repeatedly wondering whether something was already taken care of

Completion detection should reduce this mental backtracking.

---

## Core principle

Rippled should infer completion more often than users explicitly report it, but should express that inference as a confidence-based suggestion, not a hard fact.

---

## Non-goals

This system should not:

- require formal sign-off before recognizing likely delivery
- assume every “done” message equals true completion
- treat completion and closure as the same thing
- overwrite earlier evidence or lose history
- present weakly inferred completion as certain
- create excessive prompts asking users to confirm obvious work

---

## Key definitions

### Commitment

A unified object representing a likely obligation, promise, follow-up, or deliverable derived from one or more communication signals.

### Delivery

The committed action or output appears to have been performed or sent.

Examples:

- proposal emailed
- invoice sent
- draft shared
- reply given
- requested information provided

### Completion

A broader assessment that the commitment has likely been fulfilled to the extent originally promised.

In MVP, delivery and completion can usually be treated together operationally, while remaining conceptually distinct in the model.

### Closure

The commitment no longer needs active attention.

Closure may happen because:

- delivery occurred and enough time passed
- recipient acknowledged completion
- no follow-up appeared after a configured period
- the user marked it resolved
- a newer signal superseded it

Delivery does not always mean closure.

### Reopening

A delivered or closed commitment can become active again if later signals indicate revision, failure, rejection, or further required action.

---

## Relationship to lifecycle

Completion detection should feed the commitment lifecycle, but not fully define it.

Relevant states:

- `active`
- `delivered`
- `closed`

Allowed transitions include:

- `active -> delivered`
- `delivered -> active`
- `delivered -> closed`
- `closed -> active`

State transitions are based on evidence and confidence, not just time.

---

## What counts as completion evidence

Completion evidence should be evaluated as a set of signals, not a single rule.

### Strong evidence

Signals that strongly imply the committed action happened.

Examples:

- outbound email sent to expected recipient with expected attachment
- outbound email containing promised material in body
- Slack message saying “sent,” “done,” “handled,” or equivalent, when linked to the commitment context
- Slack reply containing the promised answer, artifact, or update
- file/artifact shared that matches the promised deliverable
- message explicitly confirming completion of the committed action

### Moderate evidence

Signals that suggest completion but may still be ambiguous.

Examples:

- “took care of it”
- “should be sorted now”
- “let me know if anything else is needed”
- email reply that appears to continue the promised follow-up but does not clearly show the actual deliverable
- document created or attached with a similar name but unclear target or recipient
- meeting discussion indicating the item was handled

### Weak evidence

Signals that may be relevant but should not usually trigger delivered state by themselves.

Examples:

- “looking into it”
- “working on it”
- “almost done”
- “I started that”
- draft artifact exists but not clearly sent/shared
- another person references the topic without confirming delivery

---

## Channel-specific completion rules

## 1. Email

Email is one of the strongest completion sources, especially for external commitments.

### Email should support completion detection as:

- proof of delivery
- evidence of fulfillment
- clarification of what was sent
- evidence of recipient response
- evidence of revised or reopened work

### Strong email completion cases

- user said they would send something, and a later outbound email includes that item
- user promised a follow-up, and outbound email contains the follow-up content
- user promised an introduction, and outbound email includes both intended parties
- user promised pricing/proposal/details, and email body or attachment clearly matches

### Email features relevant to completion

- outbound vs inbound direction
- sender
- recipients
- subject
- thread membership
- body content
- attachment names
- attachment text/content when available
- timestamps
- quoted-text stripping
- reply chain context

### Important email rules

- outbound email should be treated as strong completion evidence for delivery-oriented commitments
- quoted prior email text should not count as new fulfillment evidence
- attachment presence alone is not enough; attachment relevance should be assessed where possible
- external email should generally weigh more heavily than internal email for completion confidence
- recipient acknowledgement can strengthen confidence or support closure, but should not be required

---

## 2. Slack

Slack is a strong source for small commitments, progress signals, and implicit completion.

### Slack should support completion detection as:

- direct completion claim
- reply with the promised answer/update
- artifact sharing
- thread resolution
- clarification of whether work was actually done

### Strong Slack completion cases

- “Done”
- “Just sent it”
- “Handled”
- “Shared the deck here”
- “I’ve replied to them”
- posting the promised file/link in-thread
- answering the exact open question that was committed to

### Moderate Slack completion cases

- “Should be good now”
- “I think that’s sorted”
- “Put something together quickly”
- “Dropped it in the drive”
- “Made the edits”

### Important Slack rules

- thread replies are first-class context
- DMs and private channels are in scope where permissions allow
- edits may update interpretation of completion evidence
- channel context matters; “done” with no nearby relevant commitment should not trigger completion
- internal Slack completion can be accepted at lower strictness than external/client-facing delivery, but still must remain confidence-based

---

## 3. Meetings

Meetings are weaker as direct completion proof, but can still provide useful evidence.

### Meeting completion detection should focus on:

- statements that prior commitments have been completed
- statements that deliverables were already sent
- discussion of completion status
- evidence that an item is now closed or still open

### Stronger meeting completion examples

- “I already sent the proposal yesterday”
- “The invoice went out this morning”
- “That deck has been shared with them”

### Weaker meeting completion examples

- “I think that’s done”
- “That should be okay now”
- “We’ve probably handled that”

### Important meeting rules

- meeting evidence can raise completion confidence
- meeting evidence alone should often be weaker than direct email/Slack evidence for delivery-oriented commitments
- if meeting statements conflict with missing downstream delivery evidence, Rippled should preserve ambiguity rather than force completion

---

## 4. Future artifact sources

Later, completion detection may also use:

- calendar events
- file storage systems
- task systems
- CRM updates
- document comment activity
- e-signature or payment systems

These are out of MVP unless explicitly added.

---

## Completion evidence by commitment type

Completion confidence should vary by commitment type because some commitments leave clearer traces than others.

## Type A: Send / share / deliver

Examples:

- send proposal
- share deck
- send invoice
- send introduction
- send notes

These are the easiest to detect.

Strong signals:

- outbound email
- shared file/link
- explicit “sent/shared”
- recipient response

These should generally allow higher completion confidence.

## Type B: Reply / follow up / answer

Examples:

- get back to them
- reply to client
- answer question
- follow up next week

Strong signals:

- outbound reply
- Slack response in relevant thread
- meeting statement plus linked outbound proof

Moderate difficulty.

## Type C: Review / check / look into

Examples:

- look into issue
- review draft
- check numbers
- investigate bug

These are harder to prove.

Strong signals may include:

- explicit completion message
- response with findings
- review comments or summary
- subsequent decision based on completed review

These should default to lower completion confidence unless more direct evidence exists.

## Type D: Create / revise / prepare

Examples:

- update proposal
- prepare draft
- revise contract
- pull numbers

Evidence depends on whether the output was shared or only internally prepared.

If preparation was promised but not yet delivered, the system may infer partial completion but should not treat it as closed delivery unless context supports that.

## Type E: Coordinate / introduce / arrange

Examples:

- make intro
- schedule meeting
- connect parties
- coordinate next step

These can often be strongly evidenced by outbound communication or accepted calendar events.

---

## Completion confidence model

Completion detection should produce a structured confidence assessment, not only a binary result.

### Suggested dimensions

- `completion_confidence`
- `delivery_confidence`
- `evidence_strength`
- `recipient_match_confidence`
- `artifact_match_confidence`
- `closure_readiness_confidence`

Not all dimensions need to be surfaced to the user, but they should exist internally where useful.

### Factors that increase confidence

- explicit completion language
- direct match between promised action and later signal
- expected recipient match
- expected artifact match
- time proximity between promise and delivery
- same actor performing promised action
- same thread or linked context
- external/client-facing confirmation patterns
- multiple corroborating signals across channels

### Factors that decrease confidence

- vague completion language
- unclear recipient
- unclear artifact relevance
- different actor than expected
- long time gap with weak linkage
- conflicting later signals
- “we” language with no resolved owner
- signals that imply work is still in progress
- quoted or forwarded text causing false matches

---

## Matching logic

Completion detection should try to match later signals against an existing commitment.

### Matching dimensions

- actor match
- recipient/target match
- deliverable match
- topic/entity match
- time window match
- thread/conversation continuity
- explicit linguistic match

### Examples

#### Example 1: Strong match

Commitment:

> “I’ll send the proposal by Friday.”

Later evidence:

- outbound email Friday afternoon
- attachment named `Proposal_Acme_v3.pdf`
- recipient includes Acme contact

Result:

- high delivery confidence
- likely `active -> delivered`

#### Example 2: Medium match

Commitment:

> “I’ll get back to them tomorrow.”

Later evidence:

- outbound email next day
- same thread
- no direct wording match, but plausible reply

Result:

- moderate to high confidence depending on context

#### Example 3: Weak match

Commitment:

> “I’ll look into the issue.”

Later evidence:

- Slack message two days later: “done”

Result:

- moderate at best unless nearby context or follow-up details support it

---

## Suggested state-transition rules

These are MVP defaults, not permanent truths.

### Move to `delivered` when:

- completion confidence is above threshold
- evidence reflects likely fulfillment of the commitment itself
- no strong contrary evidence exists

### Stay `active` when:

- only weak progress signals exist
- completion evidence is ambiguous
- something was prepared but not clearly sent/shared when delivery was part of the promise
- later signals imply the work is still ongoing

### Move from `delivered` to `closed` when:

- recipient acknowledgement exists, or
- no contrary signals emerge during a configurable inactivity window, or
- user confirms, or
- a later signal clearly implies the thread has been resolved

### Reopen to `active` when:

- revision requested
- rejection or correction requested
- later message says it still has not been handled
- follow-up obligation emerges from the original work
- prior delivery did not actually satisfy the promise

---

## Auto-close behavior

Rippled should support configurable auto-close behavior.

### Default principle

Delivered should not immediately equal closed.

### MVP default

Allow closure after a user-configurable inactivity period following likely delivery.

Examples:

- external/client-facing delivery: close after X days without contrary signal
- internal delivery: close after a shorter or user-defined window
- no-reply after requested feedback may still permit closure after configured time

Auto-close should always remain reversible.

---

## Suggested values Rippled may generate

When Rippled detects likely completion, it may also suggest:

- likely completion status
- likely delivery timestamp
- likely delivered artifact
- likely recipient/target
- likely next step
- likely closure readiness

Safety order for suggestion:

1. likely next step  
2. likely completion/delivery  
3. likely owner linkage  
4. likely due-date resolution implications

---

## Handling ambiguity

Completion ambiguity should be preserved, not flattened.

### Examples of ambiguity

- work may be done internally but not yet delivered externally
- user said “sent,” but no matching artifact or recipient is visible
- another team member completed the work, but ownership was unresolved
- promised revision was sent, but response indicates more work is needed

In ambiguous cases, Rippled should:

- keep the evidence
- keep confidence explanations
- avoid over-promoting to closed
- optionally surface a light suggestion rather than a hard state change

---

## Internal vs external strictness

External/client-facing commitments should be treated more strictly than internal ones.

### External commitments

- surface faster
- require stronger completion matching
- escalate sooner when still unresolved
- treat outbound email and attachment signals as highly important

### Internal commitments

- can accept more implicit evidence
- can remain more lightly tracked
- may rely more on Slack completion signals
- should still avoid pretending certainty

---

## Examples

## Example 1: External email delivery

Commitment:

> “I’ll send the proposal by Thursday.”

Evidence:

- outbound email Thursday 4:12 PM
- recipient is client contact
- attachment text includes proposal title

Result:

- high delivery confidence
- state likely becomes `delivered`
- auto-close timer begins

## Example 2: Slack small commitment

Commitment:

> “Let me look into that.”

Evidence:

- same Slack thread, 90 minutes later
- “Found the issue, fixed now”

Result:

- moderate to high completion confidence
- likely delivered for shortlist purposes
- closure depends on later replies or silence

## Example 3: Internal handoff with external step remaining

Commitment:

> “I’ll get the revised pricing to Sarah.”

Evidence:

- internal email to Sarah with revised pricing
- no client-facing send yet

Result:

- internal handoff may be delivered
- if broader commitment target was client delivery, Rippled should infer likely next step remains open
- do not mark the client-facing commitment closed

## Example 4: Reopened after delivery

Commitment:

> “I’ll send the draft contract.”

Evidence:

- outbound email with draft contract
- later email reply: “Can you revise clause 4 and resend?”

Result:

- previously delivered commitment may reopen or create linked follow-up work
- preserve history of original delivery

## Example 5: Weak false completion risk

Commitment:

> “I’ll review the deck.”

Evidence:

- later Slack message: “done”

Result:

- insufficient by itself unless linked context confirms it refers to the deck review
- likely remain active or only lightly suggested as possibly complete

---

## Locked MVP decisions

- meetings, Slack, and email are all valid completion-evidence sources
- outbound email is strong completion evidence, especially for external commitments
- Slack replies and threads are first-class completion context
- quoted email text must not be treated as fresh evidence
- DMs and private Slack channels are in scope where permissions allow
- completion and closure are distinct
- delivered and closed states can reopen
- completion confidence must vary by commitment type
- Rippled should infer completion where justified, but express it as a suggestion rather than certainty

---

## Default MVP rules

- treat send/share/deliver commitments as easiest to verify
- treat review/check/look-into commitments as harder to verify
- use channel context plus linguistic match plus actor/recipient/artifact matching
- prefer multiple corroborating signals over single vague language
- allow likely delivery without recipient acknowledgement
- do not auto-close immediately on delivery
- auto-close should be configurable and reversible
- external commitments use stricter thresholds than internal commitments
- preserve evidence and explanations for every completion inference

---

## Open questions / future extension

These do not block MVP but should be left extensible:

- file content scanning depth for attachment/artifact relevance
- calendar-based completion evidence
- CRM/task system closure evidence
- user-specific relationship rules for implicit completion attribution
- stronger document-system integrations
- per-user completion sensitivity settings by commitment class
- completion bundling UX in shortlist vs main tab

---

## Engineering implications

This brief implies the system should support:

- unified commitment objects with linked multi-source signals
- thread-aware email and Slack ingestion
- outbound/inbound distinction for email
- artifact metadata and optional text extraction
- state history and reversible transitions
- structured confidence scoring
- configurable inactivity windows for auto-close
- evidence retention for audit and replay
- separate handling for delivery vs closure
- typed completion events or inferred completion records

---

## Testing requirements

Please include tests covering:

### Unit tests

- outbound email as strong completion evidence
- quoted email stripping
- Slack thread completion detection
- weak “done” message without context should not over-complete
- attachment relevance matching
- delivery vs closure distinction
- reopen behavior after revision request
- internal vs external threshold differences

### Integration tests

- promise in meeting -> delivery in email
- promise in Slack -> completion in Slack thread
- internal handoff completed but external delivery still pending
- explicit delivery followed by reopening signal
- ambiguous completion language that stays unresolved

### Fixtures

Create fixtures for:

- send proposal
- follow up by email
- small Slack promise
- review/look-into commitment
- internal-to-external handoff chain
- delivered then reopened scenario

---

## Success criteria

This brief is successful if Rippled can:

- detect likely completion without requiring manual marking
- distinguish delivered from closed
- avoid over-claiming certainty
- reduce repeated attention on already-handled commitments
- preserve enough ambiguity to remain trustworthy
- reopen commitments correctly when later signals show more work remains

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 3. Commitment Domain Model Brief]] | Delivery/closure states and evidence fields defined in the domain model |
| [[Rippled - 4. Source Model Brief]] | Source-specific completion evidence patterns (email, Slack, meetings) |
| [[Rippled - 5. Commitment Lifecycle Brief]] | The delivered/closed state transitions this brief drives |
| [[Rippled - 8. Commitment Detection Brief]] | Delivery signals detected in the same pipeline as commitment signals |
| [[Rippled - 9. Clarification Brief]] | Completion ambiguity cases that may escalate to clarification |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |