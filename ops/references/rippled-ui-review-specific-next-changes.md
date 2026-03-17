# Rippled UI Review — Specific Next Changes

## Overall assessment

This is materially better. The structure is cleaner, the top 3 idea is working, and the page is starting to feel like an assistant surface instead of a dashboard.

The remaining issues are mostly:
- interaction clarity
- density balance
- information hierarchy

These are no longer big conceptual problems.

---

## Active page

### 1. Make “Up next” more commitment-like
Right now it reads too much like a lightweight text list. It should feel closer to a queue of real commitment candidates.

Change each Up next item to include:
- status pill
- one-line title
- one metadata line
- a subtle confidence or freshness indicator
- a click target that opens detail

Suggested structure:
- **Worth confirming**
- Share design mockups with marketing team
- Meetings · Wed 9:30 AM · 68%
- `Open`

Do not necessarily box them like the main cards, but each item should feel tappable and real, not like a sidebar note.

### 2. Add a detail drawer or side panel from both main cards and Up next
Do not make users leave the page first.

Add a **right-side slide-over detail panel** or modal for now.

When a user clicks:
- the card body
- “See why”
- an Up next item

Open a detail panel with:
- full tentative title
- short summary
- source trail
- linked signals
- “why Rippled surfaced this”
- suggested action options
- maybe related people/client

This lets the surface stay calmer because the cards do not need to carry as much explanatory weight.

### 3. Tighten the main cards vertically
The three cards are good, but still slightly too tall.

Reduce height by:
- shrinking top/bottom padding
- tightening spacing between title and body
- shortening metadata line
- moving confidence into a lighter position
- making the action row slightly more compact

The three cards should feel like one triage block, not three separate panels competing for attention.

### 4. Move “Surfaced / 3 items” into the heading area
“Surfaced 3 items” on the left feels detached from the centered heading.

Better:
- keep the centered heading
- directly under it add a small supporting line:
  - `Showing 3 surfaced items`
  - or `Showing 3 highest-priority items`

Then remove the “Surfaced / 3 items” label above the card column entirely.

### 5. Make the primary card action hierarchy clearer
Recommended actions:
- **Confirm**
- **Dismiss**
- `Details`
- `Why this?`

Reason:
- “Add detail” sounds like data entry
- “Details” is lower-friction
- “Why this?” is clearer than “See why”

Styling:
- keep Confirm filled
- keep Dismiss quiet
- keep Details ghost
- keep Why this as text link

### 6. Reconsider whether confidence needs to be on every card face
The percentages are useful, but visually they create a scoring-system feeling.

Try either:
- smaller and lighter
- hidden behind “Why this?”
- or converted to language:
  - High confidence
  - Medium confidence

Recommendation:
- Active = use language, not percentages
- Commitments detail = keep percentages if needed

### 7. Give Up next one explicit purpose
Make it clear that it is:
**Up next — items that may surface after you handle the current three**

Add a tiny subline below the heading:
- `Likely next priorities if your current surfaced items are handled.`

That makes the rail feel intentional.

---

## Commitments page

### 8. Add expandable detail inline or via panel
The Commitments page needs more than grouped rows. It is clean, but too flat.

Each row should support one of:
- inline expansion
- right-side detail panel
- modal sheet

Minimum detail state should show:
- short explanation
- source trail
- related signals
- suggested next action
- why Rippled classified it this way

Without this, Commitments feels like a categorized list, not a usable review surface.

### 9. Make grouping controls more obvious
The grouping tabs are okay, but too visually small and easy to miss.

Improve by:
- adding a label: `Group by`
- making the control sit closer to the list
- slightly increasing contrast or size
- possibly using segmented control styling

Recommended:
`Group by: [Status] [Client] [Source]`

### 10. Strengthen status-group hierarchy
The grouped list is readable, but the sections need stronger separation.

For each group:
- increase spacing above section headers
- use slightly bolder/larger headers
- add count per group

Example:
- **Needs review · 3**
- **Worth confirming · 3**
- **At risk · 1**

### 11. Differentiate closed states more clearly
Delivered and Dismissed are too visually muted in similar ways.

Use clearer distinctions:
- **Delivered** = soft green or success-neutral treatment
- **Dismissed** = lower contrast, more collapsed

Recommendation:
- show Delivered
- hide Dismissed by default behind a “Show dismissed” toggle

Dismissed items rarely deserve primary review attention.

### 12. Make rows more consistent in layout
The first expanded Needs Review item sets a different pattern from the others, which makes the page feel slightly inconsistent.

Choose one base row model:
- row with label + title + metadata
- optional expanded explanation underneath when selected

Then apply it consistently.

### 13. Add a selected-state behavior
Recommended pattern:
- click row → selected state
- selected row expands or opens side panel
- actions appear there

This is better than showing action buttons on every row all the time.

So:
- Active = actions visible on cards
- Commitments = actions visible on selected item only

That will reduce noise substantially.

---

## Header / page frame

### 14. Compress the top strip a bit more
The top source/status strip is working, but still slightly stretched and visually detached.

Tighten it by:
- reducing vertical padding
- shrinking left/right spacing
- grouping source dots more tightly
- toning down divider spacing on the right

It should feel like ambient chrome, not a section.

### 15. Make the centered heading block slightly more compact
The heading works, but there is still too much empty air between:
- status strip
- heading
- main content

Reduce vertical space there by roughly 15–20%.

Enough to keep calmness, but bring the page together.

---

## What to add next

### 16. Add a commitment detail model now
Define one reusable **Commitment Detail Panel** now and use it in both:
- Active
- Commitments

Suggested sections:
- Title
- Current status / confidence
- Why Rippled surfaced it
- Source signals
- Related people / client
- Suggested next move
- Actions

This becomes the shared detailed-view foundation for the product.

### 17. Add optional filters to Commitments, but keep them hidden initially
Not on the first screen as primary UI, but accessible.

Eventually useful:
- open only
- external only
- mine
- confidence threshold
- recent only

For now:
- put a subtle filter button near `Group by`
- do not expose the full control set yet

### 18. Consider one small count on Active right rail
Use:
- `Up next · 6`

Simple, but useful.

---

## Recommended next revision list

1. Make Up next items richer and clearly commitment-like.
2. Add a reusable detail drawer/panel for cards and rows.
3. Tighten main card spacing and reduce vertical bulk.
4. Move “Showing 3 surfaced items” under the centered heading and remove the left-side surfaced label.
5. Rename `Add detail` to `Details` and `See why` to `Why this?`
6. Replace card-face percentage confidence with softer wording, or hide precision in detail.
7. Add a one-line explanatory subtitle under `Up next`.
8. Add `Group by:` label and strengthen grouping controls on Commitments.
9. Add counts to each status group on Commitments.
10. Hide Dismissed by default or collapse it behind disclosure.
11. Use selected-state expansion/detail on Commitments instead of always-visible actions.
12. Slightly compress top-strip and heading spacing.

---

## Most important next step

The biggest practical unlock now is **detail behavior**.

Once users can open a detail panel from either Active or Commitments, the rest of the UI can stay much calmer because it no longer needs to carry so much explanatory weight on the surface.
