
---
tags: [rippled, mvp, scope, product]
brief: "07 — MVP Scope"
index: "[[Index - Rippled Platform & MVP Brief]]"
---

# MVP Scope Brief

## Purpose

Define what Rippled’s MVP includes, excludes, and prioritizes so product and engineering can build toward a narrow, useful first version without drifting into a broad task manager, generic inbox assistant, or meeting-notes product.

This brief exists to reduce ambiguity around scope, sequencing, and success criteria for the first meaningful version of Rippled.

---

## Why This Matters

Rippled’s value does not come from ingesting every possible signal or automating every workflow from day one.

Its value comes from doing one job well:

**help the user forget fewer commitments and reduce cognitive load without creating another system they have to constantly manage.**

The MVP should therefore optimize for:

- trustworthy commitment capture
- useful surfacing
- low interruption
- traceability
- enough structure to support future refinement

The MVP should not optimize for:

- exhaustive coverage of all work activity
- polished workflow management
- complex team collaboration
- large-scale analytics
- broad enterprise readiness

---

## MVP Product Goal

The MVP should prove that Rippled can:

1. ingest communication signals from a limited set of core sources
2. detect likely commitments with enough quality to be useful
3. distinguish between bigger externally consequential promises and smaller cognitively burdensome commitments
4. preserve ambiguity instead of pretending certainty
5. surface a compact set of useful suggestions that help the user remember, clarify, and close loops

If the MVP works, a user should feel:

- “I forgot fewer things.”
- “I had fewer moments of realizing too late that I had promised something.”
- “I didn’t have to actively maintain another task system for this to help.”
- “The suggestions felt useful more often than annoying.”

---

## Target User for MVP

The MVP is optimized for a **single primary user** operating as an overloaded founder, operator, account lead, or service-business owner whose commitments are spread across:

- meetings
- Slack
- email

The first version is a **personal assistant layer for one user**, not a full multi-user team operating system.

Other people may appear in signals, but the system’s point of view is centered on helping one primary user track and manage commitments relevant to them.

---

## MVP Thesis

The MVP should embody these product truths:

- many small commitments create as much or more cognitive burden than a few large deadlines
- externally visible promises deserve higher priority than internal ones
- commitments should be captured more broadly than they are surfaced
- the system should infer carefully but never claim certainty it does not have
- the user should receive sparse, high-value prompts rather than constant interruptions
- later signals should be able to clarify, update, deliver, reopen, or close a commitment
- “we” should remain unresolved ownership by default

---

## In Scope for MVP

## 1. Source coverage

The MVP includes three first-class source families:

### Meetings

Used as:

- source of commitments
- source of clarification
- source of progress/completion evidence

Supported meeting inputs for MVP:

- transcript text
- speaker labels where available
- timestamps
- meeting metadata
- participant metadata
- provider summary/action items if available
- raw payload retention

### Slack

Used as:

- source of commitments
- source of clarification
- source of progress/completion evidence

Supported Slack inputs for MVP:

- channels
- private channels
- DMs
- thread structure
- timestamps
- sender identity
- message edits
- links/files metadata
- permalink/reference storage

### Email

Used as:

- source of commitments
- source of clarification
- source of progress/completion evidence

Supported email inputs for MVP:

- thread structure
- sender/recipient metadata
- internal vs external classification
- timestamps
- subject
- body
- outbound vs inbound direction
- attachment metadata
- message/thread references

For email, quoted prior thread content should be excluded from fresh commitment extraction where possible to reduce duplicate detection.

---

## 2. Commitment intelligence pipeline

The MVP includes a working pipeline that can:

- ingest raw source payloads
- normalize them into a common internal model
- detect likely commitment signals
- create unified commitment candidates
- link multiple signals to one commitment
- identify ambiguity and missing fields
- assign confidence dimensions
- infer progress/delivery/completion signals
- update commitment state over time
- preserve evidence and history

The MVP should support:

- explicit commitments
- implicit commitments
- delegated commitments
- follow-up commitments
- unresolved next steps
- delivery/progress signals
- clarification signals

The MVP should not reduce communication into generic summaries only. It must produce structured commitment objects.

---

## 3. Unified commitment model

The MVP includes one unified commitment object that can be fed by multiple linked signals across meetings, Slack, and email.

A commitment may:

- originate in one source
- be clarified in another
- be delivered in another
- be reopened by a later signal

The commitment object should retain:

- linked source signals
- evidence references
- ambiguity markers
- confidence dimensions
- state history

The system should update commitment understanding over time without losing prior traceability.

---

## 4. Commitment classes

The MVP includes two surfaced commitment classes:

### Big promises

These should generally live in the **Main** view.

Classification priority for MVP:

1. external vs internal
2. explicit due date
3. business consequence

Typical examples:

- client-facing promises
- externally visible deadlines
- consequential deliverables
- commitments with stronger business impact

### Small commitments

These should generally live in the **Shortlist** view.

Typical examples:

- “I’ll look into that”
- “I’ll send that over”
- “I’ll follow up”
- “Let me check”
- practical internal follow-through that may be easy to forget but still creates cognitive burden

This classification is about **surface priority**, not truth or confidence. A small commitment can still be highly confident and important to cognitive load.

---

## 5. Missing information and clarification handling

The MVP includes structured detection of missing or weak fields such as:

- missing owner
- vague owner
- missing deadline
- vague deadline
- unclear deliverable
- unclear target
- uncertain commitment

The MVP should prefer **silent observation first** before prompting for clarification.

Default silent observation windows should be based on working hours and source/context:

- Slack: up to 2 working hours
- internal email: 1 working day
- external email: 2 to 3 working days
- internal meetings: 1 to 2 working days
- external meetings: 2 to 3 working days

These are default MVP rules and should be configurable later.

The MVP should generate suggested values where useful, ordered roughly by safety:

1. likely next step
2. likely owner
3. likely due date
4. likely completion interpretation

Clarification should be queued when genuinely needed, but the system should err on the side of being less intrusive.

---

## 6. Confidence model

The MVP includes structured confidence dimensions rather than one opaque score.

At minimum:

- commitment confidence
- owner confidence
- deadline confidence
- delivery/completion confidence
- overall actionability confidence

The system should use confidence to determine:

- what stays internal only
- what appears in Main
- what appears in Shortlist
- what enters Clarifications
- what stays suppressed

The system should not present low-confidence interpretations as established fact.

---

## 7. Lifecycle/state handling

The MVP includes a commitment lifecycle that distinguishes at least:

- active
- delivered
- closed

These states are **not strictly one-directional**.

A commitment may move:

- active → delivered
- delivered → active again
- delivered → closed
- closed → active again

Examples:

- delivered becomes active again when revision is requested
- closed becomes active again when a new linked signal suggests the obligation is still alive
- delivered may auto-close after a user-defined inactivity period

The MVP should support this reversibility in logic and storage.

---

## 8. Completion/delivery detection

The MVP includes completion/delivery inference from communication signals.

Examples of evidence that should count in MVP:

- outbound email matching a promised deliverable
- attachment sent that likely corresponds to the commitment
- Slack language such as “done,” “sent,” “handled,” “shipped”
- direct reply with promised information
- follow-up signals indicating work was completed

Completion confidence should vary by commitment type. For example:

- “send proposal” may have strong detectable proof
- “look into it” is harder to verify

The MVP should support this distinction.

---

## 9. Surfaced product views

The MVP includes three core surfaced areas:

### Main

For bigger, more consequential commitments, especially external/client-facing ones.

### Shortlist

For smaller commitments that still matter and contribute to cognitive load.

### Clarifications

A separate area for items that need user input or review because the system lacks enough certainty.

These should function more like distinct tabs or views than one long mixed feed.

The surfaced experience should remain compact and low-friction.

---

## 10. Suggestion-first language

The MVP includes suggestion-oriented system language.

Rippled should not speak as though it knows with certainty unless the evidence is exceptionally strong.

The system should default to phrasing such as:

- likely
- seems
- may need
- looks like
- suggested
- possible follow-up

This applies to:

- surfaced commitments
- clarification prompts
- delivery detection
- prioritization suggestions

Trust is more important than sounding definitive.

---

## 11. Internal vs external strictness

The MVP should apply stricter treatment to external/client-facing commitments than to internal ones.

External commitments should generally:

- surface faster
- be scored more strictly
- escalate sooner if unresolved
- carry more weight in Main view

Internal commitments may tolerate:

- more implied context
- more silent observation
- more gradual escalation
- more shortlist placement

---

## 12. Traceability and auditability

The MVP includes traceability by default.

The system should preserve:

- raw input payloads
- normalized signals
- linked evidence
- state history
- processing/version history

This is necessary so outputs can be inspected, replayed, and improved without turning the product into a black box.

---

## Out of Scope for MVP

The MVP should explicitly exclude the following unless needed as lightweight scaffolding.

## 1. Full task manager functionality

Not in scope:

- project plans
- kanban boards
- full task editing systems
- workload planning
- dependencies
- recurring tasks
- complex collaboration workflows

Rippled is not trying to replace Asana, ClickUp, or Linear.

## 2. Broad multi-user workspace behavior

Not in scope for MVP:

- robust team workspaces
- multi-user assignment workflows
- shared team dashboards
- admin/member permissions model
- workspace-wide policy systems

MVP is centered on one primary user.

---

## 3. Enterprise-grade permissions and governance

Not in scope:

- advanced RBAC
- legal/compliance workflow design
- enterprise tenant isolation complexity
- audit export systems
- extensive retention controls beyond practical defaults

---

## 4. Full native integration breadth

Not in scope:

- many source integrations at once
- broad provider matrix
- every meeting tool
- every email system
- every chat platform
- calendar in MVP core, though it may be planned next

Only enough integrations to prove the core model should be built.

---

## 5. Native bot/recorder infrastructure

Not in scope:

- building a native meeting recorder
- building a full meeting bot product
- replacing transcription vendors

Use existing upstream sources where possible.

---

## 6. Highly polished UI

Not in scope:

- polished design system
- advanced onboarding
- dense interaction design refinement
- detailed settings architecture
- extensive mobile-specific UX refinement

The MVP UI should be good enough to test usefulness and trust, not finalized.

---

## 7. Heavy automation and autonomous actions

Not in scope:

- auto-sending clarifications
- auto-replying to contacts
- auto-creating tasks everywhere
- auto-closing with no explanation
- aggressive workflow automation

The MVP should assist and suggest, not take over.

---

## 8. Advanced learning/personalization

Not in scope as a fully realized system:

- deep behavioral learning
- mature reinforcement tuning
- strong per-user adaptive thresholds
- relationship-specific heuristics at full depth

Some light configurability is acceptable, but rich adaptation comes later.

---

## 9. Large analytics/dashboarding layer

Not in scope:

- executive reporting
- org analytics
- trend dashboards
- deep metrics views
- management reporting suites

---

## 10. Full attachment/document understanding

Partially out of scope.

The MVP may use lightweight attachment/file metadata or simple matching where practical, but not a broad document-understanding platform.

For example:

- matching a proposal attachment to a “send proposal” commitment may be acceptable
- generalized file intelligence across all documents is not required for MVP

---

# Default MVP Rules

These rules should be treated as defaults unless later revised.

## Source rules

- meetings, Slack, and email are first-class sources
- Slack DMs and private channels are in scope
- Slack thread replies are first-class context
- email quoted prior text should be excluded from fresh extraction
- outbound email is strong completion evidence
- later signals update commitment understanding while preserving prior evidence

---

## Ownership rules

- “we” never resolves to a person automatically
- likely owner suggestions are allowed
- resolved owner should remain null until sufficiently supported

---

## Surfacing rules

- capture more than is surfaced
- Main is for bigger promises
- Shortlist is for smaller but cognitively meaningful commitments
- Clarifications is separate
- push and interruption volume should stay low

---

## Communication rules

- observe before interrupting
- bundle clarifications when possible
- better to communicate too little than too much
- surfaced suggestions should feel like “good catches,” not nagging

---

## Lifecycle rules

- delivered and closed are distinct
- state transitions are reversible
- later signals can reopen commitments

---

# What Must Be Real in MVP

To count as a real MVP rather than a prototype, these things must actually work:

1. at least one working ingestion path for each of the three source families or a realistic equivalent test harness  
2. a normalized signal model across meetings, Slack, and email  
3. commitment detection that produces structured outputs  
4. a unified commitment object with linked signals  
5. classification into Main vs Shortlist  
6. ambiguity handling and a Clarifications view/state  
7. delivery/completion inference from later signals  
8. lifecycle updates over time  
9. low-volume surfaced suggestions  
10. enough traceability to inspect why the system suggested something  

---

# What Can Be Simplified in MVP

The following may be lightweight or provisional in the first version:

- scoring formula sophistication
- provider breadth
- UI polish
- advanced settings
- edge-case completion logic
- model/provider swappability depth
- sophisticated attachment understanding
- elaborate user preference systems

These can be simple if the core product behavior is preserved.

---

# Success Criteria for MVP

The MVP is successful if it demonstrates that Rippled can reliably help a single user reduce commitment-related cognitive load across meetings, Slack, and email.

Signals of success include:

- the user feels they forgot fewer commitments
- surfaced commitments are useful more often than noisy
- Main and Shortlist feel meaningfully different
- Clarifications are rare enough to feel justified
- delivery/completion updates feel helpful rather than magical or suspicious
- the system catches enough explicit commitments to build trust
- the user does not feel like they are maintaining another task system

---

# Failure Conditions for MVP

The MVP should be considered off-track if:

- it behaves mostly like a meeting notes tool
- it behaves mostly like a generic task manager
- it surfaces too many weak suggestions
- it asks for clarification too often
- it loses traceability between signal and commitment
- it overstates certainty
- it ignores Slack/email in practice and becomes meeting-led by accident
- it creates cognitive overhead instead of reducing it

---

# Open Questions for Later Phases

These are intentionally deferred beyond MVP unless needed earlier:

- calendar as a first-class source
- user-specific heuristics by relationship
- stronger attachment/file understanding
- automated clarification delivery through channels
- richer notification personalization
- broader multi-user/team support
- enterprise governance
- full analytics/reporting
- adaptive learning loops
- expanded integration ecosystem

---

# Summary

Rippled’s MVP should be a narrow, trustworthy communication commitment assistant for one primary user.

It should:

- ingest meetings, Slack, and email
- detect and unify commitments
- distinguish big promises from small commitments
- observe quietly before interrupting
- surface only compact, valuable suggestions
- track active, delivered, and closed states
- preserve ambiguity and evidence
- reduce forgotten commitments without becoming another system to babysit

That is the scope the MVP should hold.

---

## Related Briefs

| Brief | Why it connects |
|-------|----------------|
| [[Rippled - 1. Product Vision]] | The vision this MVP must prove |
| [[Rippled - 2. Product Principles Brief]] | The principles the MVP must embody |
| [[Rippled - 3. Commitment Domain Model Brief]] | The unified commitment model this MVP must implement |
| [[Rippled - 8. Commitment Detection Brief]] | The detection pipeline that must work in MVP |
| [[Rippled - 9. Clarification Brief]] | The clarification handling required for MVP |
| [[Rippled - 10. Completion Detection Brief]] | The completion inference that must work in MVP |
| [[Index - Rippled Platform & MVP Brief]] | Full brief map and reading guide |
