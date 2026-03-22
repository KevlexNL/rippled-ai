

### Purpose

Define how email provider data becomes normalized email signals, how commitment candidates are extracted from emails, and how email-specific rules resolve ownership, lifecycle, confidence, and completion in MVP.

### Why this matters

Email is the cleanest high-value source for the first serious implementation. It contains many of the strongest external commitments, but it also introduces ambiguity through quoting, multiple recipients, implicit ownership, and reply chains. Your flowchart already centers the right resolution points: sender/receiver identification, latest-authored-only handling, single vs multi-recipient branching, and bounded use of prior messages for confirmation and unclear ownership. 

### Locked decisions

* Email is an MVP source.
* Email commits to the shared commitment engine and shared outcome enum.
* Only the **latest authored block** is eligible for new candidate extraction by default.
* Quoted history is context, not a new source of commitments.
* Owner inference must be stricter in multi-recipient email than single-recipient email.
* Prior-thread inspection is bounded:

  * immediate previous message first
  * expand only when necessary for confirmation/update linkage
* If owner resolution is weak, unresolved is preferred over false assignment.
* Org-role heuristics are out of scope for MVP, though they may be a future extension. That direction is already hinted at in the draft flowchart. 

### Default MVP rules

## A. Provider input contract

```text
EmailRawMessage
- provider_message_id
- provider_thread_id
- subject
- sent_at
- received_at
- from
- to[]
- cc[]
- bcc_present
- reply_to[]
- in_reply_to
- references[]
- body_text
- body_html
- attachments[]
- embedded_links[]
- labels / folders / mailbox metadata
```

## B. Normalized email signal contract

```text
EmailSignal
- signal_id
- source_type = "email"
- source_account_id
- source_thread_id
- source_message_id
- direction                    // sent | received
- authored_at
- actor_participants[]         // usually sender
- addressed_participants[]     // usually To
- visible_participants[]       // sender + To + CC
- latest_authored_text
- quoted_history_blocks[]
- prior_context_text           // bounded summary or raw slice
- attachments[]
- links[]
- subject
- source_metadata{}
```

## C. Preprocessing pipeline

### 1. Direction detection

Determine whether the message is:

* sent by the user
* received by the user

### 2. Participant extraction

Extract:

* sender
* To
* CC
* named individuals mentioned in latest authored text

### 3. Latest authored block isolation

Rules:

* strip signatures, disclaimers, and quoted history where possible
* isolate only the newest authored content
* keep quoted content separately for bounded contextual linking

### 4. Candidate segmentation

Split the latest authored block into candidate units by:

* sentence boundaries
* bullet boundaries
* numbered-list boundaries
* conjunction splits where multiple actions are clearly present

---

## D. Speech-act classes

Allowed email candidate classes:

* request
* self_commitment
* acceptance
* status_update
* completion
* cancellation
* decline
* reassignment
* informational

No other class in MVP.

---

## E. Email ownership resolution map

### 1. Single-recipient emails

Default rules:

* direct ask from sender → likely owner is recipient
* self-commitment from sender → owner is sender
* explicit completion from sender → owner is sender
* confirmation from sender about prior ask → link to prior ask first, then resolve owner

### 2. Multi-recipient emails

Priority order:

1. explicit named owner in current text
2. section-addressed recipient in current text
3. grammatical actor in current text
4. linked owner from prior message if this is a confirmation/update/completion
5. unresolved

Hard rule:

* never assign owner from CC alone
* never assume “any recipient” is safe enough for automatic surfacing without textual support

### 3. Prior-message context

Use previous-message context only to:

* resolve acceptance / confirmation
* link a status update
* link completion evidence
* understand reassignment or cancellation

Do not use older thread history by default for new candidate extraction.

These rules directly reflect the strongest logic in the draft map. 

---

## F. Deliverable resolution

For each candidate, resolve:

* action / deliverable
* requester
* likely owner
* beneficiary / target
* due timing
* dependencies / blockers if present

Fallback rules:

* vague deliverable with no strong thread link → clarification_needed
* vague owner with medium existence confidence → observe or clarify, do not over-assign
* vague timing does not block creation if commitment + owner are strong

---

## G. Thread-linking rules

For each candidate, determine whether it is:

* new commitment
* update to existing commitment
* completion of existing commitment
* cancellation / decline of existing commitment
* reassignment of existing commitment
* duplicate candidate
* multiple separate commitments in same email

Linking inputs:

* same thread
* same participants
* deliverable similarity
* timing compatibility
* current lifecycle state

Allowed actions:

* create
* update
* merge
* split
* complete
* cancel
* reopen
* observe
* clarify

---

## H. Confidence rules

### 1. Commitment existence confidence

Increase when:

* explicit ask or promise language exists
* clear deliverable exists
* direct imperative exists
* clear response context exists

Decrease when:

* hypothetical or brainstorming language dominates
* candidate depends only on quoted history
* courtesy language is mistaken for action
* multiple competing interpretations exist

### 2. Owner confidence

Increase when:

* owner named explicitly
* direct single-recipient ask
* sender uses self-commitment language
* confirmation clearly maps to prior ask

Decrease when:

* multiple recipients
* unclear section addressing
* generic pronouns
* ownership inferred only from social norms

### 3. Completion confidence

Increase when:

* explicit completion language
* attachment or link evidence
* strong thread linkage
* clear reply timing

Decrease when:

* vague “done”
* no linked active commitment
* gratitude-only response
* multiple possible referents

### Confidence bands

* **High**: can create/update/surface
* **Medium**: can observe, tentatively create, or clarify
* **Low**: suppress or observe only

---

## I. Completion detection rules for email

Email is one of the strongest completion channels, so completion rules should be explicit. Your broader brief already calls out outbound email, attachments, document/file evidence, recipient acknowledgement, and commitment-type-specific completion rules as part of completion detection. 

### Strong completion evidence

* “attached”
* “here it is”
* “sent over”
* “done”
* plus attachment, link, or strong match to prior ask

Outcome:

* mark delivered
* mark completed if commitment type supports completion-on-send

### Medium completion evidence

* “handled”
* “taken care of”
* “should be there”
* without artifact evidence

Outcome:

* update existing commitment only if strong linkage exists
* otherwise observe only

### Weak completion evidence

* “thanks”
* “sounds good”
* “looks good”
* “noted”

Outcome:

* do not mark complete

---

## J. Clarification routing

Clarify when:

* likely commitment exists
* user value is high
* one blocking field is missing:

  * owner
  * deliverable
  * due timing for an externally relevant commitment
  * target/beneficiary

Observe when:

* ambiguity is likely to resolve in next reply
* candidate is medium-confidence but not yet worth interruption

Suppress when:

* candidate is weak
* mostly informational
* contradicted by stronger evidence

This also matches your broader framework that clarification, uncertainty, silent observation windows, and confidence routing should be explicitly separated.  

---

## K. Email-specific guardrails

* Do not create candidates from signatures or disclaimers.
* Do not create new commitments from quoted history.
* Do not assume recipient ownership in multi-recipient email without textual support.
* Do not mark complete from politeness or acknowledgement alone.
* Do not merge multiple asks in one sentence unless same action/object is clearly shared.
* Do not use whole-thread expansion by default.
* Do not use org-role heuristics in MVP.

---

## L. Example cases

### Case 1 — single-recipient ask

Email from client to user:
“Can you send the revised proposal by Friday?”

Result:

* request
* owner = user
* requester = client
* deliverable = revised proposal
* due = Friday
* likely high confidence
* create new commitment

### Case 2 — sent self-commitment

Email from user to client:
“I’ll send the revised proposal tomorrow morning.”

Result:

* self_commitment
* owner = user
* due = tomorrow morning
* create or update linked commitment

### Case 3 — multi-recipient ambiguity

Email to three teammates:
“Can one of you handle this?”

Result:

* likely request exists
* owner unresolved
* observe or clarify
* do not assign automatically

### Case 4 — confirmation in reply

Reply:
“Yes, I’ll get that over today.”

Result:

* acceptance / self_commitment
* inspect previous message
* resolve deliverable from prior ask
* owner = sender of current reply

### Case 5 — completion with attachment

Reply:
“Attached.”

Attachment present.

Result:

* likely completion / delivery
* link to active commitment
* mark delivered, maybe completed

---

## M. Open questions / future extension

* Should subject lines contribute to deliverable resolution in MVP or only later?
* When should outbound email without explicit completion language still count as likely delivery?
* Should user-specific relationship heuristics influence multi-recipient owner ranking later?
* How much of prior thread should be summarized into the model prompt versus fetched on demand?

## N. Implications for engineering / UX

* Engineering needs a robust latest-authored-block extractor before model work becomes trustworthy.
* Email parsing quality will strongly affect false positives.
* UX should show evidence trail and tentative language, especially for medium-confidence multi-recipient cases.
* Clarification prompts should be rare and high-value.

## My honest take

These two docs are now at the right depth for where you are:

* **Source Model Brief** = foundational and worth locking fairly tightly
* **Email Integration / Detection Brief** = detailed enough to build against, but still easy to revise after first pipeline outputs

The next logical docs after this are:

* **Commitment Detection Brief**
* **Clarification & Missing Information Brief**
* **Completion Detection Brief**

Those three would let you separate shared logic from email-specific execution cleanly.