# Rippled Briefing — Prompt System and App Architecture Improvements for Commitment Signals

## Purpose

This briefing outlines the recommended changes to Rippled’s prompt system and application architecture to improve the detection, classification, extraction, scoring, and lifecycle handling of commitment-related signals.

The goal is not just to improve prompt quality in isolation, but to redesign the detection pipeline so it is more reliable across channels, easier to evaluate, less prone to hallucination, and better aligned with the product behavior Rippled appears to need.

This document is written so Claude can evaluate the proposed changes against the current implementation and identify what should change in prompts, data models, and system flow.

---

## Executive Summary

Rippled’s current prompt set is directionally strong, but it appears to combine too many responsibilities into too few prompts.

At the moment, the system is trying to do several jobs at once:
- detect whether a commitment exists
- infer what kind of signal it is
- extract structured fields
- determine urgency or importance
- infer external vs internal relevance
- decide whether the structure is complete
- review model quality after the fact

That creates predictable problems:
- false negatives when one field is ambiguous
- inconsistent outputs between real-time and seed flows
- difficulty separating requests from commitments
- difficulty handling Slack-style implicit phrasing
- limited diagnostics when quality issues arise
- pressure on prompts to make product decisions that should live in architecture or scoring logic

The recommendation is to move to a layered system with:
1. **candidate detection**
2. **signal classification**
3. **structured extraction**
4. **completion / closure detection**
5. **downstream scoring and surfacing**

In addition, Rippled should introduce:
- a unified commitment ontology
- source-specific overlays for email, Slack, and meetings
- signal-type instructions per class of signal
- evidence spans for all extracted items
- field-level confidence rather than one confidence score only
- clarification handling for structurally incomplete but still useful commitments

---

## Current Prompt Set Reviewed

The current setup includes:
- `model_detection.py (ongoing-v4)` — real-time single-commitment extraction
- `seed_detector.py (seed-v3)` — bulk extraction over email bodies
- `llm_judge.py` — weekly quality review
- `eval/runner.py (seed-v1)` — regression harness

### Main concern

The current prompts do not appear to share a fully unified ontology.

For example:
- the real-time prompt extracts owner, deliverable, counterparty, deadline, user relationship, and structure completeness
- the seed prompt extracts trigger phrase, who committed, directed at, urgency, commitment type, title, and externality

This means Rippled is effectively running different conceptual models in different parts of the pipeline.

That will make it harder to:
- compare seed vs ongoing detections
- deduplicate signals
- run meaningful evaluations
- maintain consistent UI behavior
- diagnose failure modes across the system

---

## Root Cause Analysis

## 1. Detection and extraction are too tightly coupled

The real-time detector requires a high degree of structure too early.

This creates a failure pattern:
- a likely commitment exists
- one field is vague or missing
- the model either rejects the item or hallucinates structure

For Rippled, that is the wrong tradeoff.

The better behavior is:
- preserve likely commitments
- mark uncertain or missing fields explicitly
- allow clarification or downstream enrichment later

## 2. Product logic is embedded in extraction prompts

Some fields currently requested from the LLM, such as urgency, may be better determined downstream.

Urgency usually depends on more than wording alone. It often depends on:
- internal vs external context
- explicit due dates
- lateness vs freshness
- business consequence
- source type
- user role and relationship

This should mostly live in application logic or a later scoring layer rather than the primary extraction prompt.

## 3. Adjacent signal types are not sufficiently separated

The prompts currently blur the boundaries between:
- commitments
- requests
- delegations
- follow-ups
- schedule actions
- completion evidence
- status updates
- speculative ideas

That ambiguity will produce inconsistent detections and lifecycle behavior.

## 4. Source-specific behavior is under-modeled

The same phrase behaves differently by channel.

Examples:
- “On it” in Slack can be a valid commitment if replying to a task
- “On it” in an email may be too ambiguous unless message-local context is clear
- “Let’s meet Tuesday” may be a scheduling action rather than a deliverable commitment
- “Sent above” is more likely completion evidence than a new commitment

The system needs source-aware instructions and source-aware architecture.

---

## Recommended Target Architecture

Rippled should move from a monolithic extraction mindset to a staged signal pipeline.

## Proposed pipeline

### Stage 1 — Candidate Detection

Question answered:
**Is there likely a future-oriented obligation or commitment-like signal here?**

Design goal:
- high recall
- preserve ambiguity
- do not force full structure

Expected output:
- candidate yes/no
- evidence span
- coarse confidence
- maybe a rough candidate type guess

### Stage 2 — Signal Classification

Question answered:
**What kind of signal is this?**

Recommended classes:
- self_commitment
- delegated_action
- requested_action
- follow_up_intent
- schedule_action
- completion_evidence
- status_update_only
- non_commitment

Design goal:
- separate semantically adjacent patterns
- prevent downstream confusion
- define different lifecycle rules per class

### Stage 3 — Structured Extraction

Question answered:
**What structured commitment object can be extracted from this signal?**

Recommended extracted fields:
- owner
- deliverable / action
- counterparty
- deadline
- user relationship
- source type
- signal type
- evidence text
- explicitness level
- field-level confidence
- clarification needed
- clarification reasons

Design goal:
- structured, explainable outputs
- incomplete but useful candidates retained
- no forced hallucinated fields

### Stage 4 — Completion / Closure Detection

Question answered:
**Does this signal indicate a previously detected commitment has been completed, delivered, updated, or closed?**

Design goal:
- reduce duplicate commitments
- track lifecycle state changes
- separate new obligations from completion evidence

This stage should likely be independent from the primary commitment detector.

### Stage 5 — Scoring, Prioritization, and Surfacing

Question answered:
**How important is this signal, and how should it be surfaced to the user?**

This should be mostly deterministic or hybrid, using extracted fields plus app logic.

Inputs may include:
- explicit due date
- external vs internal
- lateness / stale age
- user relationship
- channel
- completion status
- business consequence indicators
- confidence threshold

Design goal:
- keep the LLM focused on semantic interpretation
- keep product policy in app logic where possible

---

## Recommended Commitment Ontology

Rippled needs a single ontology shared across all prompts, evaluation, and product logic.

## Core concepts

### Commitment
A future-oriented obligation, deliverable, or outcome that someone has taken ownership of or has been clearly assigned.

### Request
A request for action that does not yet imply accepted ownership.

### Delegation
An action explicitly assigned to someone else.

### Follow-up Intent
A commitment-like promise to revisit, respond, check, or circle back.

### Schedule Action
An agreed or proposed meeting, call, or time-bound coordination action.

### Completion Evidence
A message indicating delivery, completion, closure, or fulfillment of a previously existing commitment.

### Status Update
A progress or informational statement without a new forward-looking obligation.

### Non-Commitment
Social niceties, sign-offs, filler, speculation, hypotheticals without ownership, and other non-actionable content.

---

## Signal-Type Instruction Framework

A major recommendation is to add instructions per signal type rather than relying only on a single generic definition.

## 1. Explicit Commitment

Examples:
- “I’ll send the draft tomorrow.”
- “We will take care of this.”
- “I can handle the introduction.”

Guidance:
- usually high-confidence
- owner is often explicit
- deliverable usually extractable
- deadline may be explicit or inferable

## 2. Implicit Commitment

Examples:
- “On it.”
- “Leave it with me.”
- “Consider it done.”
- “I’ll look into it.”

Guidance:
- valid commitment candidate when nearby context supplies the object
- must use thread or message context
- do not reject just because the direct phrase is elliptical

## 3. Follow-Up Intent

Examples:
- “Need to follow up.”
- “I’ll circle back.”
- “Will follow up with finance.”
- “Let me get back to you.”

Guidance:
- should usually surface as a candidate
- often structurally incomplete
- good candidate for clarification or silent monitoring

## 4. Delegated / Assigned Action

Examples:
- “Can you send the revised version?”
- “Please handle this by Friday.”
- “John to review before EOD.”

Guidance:
- separate from self-commitments
- owner is the assignee, not the speaker
- may remain a request unless acceptance is explicit, depending on product rules

## 5. Schedule Action

Examples:
- “Let’s meet Tuesday.”
- “I’ll call you tomorrow.”
- “Can we review this Friday afternoon?”

Guidance:
- treat distinctly from deliverable promises
- may still matter operationally, but lifecycle differs

## 6. Completion Evidence

Examples:
- “Done.”
- “Sent above.”
- “Uploaded the file.”
- “Shared the proposal.”

Guidance:
- should first be considered as evidence of fulfillment
- should not create a new commitment unless a fresh future obligation is also present

## 7. Non-Commitment / Weak Intent

Examples:
- “We should probably revisit this.”
- “Maybe we can do that next week.”
- “Would be good to follow up at some point.”

Guidance:
- not a commitment unless ownership is taken or assigned
- may become relevant in later planning features, but should not be treated as a commitment by default

---

## Source-Specific Instruction Overlays

Rippled should keep a shared base prompt and add compact source-specific overlays.

## Email Overlay

Add rules such as:
- prioritize the active message over quoted history
- ignore signatures, disclaimers, and pleasantries
- distinguish sender commitment from recipient request
- treat external-party commitments with extra importance downstream
- “I’ll get back to you” and “I’ll send this over” are strong candidates
- forwarded or quoted commitments should not be treated as fresh commitments unless newly endorsed or repeated

## Slack Overlay

Add rules such as:
- thread context is often necessary to interpret short phrases
- “on it”, “will do”, and “I got this” can be valid when tied to a concrete ask nearby
- emoji-only responses are never commitments
- replies may inherit the task object from a parent message
- owner inference may depend on thread position and mentions

## Meeting Transcript Overlay

Add rules such as:
- tolerate paraphrased and indirect phrasing
- separate discussion from assigned action
- “next step is” is not enough unless ownership is present or implied strongly
- action items often appear as shorthand at the end of meetings
- transcript quality/noise should reduce confidence rather than block extraction outright

---

## Prompt Redesign Recommendations

## A. Replace the current real-time prompt with a two-part flow

### Current problem
The real-time prompt attempts detection and extraction in one shot and forces structural completeness too early.

### Recommended replacement
Split into:
1. **real-time candidate detector**
2. **real-time extractor**

The detector should answer:
- is this likely a commitment-like signal?
- what is the evidence span?
- what coarse type does it resemble?

The extractor should answer:
- what structured fields can be extracted?
- which are explicit vs inferred?
- what needs clarification?

### Recommended output shape

```json
{
  "is_commitment_candidate": true,
  "signal_type": "follow_up_intent",
  "confidence": 0.84,
  "evidence_text": "I'll follow up with finance tomorrow",
  "owner": {"value": "Kevin", "confidence": 0.96, "source": "explicit"},
  "deliverable": {"value": "follow up with finance", "confidence": 0.91, "source": "explicit"},
  "counterparty": {"value": "finance", "confidence": 0.88, "source": "explicit"},
  "deadline": {"value": "tomorrow", "normalized": null, "confidence": 0.62, "source": "explicit_relative"},
  "user_relationship": "mine",
  "needs_clarification": true,
  "clarification_reasons": ["deadline_relative"]
}
```

### Key instruction change
Do not reject a likely commitment because one or more fields are missing.

Instead:
- preserve the candidate
- mark missing fields as null
- add clarification reasons where relevant

---

## B. Redesign the seed detector to match the same schema

### Current problem
The seed prompt uses different fields and mixes in urgency and title generation.

### Recommended change
Make the seed pass use the same core schema as the real-time flow, with an array of results.

### What to remove from primary extraction
Remove from the extraction prompt if possible:
- urgency
- title

These are product outputs, not first-order extraction truths.

### What to add
Add:
- evidence_text
- signal_type
- explicitness
- field-level confidence
- clarification state
- source-specific handling

### Why
The seed pass should produce the same conceptual object as the live flow so that Rippled can:
- deduplicate reliably
- compare outputs consistently
- train evals on one ontology
- make UI behavior predictable

---

## C. Expand the judge prompt into a diagnostic evaluator

### Current problem
The current judge prompt asks for misses, false positives, a score, and one suggestion.

That is not enough to identify systemic failure modes.

### Recommended change
Have the judge classify failures into categories.

Example:

```json
{
  "missed": [
    {
      "text": "I'll circle back next week",
      "reason": "implicit_follow_up_missed"
    }
  ],
  "false_positives": [
    {
      "text": "Can you send this?",
      "reason": "request_misclassified_as_commitment"
    }
  ],
  "schema_errors": [
    {
      "field": "owner",
      "issue": "incorrect_owner_resolution"
    }
  ],
  "quality_rating": 3,
  "primary_failure_mode": "owner_resolution",
  "prompt_suggestion": "Differentiate speaker requests from accepted ownership.",
  "recommended_test_case": "Slack thread with implicit task acceptance"
}
```

### Recommended failure categories
- implicit_commitment_missed
- follow_up_missed
- request_vs_commitment_confusion
- delegation_confusion
- completion_vs_new_commitment_confusion
- quoted_text_contamination
- owner_resolution_error
- deadline_resolution_error
- counterparty_resolution_error
- non_actionable_phrase_false_positive

This makes evaluation much more actionable.

---

## D. Add a dedicated completion prompt

Rippled likely needs a separate completion-detection prompt.

Purpose:
- determine whether a new message indicates fulfillment of an existing commitment
- prevent duplicate new commitments from being created
- support delivered vs closed states

Example signals:
- “Done”
- “Sent”
- “Uploaded the final version”
- “Shared above”
- “This has been taken care of”

This stage should likely work against:
- a candidate signal
- recent commitments in context
- thread or conversation state

---

## Data Model Changes Recommended

The prompts will improve quality, but app architecture also needs a revised object model.

## Recommended canonical signal object

```json
{
  "signal_id": "...",
  "source_type": "email|slack|meeting|other",
  "signal_type": "self_commitment|delegated_action|requested_action|follow_up_intent|schedule_action|completion_evidence|status_update_only|non_commitment",
  "evidence_text": "...",
  "confidence": 0.0,
  "owner": {
    "value": null,
    "confidence": 0.0,
    "source": "explicit|inferred|unknown"
  },
  "deliverable": {
    "value": null,
    "confidence": 0.0,
    "source": "explicit|inferred|unknown"
  },
  "counterparty": {
    "value": null,
    "confidence": 0.0,
    "source": "explicit|inferred|unknown"
  },
  "deadline": {
    "value": null,
    "normalized": null,
    "confidence": 0.0,
    "source": "explicit|relative|inferred|unknown"
  },
  "explicitness": "explicit|implicit|follow_up|delegated|tentative",
  "user_relationship": "mine|contributing|watching",
  "needs_clarification": false,
  "clarification_reasons": [],
  "structure_status": "complete|partial|minimal",
  "lifecycle_state": "open|delivered|closed|dismissed",
  "linked_commitment_id": null
}
```

## Why this matters
This lets Rippled separate:
- semantic extraction
- user-facing confidence
- lifecycle state
- clarification handling
- downstream ranking

---

## Architecture Implications Beyond Prompts

## 1. Store evidence spans

Every extracted signal should preserve the exact text span that triggered detection.

Benefits:
- better debugging
- better UI explainability
- easier review workflows
- stronger evaluation
- easier deduplication

## 2. Support field-level confidence

A single top-level confidence score is not enough.

Rippled should store confidence for:
- owner
- deliverable
- counterparty
- deadline

This allows more intelligent UI and downstream rules.

## 3. Introduce clarification workflows

Some signals should not be dropped just because they are incomplete.

Examples:
- “I’ll follow up” with no clear topic
- “On it” in a Slack thread
- “We should get this over the line tomorrow” with vague ownership

A useful architecture should allow:
- silent observation
- later enrichment from more context
- optional user clarification
- confidence-based surfacing

## 4. Separate extraction from prioritization

Prioritization should not be decided primarily by the extraction prompt.

Instead, use app logic and weighted scoring rules based on extracted fields and business rules.

## 5. Add lifecycle linking

A signal may:
- create a commitment
- update a commitment
- complete a commitment
- close a commitment
- dismiss a commitment

This is a lifecycle problem, not only an extraction problem.

---

## Evaluation Changes Recommended

Rippled’s eval layer should test more than whether a commitment was found.

## Recommended metrics

### Detection metrics
- candidate recall
- candidate precision

### Field extraction metrics
- owner accuracy
- deliverable accuracy
- counterparty accuracy
- deadline accuracy

### Classification metrics
- signal type accuracy
- explicit vs implicit accuracy
- completion vs new commitment accuracy

### Operational metrics
- incomplete-but-useful candidate rate
- false dismissal rate
- quoted-text contamination rate
- source-specific performance by channel
- external vs internal performance

## Recommended slices
- email vs Slack vs transcript
- explicit vs implicit commitments
- internal vs external
- follow-up signals
- delegated actions
- schedule actions
- completion evidence
- structurally incomplete signals

---

## Recommended Implementation Sequence

## Phase 1 — Unify the ontology

Deliverables:
- define shared signal taxonomy
- define canonical signal object
- update eval language to match taxonomy

## Phase 2 — Split detection from extraction

Deliverables:
- candidate detector prompt
- structured extraction prompt
- shared schemas across live and seed modes

## Phase 3 — Add source overlays

Deliverables:
- email overlay
- Slack overlay
- meeting transcript overlay

## Phase 4 — Add completion detection

Deliverables:
- completion prompt
- lifecycle-linking logic
- delivered vs closed handling

## Phase 5 — Move prioritization out of prompts

Deliverables:
- downstream scoring rules
- surfacing thresholds
- clarification logic

## Phase 6 — Upgrade evaluation

Deliverables:
- diagnostic judge prompt
- failure taxonomy
- expanded regression cases

---

## Concrete Guidance for Claude’s Review

Ask Claude to evaluate the current Rippled setup against the following questions:

### Ontology and schema
- Are real-time and seed flows using the same conceptual object?
- Where are the schema mismatches?
- Which fields are extraction truths versus product-level enrichments?

### Prompt responsibilities
- Which prompts are doing too many jobs at once?
- What should be split into separate stages?
- Which current instructions should move into downstream logic instead of LLM prompts?

### Signal-type handling
- Which signal types are currently under-modeled?
- Where do requests, delegations, follow-ups, and completions get confused?

### Source handling
- How much channel-specific logic exists today?
- Where does Slack need thread-aware treatment?
- How are quoted email histories handled?

### Lifecycle and architecture
- How are commitment creation, updates, completion, and closure represented today?
- What architecture changes are needed to prevent duplicate commitments?
- What object changes are needed to preserve incomplete-but-useful candidates?

### Evaluation and observability
- Can the current judge prompt explain failure modes clearly enough?
- Are evidence spans stored today?
- Are field-level confidences captured?

---

## Recommended Decisions to Make Before Refactoring

Before implementation begins, Rippled should explicitly decide:

1. **Are delegated asks first-class commitments, or only commitments once accepted?**
2. **Are schedule actions treated as commitments, or as a separate signal family?**
3. **How should incomplete but high-probability commitments be surfaced?**
4. **What minimum structure is required to create a user-visible signal?**
5. **What confidence thresholds differ by signal type and channel?**
6. **What is the lifecycle distinction between delivered and closed?**
7. **How should completion evidence link to prior commitments?**

These decisions will shape both prompt design and data model design.

---

## Bottom Line

The main recommendation is not just “rewrite the prompts.”

It is to redesign Rippled’s commitment-signal pipeline so prompts do the semantic work they are good at, while the app architecture handles classification persistence, clarification, lifecycle, and prioritization more deliberately.

### In practical terms
Rippled should:
- unify its commitment ontology
- separate detection from extraction
- add instructions per signal type
- add source-specific overlays
- capture evidence spans and field-level confidence
- create a separate completion / closure flow
- move urgency and prioritization mostly out of extraction prompts
- upgrade evaluation so it diagnoses failure modes, not just quality scores

That combination should make the system more accurate, more explainable, easier to iterate, and better aligned with the product Rippled appears to be building.

---

## Suggested Next Artifact

After Claude reviews this against the current codebase, the next recommended artifact is:

**“Rippled Commitment Signal v2 Spec”**

That spec should include:
- canonical taxonomy
- JSON schemas
- per-stage prompt contracts
- channel overlays
- lifecycle model
- scoring model
- eval design

