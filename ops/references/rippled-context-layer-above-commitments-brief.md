# Rippled Brief — Add a Context Layer Above Commitments

## Goal

Add a lightweight **context / project-like taxonomy layer** above individual commitments so Rippled can connect related commitments and signals under a shared work context.

This should help users understand not just:
- which commitments are open

but also:
- what bigger work context those commitments belong to

This is a **product + UI implementation brief** for Claude Code.  
Keep it practical. Do not expand this into a full project management system.

---

## What this should do

Rippled should be able to recognize that several commitments may belong to the same broader context, such as:

- a client onboarding
- a proposal cycle
- a legal / NDA thread
- a campaign or launch
- a recurring internal initiative
- a meeting-driven workstream

Examples:
- “send revised proposal”
- “confirm onboarding date”
- “share updated mockups”

These may be separate commitments, but Rippled should be able to recognize when they belong to the same broader context, such as:
- **Acme onboarding**
- **Vertex legal / NDA**
- **Marketing team deliverables**
- **Company all-hands prep**

---

## Why this adds value

This should improve Rippled in 4 practical ways:

### 1. Better context recovery
Users can understand what commitments are about, not just see them as isolated items.

### 2. Better prioritization
Multiple open commitments tied to the same context can signal that the broader workstream needs attention.

### 3. Better merge / deduplication support
Signals from email, meetings, and Slack can be connected not only to the same commitment, but also to the same broader context.

### 4. Better explainability
Rippled can say:
- this belongs to Acme onboarding
- this belongs to company all-hands prep
- there are 3 related commitments in this context

That makes the system feel less random and more trustworthy.

---

## Scope for this phase

Do **not** build:
- a full project management system
- manual project setup flows
- mandatory taxonomy for every item
- a separate Projects tab
- a heavy hierarchy UI

Do build:
- a lightweight inferred **Context** layer
- a way to display context in detail view
- a way to group commitments by context in the Commitments view

---

## Core model change

Add a conceptual layer like this:

**Context → Commitments → Signals**

### Context
A broader work grouping inferred from connected sources.

Examples:
- Acme onboarding
- Vertex proposal
- Q1 finance review
- Company all-hands
- Marketing deliverables

### Commitment
An individual likely promise / follow-up / clarification item.

### Signals
The supporting evidence from:
- email
- Slack
- meetings
- other connected sources later

---

## Implementation requirements

## 1. Add a Context field to commitment data
Each commitment should be able to optionally reference a context.

Add mock support for:
- `context_id`
- `context_name`

Examples:
- `context_name: "Acme onboarding"`
- `context_name: "Company all-hands prep"`

This does not need final backend logic yet, but the UI and mock data should support it cleanly.

---

## 2. Show Context in the detail panel first
The first place this should appear is the detail view.

When opening a surfaced item or commitment detail panel, add a new section:

### Context
Show:
- context name
- optional short context summary if available
- count of related commitments in this context

Example:
- **Context**
- Acme onboarding
- 3 related commitments in this context

Optional:
- a subtle link or affordance to view related commitments in the Commitments page

---

## 3. Add “Related commitments in this context” to detail view
Inside the detail panel, below the Context section, add a small related-items block.

Show 2–4 related commitments max.

Example:
- Confirm onboarding date
- Send revised onboarding doc
- Follow up on client kickoff timing

This should help users quickly understand the surrounding work without leaving the page.

---

## 4. Add “Group by Context” to the Commitments page
Update the grouping control in Commitments.

Current grouping modes:
- Status
- Client
- Source

Add:
- **Context**

Updated grouping options:
- Status
- Client
- Source
- Context

Default should remain:
- **Status**

Do not make Context the default grouping yet.

---

## 5. Define how Context grouping should look
When grouped by Context, the Commitments page should show sections like:

- **Acme onboarding**
- **Vertex legal / NDA**
- **Marketing deliverables**
- **Company all-hands prep**

Within each group, show:
- related commitment rows
- compact status mix if possible

Optional summary line per group:
- `3 open · 1 at risk · 2 worth confirming`

This should help the user understand the bigger work cluster without turning the page into a project management tool.

---

## 6. Keep Context lightweight and inferred
Do not require the user to create, rename, or manage contexts manually in this phase.

The assumption for now:
- contexts are inferred from signals / mock data
- users can view them
- users can use them to understand grouped commitments

Manual editing can come later if needed.

---

## 7. Do not redesign the whole Commitments page around Context
Context should be added as:
- a detail-view field
- a grouping mode

Do not:
- replace status grouping as default
- turn the screen into a context board
- add a separate context overview surface yet

This should be an additive layer, not a new product mode.

---

## UI guidance

## Detail panel
Add sections in this order where appropriate:
1. Title
2. Status / confidence
3. Why Rippled surfaced this
4. Source signals
5. **Context**
6. **Related commitments in this context**
7. Related person / client if useful
8. Suggested next move

## Commitments page
Add:
- `Group by: Status | Client | Source | Context`

When Context is selected:
- use context section headers
- show grouped commitments under each header
- keep row layout consistent with current commitments design

---

## Mock-data requirements

Update mock data so commitments can belong to broader contexts.

Example mock contexts:
- Acme onboarding
- Vertex legal
- Marketing team deliverables
- Company all-hands prep
- Q1 finance review

Example commitment records should include context linkage.

Use cases to model:
- multiple commitments under one context
- one isolated commitment with no strong context
- commitments from different sources under the same context

---

## What not to do yet

Do not add:
- a Projects tab
- project creation UI
- drag-and-drop organization
- project dashboards
- manual context management
- nested task structures
- due-date planning interfaces

This should remain:
- inferred
- lightweight
- supportive
- non-managerial

---

## Acceptance criteria

This addition is successful if:

1. A commitment can display a context in its detail view.
2. The detail panel can show related commitments from the same context.
3. The Commitments page supports **Group by Context**.
4. Context grouping helps users understand the broader work cluster behind related commitments.
5. The feature adds structure without making Rippled feel like a project management tool.
6. Status remains the default grouping mode.
7. The UI remains lightweight and calm.

---

## One-sentence implementation doctrine

**Add a lightweight inferred Context layer so Rippled can connect related commitments under a shared workstream without turning the product into a project management tool.**
