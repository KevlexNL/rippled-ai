# Product Truth

!!! warning "Locked document"
    This document is the product source of truth. Changes require Kevin's explicit approval.

---

## What Rippled Is

A commitment intelligence layer that watches your communication channels and surfaces what you promised — and what was promised to you — before it gets forgotten.

**It is not:**
- A task manager
- A project management tool
- Another inbox to check

**It is:**
- An ambient safety net that lives between your existing tools
- A memory prosthetic for people who work from working memory
- A layer that catches what's falling through the cracks

---

## The Core Object

A commitment is **a promise from one person to another, with an expected delivery.**

Required elements:
- **Owner** — who made the promise (accountable for delivery)
- **Deliverable** — what was promised
- **Counterparty** — who it was promised to

Optional but important:
- **Deadline** — explicit or inferred
- **Requester** — who originally asked for it (may differ from counterparty)
- **Beneficiary** — who ultimately benefits

---

## User Relationship Model

Every commitment has a relationship to the logged-in user:

| Relationship | Meaning | Default view |
|-------------|---------|-------------|
| `mine` | I made the promise / I'm accountable | Active + Commitments tab |
| `contributing` | Someone else owns it, but I have a task in it | Commitments tab only |
| `watching` | Commitment between two other parties | Hidden (All commitments) |

---

## Target Audience

**Small business operators with a hustle mentality.**

- 2–10 person teams doing the work of 100
- Work from working memory, not task systems
- Don't have time to log things — they just get work done
- Forgetting things is natural, not a failure
- They don't want another system to manage

**Not the target user:** Corporate knowledge workers in structured environments where loop-closing is a trained, supported behavior backed by dedicated systems and processes.

**One-sentence ICP:** *People who make a lot of commitments but don't have the systems or discipline to track them — and don't want another system to manage.*

---

## Commitment List Filtering

Default view shows:
1. **My commitments** — assigned to or owned by user
2. **Triage** — unclear owner, user needs to decide
3. *(collapsed)* Dismissed
4. *(collapsed, link)* All commitments — everything else

---

## Commitment Lifecycle States

See [Architecture → Lifecycle](../architecture/lifecycle.md)

Key distinctions:
- `dormant` ≠ `discarded` — dormant means "not now but real", discarded means "wrong"
- `delivered` ≠ `completed` — delivered is system-detected, completed is user-confirmed
- `confirmed` ≠ `active` — confirmed has explicit user signal, active is system-inferred

---

## What Rippled Does Not Do

- Manage tasks for people (other tools do this)
- Close the entire loop (humans are still accountable)
- Work for teams (single-user focus keeps complexity manageable)
- Tell you what to do (it reminds you of what you said you'd do)

Source: `ops/product-truth.md`
