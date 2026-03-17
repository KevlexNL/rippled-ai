# Rippled Active + Commitments UI Revision Brief

## Purpose

Revise the current UI prototype so the product feels more coherent, more selective, and more aligned with Rippled’s core promise:

**Rippled is a restrained assistant that helps users remember and follow through on commitments without becoming another task manager or a noisy dashboard.**

This brief is for a **UI-only revision**.  
Do not implement real product logic yet.  
Use static mock data and presentational state only.

---

# Why this revision matters

The current prototype is much closer than earlier versions, but it still spreads user attention across too many conceptual buckets at once.

Right now, the UI still contains too much duplication between:
- main surfaced items
- shortlist-like behavior
- commitments overview
- proof-of-work blocks
- source/status information
- extra support modules like good catches

That creates friction against the intended Rippled experience:
- low cognitive load
- selective surfacing
- quiet confidence
- clear prioritization
- trust through restraint

Rippled should not make the user more aware of the system.  
It should make the user feel that the system is calmly handling the background while only bringing forward what truly deserves attention. That directly aligns with the product principles and surfacing philosophy already defined for Rippled.

---

# Core product posture this UI must express

Design the revised UI so Rippled feels like:

- a restrained executive assistant
- not a task manager
- not a CRM
- not a metrics dashboard
- not a feed of everything the system noticed

The UI should communicate:

- calmness
- trust
- selectivity
- quiet intelligence
- visible but low-friction liveness
- clarity over comprehensiveness

The emotional outcome should be:

**“Rippled is already watching what matters. I only need to look at the few things it thinks deserve a decision right now.”**

This is consistent with the product brief stack that locks in cognitive load reduction, anti-task-manager positioning, and “capture more than you show / infer more than you assert / never speak in absolutes / trust beats cleverness.”

---

# Final IA / surface model

## Keep only 2 primary views

### 1. Active
The assistant view.  
This is the default home surface.

### 2. Commitments
The broader review surface.

## Remove the separate Shortlist tab
The separate Shortlist view is now redundant.

Its value should be absorbed into:
- the **3-item main attention area** on Active
- the **right-rail “Up next” list** on Active

This matches the broader recommendation to avoid preserving separate surfaces when they conceptually overlap and increase UI complexity. Rippled should not keep multiple adjacent views that all express roughly the same prioritization idea.

---

# View 1: Active

## Purpose
The Active view is **not** a dashboard in the traditional sense.

It is a **3-item assistant surface**.

Its job is to answer:
- what deserves my attention now?
- what is coming next?
- is Rippled actively working in the background?

## Active page structure

### A. Top navigation bar
Include:
- Rippled wordmark
- Active
- Commitments
- settings / notifications / profile

Keep this simple and quiet.

### B. Slim system status strip
Directly under top nav, keep a single compressed status layer.

It should include:
- connected source indicators
- freshness / recent activity
- signal count over the last 24 hours
- one compact reassurance phrase

Example:
- Email • Slack • Meetings • Calendar
- 14 signals reviewed in the last 24 hours
- Watching 6 active threads

This replaces the need for separate large “source health” or “quietly covered” modules.

### C. Centered heading area
Use a proper centered heading block near the top of the page.

This should replace the awkward floating “Rippled is monitoring your inbox…” line.

Recommended pattern:
- heading: **What deserves your attention**
- supporting line: **Rippled is only surfacing the highest-priority items right now.**

This area should feel more like Claude’s centered conversation framing:
- calm
- clear
- slightly editorial
- not decorative
- not promo-like

### D. Main left column: top 3 surfaced items only
This is the centerpiece of the page.

Rules:
- show **exactly 3 surfaced items**
- when one is handled, the next best candidate would conceptually replace it
- do not show long lists here
- do not let this become a review queue

This aligns strongly with the surfacing and prioritization direction already established for Rippled, including bundle-size rules and selective surfacing rather than comprehensive display.

### E. Right rail: “Up next”
Use the right rail to show the next most relevant commitments that did not make the top 3.

This replaces the old shortlist tab in practice.

The right rail should contain:
- a compact **Up next** list
- around 5–7 items
- lighter treatment than the main cards
- title + status + small metadata line
- maybe one subtle affordance, but keep it lightweight

Do **not** use the right rail for random support modules.

### F. Sticky footer: proof of work
Move Proof of work out of the page body and into a sticky footer.

This should act as ambient reassurance, not a dashboard block.

It should be:
- compressed
- low visual weight
- always available
- not boxy
- not four equal cards

Preferred style:
- `89 emails captured • 234 messages processed • 12 meetings logged • 31 people identified`

Or:
- `Rippled reviewed 14 signals today • 234 messages processed this week`

The goal is quiet proof, not KPI emphasis.

### G. Remove Good catches
Remove the Good catches module entirely.

Reason:
- it introduces another category competing for attention
- it weakens the simplicity of the Active surface
- if something is important enough, it should appear in the top 3 or Up next
- if not, it should remain quietly observed until it matters

This is fully consistent with Rippled’s principle that the system should surface selectively and keep more context internal than visible.

---

# Active view content rules

## Top surfaced items
Each of the 3 cards should represent a commitment candidate or follow-through item that most deserves human attention.

Examples:
- at risk follow-up
- likely missing date
- likely needs confirmation
- unclear owner
- likely still open external promise

## Card layout
Each primary card should include:
- soft status label
- tentative title
- short explanation
- provenance / source cues
- visible actions

### Required visible actions
Show actions directly on the card. Do not hide them.

Preferred actions:
- Confirm
- Dismiss
- Add detail

Also include:
- See why

Keep actions restrained and low-friction.

## Language rules
Card language must be:
- tentative
- assistant-like
- confidence-sensitive
- not ticket-like
- not absolute

Prefer:
- “David contract review may need a follow-up”
- “Acme onboarding follow-up may need a clearer date”

Avoid:
- “Follow up with David”
- “Timeline unclear”
- “Task overdue”

This matches the earlier guidance that Rippled should never assert as fact when it is actually making a structured suggestion. The Suggestion Language / Voice direction explicitly supports tentative phrasing and confidence-sensitive language.

## Provenance / explainability
Each card should provide subtle context for why it is appearing.

Examples:
- from Slack
- from meeting + email
- mentioned yesterday
- 2 related signals
- no follow-up detected

“See why” should remain available, but evidence should not dominate the default card view.

---

# View 2: Commitments

## Purpose
This is the broader review surface.

It is where the user can see a larger set of commitments Rippled is tracking.  
This page may be more structured and slightly more operational than Active, but it still must not feel like Jira, Asana, a CRM, or a task manager.

## Commitments page structure

### A. Shared top navigation
Keep the same top nav and slim status strip as Active.

### B. Centered page heading
Use a clear heading such as:
- **All commitments**
- supporting line: **A broader view of likely commitments Rippled is tracking across your connected sources.**

### C. Main commitments list
Show a broader list of items than the Active view.

This can be:
- list-based
- grouped list
- list/table hybrid

But it should still remain visually clean and readable.

### D. Grouping support
Allow grouping in Commitments.

Preferred grouping modes:
1. **Status** (default)
2. **Client**
3. **Source / type**

Default should be **Status**, because it is the clearest and most actionable mental model for the user.

Suggested default groups:
- Needs review
- Worth confirming
- At risk
- Delivered
- Dismissed

This reflects the broader brief architecture where the Commitments surface can be more structured than the lighter Active surface, while still remaining within Rippled’s suggestion-based product model.

### E. Detail / selected state
You may optionally support a selected-item detail panel or expanded inline view, but keep it lightweight.

Avoid turning the Commitments page into a dense admin interface.

---

# What to remove from the current prototype

Remove these from the revised direction:

- separate **Shortlist** tab
- standalone **Good catches** module
- large boxed **Proof of work** card in the right rail
- awkward floating “Rippled is monitoring your inbox…” sentence line
- duplicate prioritization surfaces that repeat the same items in multiple places
- dashboard-style support modules that compete with the main assistant flow

---

# Design principles for this revision

## 1. Make the product feel more coherent by reducing conceptual duplication
The problem is not primarily visual clutter.  
It is duplicated mental models.

The user should not have to distinguish between:
- top items
- good catches
- shortlist
- commitments
- proof widgets
- multiple status areas

The design should collapse those into a more coherent system.

## 2. The Active page should feel like guided attention, not a queue
This is the most important principle.

The Active page is not a place to browse a lot of work.  
It is a place to see the **3 things Rippled believes most deserve your attention now**.

## 3. Preserve visible liveness, but compress it
The product still needs to feel alive and trustworthy.

Do not remove:
- connection state
- freshness cues
- signal volume
- quiet proof of work

But compress them into:
- one slim status strip
- one sticky footer

This preserves trust without spreading system-awareness across the whole screen.

## 4. Let the right rail reinforce the primary task
The right rail should support the main flow, not distract from it.

That is why it should become **Up next**, not a mixed collection of widgets.

## 5. Keep the product identity assistive, not managerial
Every UI decision should be tested against this question:

**Does this make Rippled feel more like a calm assistant, or more like a work management tool?**

Rippled should stay on the assistant side.

---

# Visual direction

Keep the current lighter direction and continue refining it.

Use:
- white / off-white backgrounds
- light gray structure
- soft borders
- black / charcoal text
- restrained accent use
- strong whitespace
- clean typography hierarchy

Do not add more visual emphasis to compensate for removed modules.  
The goal is not to fill space.  
The goal is to create a stronger center of gravity.

---

# Final page model

## Active
- top nav
- slim status strip
- centered heading
- left: 3 surfaced items only
- right: Up next list
- sticky footer: proof of work

## Commitments
- top nav
- slim status strip
- centered heading
- grouped commitments list
- optional lightweight detail/expanded state

---

# Build constraints for Claude Code

This is still a **UI-only prototype**.

## Do:
- use static mock data
- use presentational state only
- make tabs switchable locally
- make grouping locally switchable in Commitments
- keep components reusable
- keep layout polished and realistic

## Do not:
- wire APIs
- fetch data
- implement real queue replacement logic
- implement real ranking logic
- implement persistence
- implement integrations
- implement real source monitoring behavior

The goal is strictly:
**test the revised information architecture and interaction feel before implementing logic.**

---

# Acceptance criteria

The revision is successful if:

1. The Active page feels calmer and more coherent than the current prototype.
2. The user’s attention is centered mostly on 3 surfaced items.
3. The right rail feels supportive, not competitive.
4. Proof of work becomes ambient reassurance instead of a widget.
5. The product feels more like a restrained assistant and less like a dashboard.
6. The Commitments page supports grouped review without becoming a task manager.
7. Duplicate information is meaningfully reduced.
8. The UI still feels alive and trustworthy, not empty.

---

# One-sentence design doctrine

**Design Rippled so the user sees only the few things worth deciding now, while the rest of the system stays visible only as quiet confidence in the background.**
