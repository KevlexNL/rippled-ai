# Rippled Brief — Add a Short List / Best Next Moves Layer

## Purpose

Add a **short list / best next moves** layer to Rippled that helps answer a simple user question:

**“What should I do next?”**

This feature should help users quickly identify a small number of likely high-value actions that can:
- unblock work
- close loops
- move commitments forward
- reduce the chance of forgotten follow-through

This should be treated as a **UI + product concept brief**, not as final production logic.

---

## Core framing

The short list should **not** become:
- a second task manager
- a backlog
- a generic to-do list
- a replacement for the Commitments view

Instead, it should function as:

**Rippled’s suggested momentum list**  
or  
**Best next moves**

The intent is to preserve Rippled’s core posture as:
- a restrained assistant
- suggestion-based, not authoritative
- selective, not comprehensive
- helpful in moments of indecision

The user feeling should be:

**“If I have 10 minutes, Rippled can tell me the 5 things most likely to unblock progress or keep promises.”**

---

## Product role

This layer should help with situations where the user is stuck thinking:

- What should I do next?
- What can I quickly knock out?
- What is overdue?
- What might be blocking someone else?
- What likely needs a fast response, confirmation, file send, or follow-up?

This is especially useful when a user:
- has many open loops
- is context-switching
- has limited time
- wants quick momentum
- does not want to scan a full commitments list

---

## Recommendation: do not add a new main tab yet

Do **not** make this a separate primary tab at this stage.

Instead, integrate it into the **Active** experience in one of these ways:

### Preferred direction
Evolve **Up next** into a more explicit **Best next moves** list.

### Alternative direction
Add a toggle inside Active:
- Attention now
- Best next moves

### Lower-priority alternative
Use it as a compact daily summary or digest later.

The key point is:
- do not duplicate surfaces
- do not create another adjacent prioritization view unless needed later

---

## Recommended name options

Preferred:
- **Best next moves**

Possible alternatives:
- **Short list**
- **Next best moves**
- **Momentum list**
- **Quick wins**
- **Move things forward**

Recommendation:
Use **Best next moves** for now because it is the clearest balance between usefulness and non-task-manager framing.

---

## What belongs in the list

Items in the list should be biased toward actions that are:

### 1. Quick wins
Low-effort actions that close a loop fast.

Examples:
- sending a promised file
- replying with a date
- confirming timing
- acknowledging a message
- forwarding a deliverable

### 2. Overdue items
Especially externally visible or explicitly promised actions.

### 3. Blocking someone else
Likely waiting-on-you items.

### 4. High-leverage next steps
Actions that unlock multiple downstream things.

### 5. Easy confirmations
Short actions that remove ambiguity.

Examples:
- confirming owner
- confirming deadline
- confirming date/time
- confirming whether something was handled

---

## What should not belong in the list

Do **not** include items simply because they are:
- open
- old
- low-signal
- informational only
- important in theory but not actionable
- better handled in the broader Commitments overview

Avoid turning this into:
- a list of everything still open
- a manually maintained queue
- a due-date-only list
- a generic daily planner

---

## Ranking logic direction

This feature should **not** be driven only by confidence.

It should weigh multiple factors, including:

- likelihood that the item is still open
- external vs internal impact
- blocking potential
- ease / speed of resolution
- whether the action closes a loop
- whether ambiguity can be removed quickly
- whether someone else is likely waiting
- whether the user explicitly promised something
- whether it is overdue or near due

Important:
**Confidence and priority should remain separate ideas.**

A low-effort, high-leverage item may deserve surfacing even if it is not the single highest-confidence commitment.

---

## UI recommendation

## Active page
The current Active page should remain centered on:
- **top 3 surfaced items**
- the highest-priority items that deserve direct attention right now

## Right rail
Repurpose or refine the existing right rail so it becomes:

# Best next moves

This should be:
- a list of **5 items max**
- lighter-weight than the top 3 surfaced cards
- clearly framed as “likely next moves”
- actionable, but not task-manager-like

### Recommended structure per item
Each item should include:
- soft status pill
- one-line title
- compact metadata line
- quick rationale

Example:
- **Worth confirming**
- Share design mockups with marketing team
- Meetings · Wed 9:30 AM
- Quick confirmation may unblock follow-up

Optional:
- subtle `Open` affordance
- opens detail panel

### Optional supporting line under section title
Use something like:
- `5 likely next moves to unblock work or move commitments forward.`
- or
- `If your current surfaced items are handled, these are likely next.`

---

## Relationship to the top 3 surfaced items

The top 3 surfaced items and Best next moves should have **different jobs**.

### Top 3 surfaced items
These are:
- the highest-priority items Rippled believes deserve direct attention now
- more prominent
- fuller cards
- with visible actions

### Best next moves
These are:
- likely useful follow-on actions
- slightly lower priority or lower certainty
- lighter treatment
- quick-scan support layer

This avoids redundancy while still helping users answer:
**What should I do next?**

---

## Relationship to Commitments view

The Best next moves list should **not** replace the Commitments page.

### Commitments page remains:
- the broader review surface
- structured
- grouped
- more complete

### Best next moves is:
- selective
- practical
- momentum-oriented
- optimized for short decision windows

Think:
- **Commitments** = broader review
- **Best next moves** = likely immediate momentum

---

## Detail behavior

Best next moves items should support opening a shared **Commitment Detail Panel**.

When opened, the detail should show:
- tentative title
- short explanation
- source signals
- why Rippled surfaced it
- related person/client if useful
- suggested action options

This should reuse the same detail model used by:
- Active surfaced cards
- Commitments rows

That keeps the design coherent.

---

## Voice and phrasing

The short list must preserve Rippled’s suggestion-based tone.

Use phrasing like:
- may need a follow-up
- may still be outstanding
- worth confirming
- likely blocking next steps
- quick confirmation could move this forward

Avoid phrasing like:
- do this now
- your tasks
- must complete
- overdue task
- pending work item

This should feel assistive, not managerial.

---

## UX principles

### 1. Keep it short
Cap at **5 items**.

### 2. Bias toward momentum
Choose items that are easy, unblocking, or overdue in ways that matter.

### 3. Do not duplicate the top 3
The list should complement, not repeat, what is already surfaced.

### 4. Keep it lightweight
Use a lighter visual treatment than the main cards.

### 5. Make it skimmable
A user should understand the shortlist in seconds.

---

## Acceptance criteria

This addition is successful if:

1. The user can quickly answer: **What should I do next?**
2. The list feels like Rippled’s suggestion, not a command queue.
3. It helps users identify quick wins, overdue items, and blockers.
4. It does not create a second task-manager-like experience.
5. It complements Active and Commitments rather than duplicating them.
6. It remains short, skimmable, and calm.

---

## Recommended one-sentence product doctrine

**Add a Best next moves layer that helps users quickly choose a few likely high-value actions without turning Rippled into a task manager.**
