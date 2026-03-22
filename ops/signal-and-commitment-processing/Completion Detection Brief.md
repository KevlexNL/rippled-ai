## Completion Detection Brief

### Purpose

Define what counts as evidence that a commitment has been delivered, completed, closed, or partially satisfied.

### Why this matters

Completion is one of the highest-value moments in the product. Users do not just want help remembering what they promised; they want help knowing what is actually done without manually tracking everything. Your development brief explicitly frames this doc around outbound email, attachments, Slack “done/sent/handled,” document evidence, recipient acknowledgement, later calendar evidence, and commitment-type-specific rules.

### Locked decisions

* Completion detection is evidence-based, not phrase-based only.
* “Delivered” and “completed” are related but distinct.
* Completion must usually link back to an existing commitment or very strong candidate.
* Different commitment types may complete differently.
* Different sources provide different strengths of completion evidence.
* Completion confidence is separate from commitment existence confidence.
* Weak completion evidence should not silently close work.

### Default MVP rules

#### 1. Core completion states

Use these distinctions:

**Delivered**
The promised artifact or response appears to have been sent or provided.

**Completed**
The work appears done according to the commitment’s type or expected outcome.

**Closed**
The item is no longer active, whether because it completed, was canceled, or became irrelevant.

This aligns with the broader spec direction that lifecycle needs a meaningful distinction between delivered, completed, and closed. 

#### 2. Completion evidence types

Allowed evidence sources in MVP:

* outbound email
* email attachments
* email links
* Slack completion language
* document or file evidence
* recipient acknowledgement
* later cross-signal confirmation

#### 3. Evidence strength bands

**Strong**

* explicit completion language tied to a specific deliverable
* attachment or link evidence present
* clear outbound response to the requester
* strong thread or entity linkage

**Medium**

* explicit completion language without artifact evidence
* likely linkage to the active commitment
* supporting cross-signal context, but not definitive

**Weak**

* vague status language
* gratitude-only response
* acknowledgment without evidence
* artifact exists but linkage is poor

#### 4. Source-specific completion logic

**Email**
Strong completion source for:

* sending documents
* answering requests
* delivering promised outputs
* confirming handoff

Rules:

* outbound email with clear deliverable language is strong evidence
* attachment presence materially increases confidence
* reply position in thread matters
* recipient acknowledgement can strengthen completion but should not be required in all cases
* only latest authored message should drive new completion evidence in email-specific parsing 

**Slack**
Useful for:

* lightweight internal completion
* quick handoffs
* “done / sent / handled / pushed” statements

Rules:

* require stronger linkage than email when artifact evidence is absent
* emoji or reaction-only evidence is weak
* screenshots or doc links increase confidence

**Meetings**
Usually weak as direct completion evidence.
Useful more for:

* confirming that work was said to be done
* clarifying interpretation of progress
* linking later evidence

#### 5. Commitment-type-specific rules

**Artifact delivery commitments**
Examples:

* send proposal
* share deck
* forward contract

Likely completion condition:

* outbound delivery evidence
* attachment / link / sent confirmation

**Reply / response commitments**
Examples:

* get back to client
* answer question
* send update

Likely completion condition:

* outbound reply matching the ask

**Action / execution commitments**
Examples:

* fix bug
* review document
* talk to legal

Likely completion condition:

* stronger need for corroborating evidence
* “done” alone may be insufficient unless source context is strong

**Coordination commitments**
Examples:

* loop in Sarah
* schedule meeting
* hand off to ops

Likely completion condition:

* participant change, invite creation, forward/handoff evidence, or explicit confirmation

#### 6. Linking before completion

Before marking anything delivered or completed, attempt linkage using:

* same thread
* same participants
* same deliverable
* recency
* state compatibility
* source relevance

Hard rule:

* do not close an item from lexical completion language alone if no plausible linked commitment exists

#### 7. Recipient acknowledgement

Acknowledgement from the requester or recipient can strengthen completion, but should not always be mandatory.

Examples:

* “Got it, thanks”
* “Looks good”
* “Received”

Rules:

* strong for delivery verification
* weak for proving work-quality completion
* should not create false completion for unrelated commitments

#### 8. Partial completion

Some commitments may be partially fulfilled.

Examples:

* only one of two promised files sent
* initial draft sent, final version not yet sent
* update provided, but requested action still open

MVP rule:

* prefer `delivered` or `updated` over `completed` when evidence suggests partial fulfillment

#### 9. Reopen rules

A completed or delivered item may reopen when:

* requester says it is incomplete
* a correction is requested
* new follow-up work is explicitly tied to the same commitment
* the sent artifact is rejected or missing something material

#### 10. Completion output contract

Each evaluated commitment should produce:

* completion_evidence_ids[]
* completion_confidence
* completion_state_recommendation
* rationale_codes[]
* needs_review flag if evidence conflicts

### Examples

#### Example 1 — outbound email with attachment

Commitment: “Send revised proposal by Friday.”
Later email reply: “Attached.” with file.

Result:

* strong completion evidence
* likely mark delivered
* mark completed if commitment type is delivery-based

#### Example 2 — Slack statement

“I handled it.”

Result:

* medium or weak depending on linkage
* do not complete unless active commitment match is strong

#### Example 3 — recipient acknowledgement

“Received, thanks.”

Result:

* strengthens delivered status of the linked item
* does not necessarily prove broader work completion

#### Example 4 — action commitment without artifact

“I finished reviewing the contract.”

Result:

* medium completion evidence
* may need stronger context than simple delivery tasks

### Open questions / future extension

* Should some commitment types require recipient acknowledgement before auto-completion?
* When should file creation or document edits count as completion evidence directly?
* Should calendar evidence later support coordination-completion states?
* How aggressively should Rippled reopen completed items after follow-up messages?

### Implications for engineering / UX

* Engineering needs a completion evaluator separate from detection.
* State transitions should be evidence-gated and auditable.
* UX should show why Rippled thinks something is delivered or completed.
* Medium-confidence completion should often be phrased as tentative, not final.

My honest take: these three are now at the right level. They are specific enough to build against, but still loose enough to adapt once you see first-pass outputs and actual failure modes, which is exactly how your development brief says these Level 2 docs should behave.

The next clean step would be to write the **Confidence & Scoring Brief**, because these three now depend on a shared scoring and routing model.