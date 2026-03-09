---
tags: [rippled, clarification, ambiguity, engineering]
brief: "09 — Clarification"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# Clarification Brief

## Purpose

Define how Rippled handles incomplete, ambiguous, or low-confidence commitments so the system reduces cognitive load without becoming intrusive, noisy, or overly certain.

This brief governs:

- when Rippled should wait for more evidence
- when Rippled should suggest clarification
- what kinds of ambiguity matter
- how clarification should be surfaced
- how clarification should be worded
- what Rippled should suggest by default without pretending certainty

Clarification is not a generic “fill in missing fields” workflow. It is a trust-preserving mechanism that helps turn messy real-world communication into usable commitments with minimal user burden.

---

## Why this matters

A commitment engine becomes annoying fast if it asks too many follow-up questions.

But it also becomes unreliable if it quietly stores half-formed commitments that never become actionable.

Rippled must balance both risks:

- **asking too often creates cognitive fatigue**
- **asking too little allows forgotten commitments to accumulate invisibly**

The goal is not to clarify everything.  
The goal is to clarify only when doing so meaningfully reduces future cognitive load, missed expectations, or unresolved accountability.

---

## Product role of clarification

Clarification exists to answer one or more of these questions:

- Is this actually a commitment?
- Who is responsible?
- When is it expected?
- What exactly is meant to be delivered or done?
- Has later communication already resolved the ambiguity?
- Is this important enough to surface now, or should Rippled wait?

Clarification should help Rippled move an item from:

- vague → usable
- uncertain → reviewable
- implied → explicit enough to support follow-through
- cognitively heavy → mentally offloaded

---

## Core principles

### 1. Clarify only when it reduces burden

Rippled should not clarify for completeness alone.  
It should clarify when the missing information is likely to create:

- future forgetting
- ownership confusion
- missed expectations
- uncertainty about whether something is still open

### 2. Observe before interrupting

By default, Rippled should prefer a silent observation window before surfacing clarification.

In real work, ambiguity often resolves naturally:

- someone later volunteers ownership
- a due date gets mentioned in follow-up
- a deliverable becomes obvious in a thread
- completion happens before clarification is needed

Clarification should often be a second move, not the first.

### 3. Suggest, do not assert

Rippled should never behave as though its interpretation is hard truth.

It may suggest:

- likely next step
- likely owner
- likely due date
- likely meaning

But it must preserve ambiguity and present suggestions accordingly.

### 4. External commitments deserve earlier clarification

Client-facing or external commitments carry greater expectation weight and should generally:

- surface faster
- be clarified sooner
- use stricter confidence thresholds
- escalate unresolved ambiguity earlier

### 5. “We” is not resolved ownership

Collective wording such as:

- we
- the team
- someone
- us

must not be treated as a resolved owner by default.

Rippled may suggest a likely owner later, but should preserve unresolved ownership until evidence supports otherwise.

### 6. Clarification should be compact

Clarification must never become a massive cleanup queue.

It should appear as:

- a small, high-value bundle
- a separate review surface
- quick-to-clear items
- “good catch” moments rather than admin work

---

## What counts as a clarification-worthy issue

Rippled should detect and classify ambiguity into machine-readable issue types.

## Issue categories

### 1. Uncertain commitment

Used when it is not sufficiently clear whether a statement represents a real commitment versus:

- brainstorming
- suggestion
- hypothetical
- commentary
- discussion of something already done

Examples:

- “Maybe we should update that.”
- “It might make sense to revisit pricing.”
- “We could send something next week.”

This does not always need user clarification. It may simply remain observed until more evidence appears.

---

### 2. Missing owner

Used when a commitment appears real, but no responsible person is identifiable.

Examples:

- “We’ll send the deck tomorrow.”
- “Someone should get that invoice out.”
- “We need to follow up on this.”

This is a high-value clarification target because ownership confusion creates cognitive load quickly.

---

### 3. Vague owner

Used when an owner reference exists but is collective or non-specific.

Examples:

- “We’ll handle that.”
- “The team will pick it up.”
- “One of us will send it.”

This should remain unresolved by default.

---

### 4. Missing deadline

Used when a commitment appears actionable, but no time expectation is stated.

Examples:

- “I’ll send the proposal.”
- “I’ll take a look.”
- “We’ll follow up.”

Not all missing deadlines require immediate clarification. Some commitments are still actionable without an explicit due date, especially for a short observation window.

---

### 5. Vague deadline

Used when timing exists but is not concrete enough to normalize confidently.

Examples:

- “soon”
- “later”
- “this week”
- “end of month”
- “after the holidays”

These may be usable as weak timing cues, but should not be treated as precise deadlines without confidence.

---

### 6. Unclear deliverable or action

Used when a commitment exists, but what will actually be done is underspecified.

Examples:

- “I’ll handle it.”
- “I’ll sort that out.”
- “We’ll take care of it.”

These often benefit from suggested next-step interpretation, but may not require user clarification immediately if later evidence is likely.

---

### 7. Unclear target

Used when the action is somewhat clear but the object, recipient, client, project, or artifact is uncertain.

Examples:

- “I’ll send that over.”
- “We’ll update the doc.”
- “I’ll forward it.”

If Rippled cannot confidently link the action to a target entity, it should preserve the ambiguity.

---

### 8. Conflicting signals

Used when later communication appears to change or contradict earlier interpretation.

Examples:

- meeting: “I’ll send it Friday”
- email later: “We may need to move this to end of month”

Conflicting signals should usually reduce certainty and may trigger clarification or deferred review.

---

### 9. Completion ambiguity

Used when Rippled suspects the commitment may have been delivered or closed, but evidence is incomplete or mixed.

Examples:

- “sent”
- attachment present, but unclear if it fulfills the commitment
- internal delivery happened, but client delivery may still be pending

This is especially important for internal handoff chains.

---

## Which issues are critical vs non-critical

Rippled should distinguish between issues that block actionability and those that merely reduce confidence.

### Critical issues

These usually justify clarification sooner if the item is important enough.

- uncertain commitment
- missing owner
- vague owner
- severe conflict between signals

### Usually non-critical issues

These may still allow the item to be tracked while being observed.

- missing deadline
- vague deadline
- unclear target
- mildly unclear deliverable
- weak completion ambiguity

### Context-sensitive issues

These depend on internal vs external context.

- missing deadline on external/client-facing promise may become critical sooner
- unclear target in client-facing delivery may become critical sooner
- vague owner in internal founder-assistant dynamic may allow likely-owner suggestion, but still should not be treated as resolved ownership

---

## Silent observation policy

Before surfacing a clarification, Rippled should usually wait for additional signals during a source- and context-sensitive observation window.

These should use **working hours**, not simple clock time.

## Default MVP observation windows

### Slack

- internal: up to 2 working hours
- external/client-facing Slack is not assumed for MVP unless explicitly supported later

### Email

- internal: 1 working day
- external: 2 to 3 working days

### Meetings

- internal: 1 to 2 working days
- external: 2 to 3 working days

These are provisional defaults and should be configurable later.

---

## When Rippled should skip or shorten observation

Rippled should clarify sooner when:

- the commitment is external/client-facing
- a concrete due date is near
- the commitment appears consequential
- the ambiguity is ownership-related
- conflicting signals create real risk of missed expectation
- the item is likely to be surfaced in the Main tab soon

Rippled should wait longer when:

- the item is internal
- it appears low consequence
- follow-up messages are likely to resolve ambiguity naturally
- the signal is weak or partially implicit
- the user would be interrupted for low-value clarification

---

## Clarification decision framework

After detection and scoring, Rippled should decide among four behaviors:

### 1. Do nothing yet

Used when:

- ambiguity exists
- but likely future signals will resolve it
- and interruption would add more burden than value

Result:

- keep observing
- retain suggested values internally
- do not surface yet

---

### 2. Surface internally only

Used when:

- Rippled has a useful interpretation
- but confidence is not high enough for broader surfacing
- or clarification is not worth prompting yet

Result:

- item appears in Clarifications view or internal shortlist logic
- no push-style interruption

---

### 3. Suggest clarification in review surface

Used when:

- ambiguity materially affects actionability
- enough observation time has passed
- the item is worth resolving
- a compact clarification bundle would likely help

Result:

- appears in Clarifications view
- may include suggested values
- user can confirm, edit, ignore, or leave unresolved

---

### 4. Escalate for timely review

Used sparingly when:

- external expectation risk is meaningful
- a due date is close or drifting
- ownership conflict persists
- a client-facing commitment may be missed

Result:

- still phrased cautiously
- bundled if possible
- reserved for high-value cases only

---

## Suggested values

Rippled should generate suggested values by default when helpful, but preserve them as suggestions rather than resolved facts.

## Suggested-value priority order

Safest to riskiest:

1. likely next step
2. likely owner
3. likely due date
4. likely completion interpretation

This order reflects current product preference.

---

## Guidance by suggestion type

### Likely next step

Usually the safest suggestion because it helps the user orient quickly without over-asserting.

Example:

- “Likely next step: send revised proposal to client”

### Likely owner

Useful, but should be conservative.  
Allowed even when `resolved_owner` remains null.

Example:

- “Likely owner: account manager who replied ‘I’ll handle it’ in follow-up thread”

### Likely due date

Should only be suggested when there is a meaningful cue.  
Weak phrases should remain clearly tentative.

Example:

- “Possible timing: by end of week based on follow-up email”

### Likely completion

Useful for completion review, but should be especially cautious when proof is indirect.

Example:

- “Possibly delivered via outbound email with matching attachment”

---

## Clarification output model

For any item in clarification flow, Rippled should produce a structured clarification object.

## Clarification object fields

- `clarification_id`
- `commitment_id`
- `issue_types[]`
- `issue_severity`
- `why_this_matters`
- `observation_window_status`
- `suggested_values`
- `supporting_evidence`
- `supporting_signals`
- `suggested_clarification_prompt`
- `surface_recommendation`
- `created_at`
- `updated_at`

## Example structure

```json
{
  "clarification_id": "clar_123",
  "commitment_id": "com_456",
  "issue_types": ["missing_owner", "vague_deadline"],
  "issue_severity": "high",
  "why_this_matters": "This appears to be an external client-facing promise with no clearly assigned owner and only a vague timing reference.",
  "observation_window_status": "expired",
  "suggested_values": {
    "likely_next_step": "Send revised pricing to client",
    "likely_owner": {
      "value": "Kevin",
      "confidence": 0.58,
      "reason": "Kevin made the original promise and later referenced preparing pricing."
    },
    "likely_due_date": {
      "value": "end of week",
      "confidence": 0.42,
      "reason": "Follow-up email referenced 'later this week'."
    }
  },
  "supporting_evidence": [
    "Meeting segment 12",
    "Email thread reply 3"
  ],
  "suggested_clarification_prompt": "This looks like a client-facing follow-up on pricing, but I’m not fully sure who owns it or when it’s due. Is Kevin the owner, and is this meant for later this week?",
  "surface_recommendation": "clarifications_view"
}
```

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 3. Commitment Domain Model Brief]] | Where ambiguity fields and suggested values are defined |
| [[Rippled - 4. Source Model Brief]] | Source-aware observation windows that delay clarification |
| [[Rippled - 5. Commitment Lifecycle Brief]] | The `needs_clarification` state this brief governs |
| [[Rippled - 6. Surfacing & Prioritization Brief]] | The Clarifications surface and when items route to it |
| [[Rippled - 8. Commitment Detection Brief]] | Detection-time ambiguity flags that trigger this workflow |
| [[Rippled - 10. Completion Detection Brief]] | Completion ambiguity cases handled here |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |