## Clarification & Missing Information Brief

### Purpose

Define what counts as incomplete, when Rippled should wait, when it should ask, and when it should quietly carry uncertainty without interrupting the user.

### Why this matters

Clarification is where trust can either compound or collapse. If Rippled asks too often, it becomes cognitive tax. If it never asks, it starts inventing certainty. This brief exists to keep the product aligned with its core stance: suggest, do not overclaim; reduce burden, do not create more of it. The development brief explicitly calls out missing owner, vague timing, unclear deliverable, uncertain commitment, silent observation windows, and the distinction between waiting and asking.

### Locked decisions

* Missing information is a first-class system concept.
* Clarification is not the default response to ambiguity.
* Unresolved is a valid system state.
* The system may:

  * clarify now
  * observe silently
  * suppress entirely
* Confidence and clarification are related but not identical.
* Clarification should be rare, high-value, and well-timed.
* External commitments should generally have stricter clarification rules than low-stakes internal chatter.
* Clarification should happen after candidate detection and preliminary resolution, not during initial extraction.

### Default MVP rules

#### 1. Clarification dimensions

A candidate may be incomplete on one or more of these axes:

* owner missing
* owner vague
* deliverable unclear
* target / beneficiary unclear
* due date missing
* timing vague
* commitment existence uncertain
* lifecycle linkage uncertain
* completion evidence ambiguous

#### 2. Missing vs vague vs uncertain

**Missing**
A required field is absent.
Example: “Can you do this?” with no clear owner in a multi-recipient thread.

**Vague**
A field exists but is too imprecise.
Example: “I’ll send it soon.”

**Uncertain**
The system is not sure the thing is a commitment at all.
Example: “Maybe we should look into that.”

#### 3. Required fields by stage

**To create a tentative commitment**
Need:

* likely existence
* some action / deliverable anchor
* at least one participant relationship

**To create a higher-confidence active commitment**
Prefer:

* owner
* deliverable
* meaningful timing or at least actionable status

**To surface prominently**
Usually need:

* commitment likely exists
* owner or likely responsible party
* enough clarity to be useful to the user

#### 4. Clarification decision routes

**Clarify now**
Use when:

* user value is high
* a single missing field blocks usefulness
* the ambiguity is unlikely to self-resolve
* the item is important enough to justify interruption

**Observe silently**
Use when:

* the ambiguity is likely to resolve in a near-term reply
* the candidate is medium confidence
* interruption would create more burden than value

**Suppress**
Use when:

* existence is too weak
* ambiguity is too broad
* the item is mostly informational
* any clarification would feel arbitrary or annoying

#### 5. Silent observation windows

The system should sometimes wait before asking.

MVP observation windows:

* short-lived conversational ambiguity in Slack: wait briefly
* email reply chains with likely near-term clarification: wait until next reply or bounded time window
* meeting-derived items: often wait for cross-signal confirmation before asking

This is directly aligned with the brief’s emphasis on silent observation windows and “when to wait vs when to ask.” 

#### 6. Owner clarification rules

Clarify owner when:

* commitment likely exists
* ownership ambiguity changes usefulness materially
* the system cannot safely infer one responsible party

Do not clarify owner when:

* the likely owner is already strong enough for observation
* the ambiguity is likely to resolve naturally in the next signal
* the commitment is too weak to justify interruption

#### 7. Timing clarification rules

Clarify timing when:

* the commitment is real and meaningful
* timing matters to the user
* the timing is externally relevant or tied to delivery risk

Do not clarify timing when:

* vague timing is acceptable for now
* the item is early-stage internal work
* asking would create more friction than value

#### 8. Deliverable clarification rules

Clarify deliverable when:

* the action exists but “it / this / that” cannot be resolved from bounded context
* multiple plausible deliverables exist
* surfacing would otherwise mislead

#### 9. Existence clarification rules

Usually do **not** clarify low-confidence existence directly.
Prefer:

* observe
* wait for follow-up evidence
* suppress

Asking “Did you mean this as a commitment?” too often will likely feel bad in product.

#### 10. Clarification output contract

Each candidate should carry:

* clarification_needed: true / false
* clarification_reason[]
* clarification_priority
* recommended_action: ask_now / observe / suppress
* clarification_prompt_template_id or null

### Examples

#### Example 1 — multi-recipient email

“Can one of you handle this?”

Result:

* commitment likely exists
* owner unclear
* recommend observe or clarify depending on importance
* do not auto-assign from recipient list alone

#### Example 2 — vague timing

“I’ll send it soon.”

Result:

* likely commitment
* vague timing
* create candidate
* do not necessarily clarify immediately

#### Example 3 — unclear deliverable

“Yes, I’ll handle that.”

With multiple unresolved referents in prior context.

Result:

* likely commitment
* deliverable unclear
* observe briefly or clarify if needed for usefulness

#### Example 4 — weak existence

“We should probably revisit pricing at some point.”

Result:

* likely suppress or observe only
* not a strong clarification candidate

### Open questions / future extension

* Should users be able to set their own clarification aggressiveness?
* Should external-client ambiguity trigger earlier clarification than internal-team ambiguity?
* How long should observation windows be by source?
* When should the system bundle multiple clarifications into one review moment?

### Implications for engineering / UX

* Engineering needs explicit unresolved states and clarification reasons in the schema.
* UX should support quiet waiting, not only asking.
* Clarification surfaces should feel lightweight and sparse.
* Copy should be tentative and confidence-sensitive, not interrogative or robotic.

---
