# Rippled UI Adjustment Brief — Current Active View

## Goal

Implement the current approved Active-page layout adjustments exactly as reflected in the latest mock.

This is a **UI-only implementation brief**.  
Do not change product structure or introduce new concepts.  
Just adjust the existing design to match the current direction.

---

## Changes to implement

### 1. Keep the centered page heading
Use the centered heading block as the primary page anchor.

Required content:
- **What deserves your attention**
- `Rippled is only surfacing the highest-priority items right now.`
- `Showing 3 highest-priority items`

Do not move this heading to the left column.

---

### 2. Add a left-column section heading
Add a clear section heading above the three main surfaced cards.

Use:
- **Surfaced for review**

This heading should:
- sit above the left card stack
- be smaller and lower priority than the centered page heading
- act only as a section anchor for the left column

---

### 3. Keep the right-column heading
Use:
- **Best next moves**
- `Unblock work or move commitments forward.`

Keep this short and exactly in that spirit.

---

### 4. Keep the grouped right-column layout
Best next moves should remain grouped into three stacked cards or sections.

Use these groups:
- **Quick wins**
- **Likely blockers**
- **Needs focus**

Each group should:
- have a small colored pill label
- include a count in the pill
- contain 1–2 items max
- use a grouped card layout

---

### 5. Keep the main surfaced cards simple
For each surfaced card in the left column, keep:
- status pill at top-left
- title
- one short supporting sentence
- source/date/person metadata on the right
- primary action row at bottom-left
- Details button at bottom-right

Do not add extra explanation back onto the card face.

---

### 6. Keep the simplified action row
For surfaced cards, use only:
- `Confirm`
- `Dismiss`

Do not re-add:
- Why this?
- Add detail
- any extra tertiary action in the button row

---

### 7. Keep Details as a separate action on the right
The surfaced cards should keep:
- a separate `Details →` button on the far right

Do not merge this back into the main button row.

---

### 8. Keep supporting metadata visually quiet
The supporting metadata and secondary lines should remain visually subdued.

Examples of elements that should stay lighter or greyer:
- source line
- timestamps
- person/client names
- explanatory secondary lines under best-next-move items

The intent is:
- primary text gets attention first
- supporting context stays readable but quiet

---

### 9. Keep the current page balance
Do not reintroduce:
- extra left-column headings
- duplicate labels
- extra helper modules
- proof-of-work cards in the body
- additional strategic or explanatory content

The page should remain visually balanced between:
- centered page heading
- left surfaced stack
- right best-next-moves stack

---

### 10. Use realistic spacing and hierarchy
Implement spacing so the screen reads in this order:
1. top nav
2. source/status strip
3. centered heading block
4. left surfaced section plus right best-next-moves section

Keep the spacing calm and clean, but do not leave excessive dead space.

---

## Content / mock-data expectations

### Left surfaced cards
Use 3 surfaced items.

They should represent different commitment types where possible, for example:
- overdue follow-up
- missing detail
- externally blocking promise

Avoid duplicating the same placeholder card 3 times in the final mock.

### Right best-next-moves items
Use distinct mock items with short rationale lines.

Each item should include:
- title
- source/date line
- short rationale line

Examples of rationale style:
- `Promised in standup — deadline approaching`
- `Quick confirmation may unblock follow-up`
- `Likely waiting on your reply`
- `External promise — no response detected`

---

## Detail panel behavior

If the current implementation already includes the detail panel, keep it.

The surfaced cards should continue to support opening a detail view via:
- `Details →`

Do not add extra entry points on the card face.

---

## Do not change

Do not change:
- top nav structure
- source/status strip structure
- primary centered heading copy
- overall 2-column layout
- grouped best-next-moves concept
- simplified surfaced-card button row

This brief is only to lock in and implement the current approved layout direction.

---

## Acceptance criteria

This revision is successful if:

1. The left column has a clear section anchor: **Surfaced for review**
2. The centered page heading remains the primary page title
3. The right rail remains grouped as **Best next moves**
4. Surfaced cards remain simple and uncluttered
5. Only `Confirm`, `Dismiss`, and `Details →` remain as surfaced-card actions
6. Supporting metadata stays visually quiet
7. The final page feels balanced, not under-labeled and not over-explained
