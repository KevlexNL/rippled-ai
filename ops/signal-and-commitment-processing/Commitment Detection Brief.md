## Commitment Detection Brief

### Purpose

Define how Rippled detects likely commitments from normalized signals and turns them into structured commitment candidates.

### Why this matters

This is the front door of the intelligence layer. If detection is too loose, the product becomes noisy and untrustworthy. If detection is too strict, it misses the moments users actually care about. Rippled should detect more than it surfaces, but it should not pretend every action-adjacent phrase is a real commitment. That fits the broader product stance of reducing ambiguity in layers rather than over-specifying everything as certainty too early.

### Locked decisions

* Detection operates on **normalized signals**, not raw provider payloads.
* Detection produces **commitment candidates**, not final truth objects.
* One signal may produce zero, one, or multiple candidates.
* Detection is separate from:

  * clarification
  * confidence scoring
  * lifecycle transitions
  * surfacing
* Explicit and implicit commitments are both in scope.
* Detection rules are **channel-aware**, but outcomes must map into the shared commitment engine.
* Quoted or historical context may support interpretation, but should not create current candidates by default.
* The system should prefer **tentative candidate creation + later validation** over false finality.

### Default MVP rules

#### 1. Detection input

Detection consumes a `NormalizedSignal` with:

* source type
* participants
* latest authored text
* bounded prior context
* attachments / links
* timestamps
* source metadata

#### 2. Detection output

Detection emits `CommitmentCandidate` objects with:

* candidate id
* source signal id
* text span
* normalized text
* candidate type
* explicitness
* preliminary owner hypothesis
* deliverable hypothesis
* timing hypothesis
* evidence markers
* initial existence confidence

#### 3. Candidate classes

MVP candidate classes:

* request
* self_commitment
* acceptance
* status_update
* completion
* cancellation
* decline
* reassignment
* informational

#### 4. Positive detection patterns

A signal is more likely to produce a candidate when it contains:

* direct requests
* explicit promises
* confirmations of ownership
* explicit due dates or delivery statements
* statements that imply responsibility transfer
* status language tied to a concrete deliverable
* completion language tied to a likely prior ask

Examples:

* “Can you send the revised deck by Friday?”
* “I’ll take care of this.”
* “Yes, I’ll get that over today.”
* “Sarah will handle the client response.”
* “Attached.”

#### 5. Negative detection patterns

A signal should not create a commitment candidate when it is mainly:

* informational
* social / courtesy language
* brainstorming without implied ownership
* rhetorical or hypothetical
* quoted history only
* signatures / disclaimers / footers
* acknowledgements without action meaning

Examples:

* “Thanks”
* “Looks good”
* “Interesting idea”
* “Maybe we could do this someday”
* “Per my previous email...” when no new action is introduced

#### 6. Explicit vs implicit detection

**Explicit** candidates include clear ask / promise / delivery language.
**Implicit** candidates include likely commitments inferred from context, such as:

* decisions that imply action
* “I can do that”
* “Let’s have John take this”
* “Will review and circle back”

Rules:

* explicit candidates may be created at lower uncertainty
* implicit candidates require higher evidence or stricter confidence gates
* implicit detection should be more conservative in noisy channels

#### 7. Channel boundaries

**Email**

* prioritize direct asks, self-commitments, replies, due language, attachments
* only latest authored message creates new candidates by default
* quoted history supports linkage only
* single-recipient asks may infer owner more confidently than multi-recipient asks 

**Slack**

* allow lighter commitment language
* require stronger thread awareness
* be more conservative with reaction-only evidence
* tolerate informal phrasing, but not vague chatter

**Meetings**

* allow decision-derived and implied commitments
* require higher ambiguity tolerance
* expect later confirmation from other signals when possible

#### 8. Initial candidate creation rules

Create a candidate when all of the following are true:

* there is a plausible action / responsibility signal
* the statement is anchored to a participant or deliverable
* the text is current authored content, not historical context
* the signal exceeds the minimum existence threshold

Do not create a candidate when:

* the only evidence is quoted prior text
* action meaning depends entirely on guesswork
* the phrase is purely acknowledgment
* the signal is too weak to support later resolution

#### 9. Detection should not do final resolution

Detection may propose:

* likely owner
* likely deliverable
* likely due timing

But it must not finalize:

* lifecycle state
* clarification requirement
* surfacing decision
* merge / dedupe outcome

Those belong to later stages.

### Examples

#### Example 1 — email ask

“Can you send the revised proposal by Friday?”

Result:

* create request candidate
* explicit
* likely owner hypothesis present
* deliverable and due timing extracted

#### Example 2 — email confirmation

“Yes, I’ll get that over today.”

Result:

* create acceptance / self_commitment candidate
* must use bounded prior context for deliverable resolution
* candidate exists even before final linkage

#### Example 3 — Slack chatter

“Maybe we should update that page sometime.”

Result:

* no candidate or low-confidence observe-only candidate
* insufficient ownership / commitment strength

#### Example 4 — meeting decision

“John will send the deck tomorrow.”

Result:

* create likely commitment candidate
* explicit enough for candidate creation even if later confirmation is needed

### Open questions / future extension

* Should some users be allowed more aggressive implicit detection than others?
* How much should subject lines contribute in email detection?
* Should meeting-derived commitments require secondary confirmation more often than email commitments?
* When should repeated weak evidence across signals combine into one stronger candidate?

### Implications for engineering / UX

* Engineering needs a clean separation between extraction and later validation.
* Detection should return typed, inspectable outputs with text spans.
* UX should not expose raw candidates as facts.
* Replay tooling should show why a candidate was created and what pattern triggered it.

---
