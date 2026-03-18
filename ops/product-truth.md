# Rippled Product Truth

## Purpose
This document captures the locked product truth that should guide OpenClaw orchestration and Trinity execution.

It is intentionally compact. It is not the full spec library.
It defines what Rippled is, what problem it solves, what the first-wave MVP is trying to prove, and which product assumptions should be treated as stable versus revisable.

This structure follows the same layered approach already established in the Rippled brief: fully specify the foundational systems, semi-spec the dependent systems, and avoid overcommitting on later surfaces before live behavior exists.

---

## 1. Product Definition
Rippled is an assistant that helps users avoid dropping commitments made in communication.

Rippled observes communication signals, detects likely commitments, tracks their status, and surfaces the most useful ones back to the user.

Rippled is not a traditional task manager whose value depends on manual entry and perfect user maintenance.

---

## 2. Core Problem
The product exists to reduce cognitive load.

Users casually make commitments in meetings, Slack, email, and similar communication streams. Those commitments are easy to forget, especially when they are:
- made informally
- missing a clear due date
- buried in threads
- spread across tools
- not yet important enough to manually enter into a task system

Rippled's job is not to replace judgment. Its job is to help the user notice, clarify, and follow through on likely commitments before they are missed.

---

## 3. Core Promise
Rippled should help users:
- forget fewer commitments
- see what they likely promised
- identify what still lacks clarity
- notice what appears delivered or complete
- trust the system enough to use it as a cognitive support layer

The product promise is assistance, not perfect certainty.

---

## 4. Product Stance
### Rippled is:
- a commitment detection and tracking assistant
- communication-native
- suggestion-based
- confidence-aware
- low-friction

### Rippled is not:
- a standard task manager
- a project management system
- a system that should speak in absolutes when evidence is incomplete
- a tool that should force the user into extra cognitive overhead just to maintain usefulness

The product vision and principles underlying this stance were already identified as foundational and should be locked earlier and more tightly than downstream logic.

---

## 5. Product Principles
These are the non-negotiable operating principles.

### 5.1 Capture more than you show
Rippled should observe broadly and surface selectively.
Not every detected signal becomes a surfaced item.

### 5.2 Infer more than you assert
Rippled may infer likely meaning, but should avoid pretending to know more than the evidence supports.

### 5.3 Never speak in absolutes when confidence is incomplete
The product should favor suggestion language over brittle certainty.

### 5.4 Reduce cognitive burden, do not increase it
If Rippled creates more triage overhead than value, it is failing.

### 5.5 Trust beats cleverness
A simpler, more understandable suggestion is better than a magical but erratic one.

### 5.6 Clarity beats comprehensiveness
Users should get the most useful signal, not the most exhaustive interpretation.

These principles are directly aligned with the Rippled briefing recommendations for the Product Principles / Design Philosophy Brief and the suggestion-not-truth positioning.

---

## 6. Initial User Context
The earliest user context should be treated as:
- founders or owner-operators
- service businesses
- client-facing operators
- people who make many informal commitments across Slack, email, and meetings
- users whose pain is less about planning and more about remembering, clarifying, and not letting things slip

This matches the initial user/persona framing recommended for the first spec layer.

---

## 7. MVP Goal
The MVP should prove that Rippled can do all of the following with enough trust to matter:
1. ingest signals from first-wave communication sources
2. detect likely commitments with acceptable usefulness
3. surface the right subset of those commitments
4. show meaningful state and evidence around them
5. support real testing with live or backfilled data

If the product is not processing real data, the MVP is not being tested meaningfully.

---

## 8. MVP Source Priority
### First-wave sources
- Slack
- email
- meetings

### Later sources
- calendar systems
- task systems
- other structured provider inputs

The source model was explicitly called out as foundational, and those first-wave communication sources should be treated as core, not optional nice-to-haves, for the MVP.

---

## 9. Core User-Facing Surfaces
The MVP should revolve around a small number of meaningful surfaces.

### Main commitments view
Where the user sees the most relevant likely commitments.

### Shortlist or prioritization layer
Where the most important or time-sensitive items are emphasized.

### Clarification view
Where incomplete, ambiguous, or uncertain items can be reviewed.

These user-facing surfaces were already identified as the core surfaces that matter first.

---

## 10. Commitment Truth Model
The product revolves around commitments, not generic tasks.

A commitment is a likely promise, responsibility, or follow-up that can be inferred from communication.

A commitment may be:
- explicit or implicit
- complete or incomplete
- active, delivered, closed, or reopened
- supported by one or more linked signals

The exact commitment model should eventually be specified in the dedicated domain model and lifecycle briefs, but it is already clear from the Rippled spec map that commitments, sources, lifecycle, clarification, completion, and surfacing are the core product objects and behaviors.

---

## 11. Locked vs Revisable Truth
### Locked now
Treat the following as stable unless Kevin explicitly changes them:
- Rippled is a commitment assistant, not a generic task manager
- the product reduces cognitive load rather than demanding more manual upkeep
- the system should suggest rather than over-assert
- first-wave sources are communication sources
- trust and usefulness matter more than exhaustiveness
- the product should capture more than it surfaces
- real data readiness is essential for meaningful MVP testing
- main commitments, shortlist, and clarification are the key initial surfaces

### Revisable after live testing
Treat the following as adjustable:
- exact detection rules
- confidence thresholds
- clarification timing
- completion heuristics
- notification logic
- prioritization scoring details
- edge-case UX states

This locked-versus-revisable split is directly consistent with the recommended three-depth model for Rippled's spec library.

---

## 12. What Good MVP Progress Looks Like
The product is progressing well when:
- the app shows real signals and commitments rather than empty shells
- integrations reflect realistic production-shaped setup, not misleading shortcuts
- a user can understand why something is surfaced
- a user can see what is still unclear
- the system behaves consistently across core flows
- debugging a missing commitment or empty dashboard is possible without guesswork

---

## 13. What To Avoid
Avoid work that pushes Rippled toward:
- heavy manual task entry
- overconfident language
- broad workflow bloat
- speculative personalization before real usefulness is proven
- surface sprawl before the core commitment loop is trustworthy
- hacks that make MVP testing feel successful while hiding true integration limitations

---

## 14. Decision Standard
When evaluating candidate work, ask:
- does this help Rippled function more like a real commitment assistant?
- does this reduce user cognitive load?
- does this improve trust, realism, or debuggability?
- is this aligned with the locked truths above?
- is this unlikely to require strategic reversal later?

If the answer is mostly no, the work is probably not a priority.

---

## 15. Third-Party Extraction as Calibration Signal

When a user connects a meeting transcription tool (Read.ai, Otter.ai, Fireflies, Zoom AI), that tool's extracted action items and summaries represent a second-opinion model output — not ground truth.

**How to use them:**
- Store as `reference_labels` alongside the raw transcript in source_items
- Run Rippled's own detection independently on the same content
- Compare outputs to identify gaps: what Rippled missed vs. what the tool missed
- Use divergence analysis to improve detection prompts, not to copy the tool's output

**Why this matters:**
- Third-party tools are trained on meeting data at scale — high signal quality baseline
- Comparison is free and automatic — no manual labeling needed for meetings
- Rippled should capture more than meeting tools (implicit commitments, email/Slack cross-references) — divergence where Rippled catches more is a feature, not noise
- Over time the gap should narrow from Rippled's side — fewer misses, more implicit catches

This principle applies to any integration where the source tool has its own extraction layer.

---

## Audience Clarity (added 2026-03-18)

**Target user:** Small business owner, 2-10 person teams, hustle mentality.

**Key trait:** Works from working memory, not task systems. Gets things done but doesn't have the overhead — budget, staff, or time — to track everything with diligence. Forgetting things is not a failure of character, it's a natural consequence of doing the work of 100 people with 10.

**Not the target user:** Corporate knowledge workers in structured environments where loop-closing is a trained, supported behavior backed by systems, processes and accountable teams.

**Why this matters for product decisions:**
- Don't build another system to manage. Build a safety net that lives between existing systems.
- Don't require the user to log things. Observe and remind.
- Don't surface everything. Surface what's slipping.
- The dashboard is a review surface, not the daily interface. Slack and email are where this lives.

**Contrast that sharpened this:** Minnie (Kevin's partner) comes from a corporate environment where comprehensive task tracking and RACI-style accountability are standard. Her instinct was "shouldn't the system do everything?" — which is the right question for her world. Kevin's instinct — "we live between the systems, not on top of them" — is the right answer for the Rippled audience.

**One-sentence ICP:** *People who make a lot of commitments but don't have the systems or discipline to track them — and don't want another system to manage.*

---

## Commitment Lifecycle States (added 2026-03-18)

The current binary (active / dismissed) is insufficient. The full intended lifecycle:

| State | Meaning | Triggered by |
|-------|---------|-------------|
| `detected` | Extracted, not yet reviewed | System |
| `active` | Surfaced, needs attention | System (surfacing logic) |
| `confirmed` | User verified as real | User |
| `dormant` | Not relevant now, but hold onto it | User (replaces "dismiss") |
| `completed` | Done | User |
| `dismissed` | Explicitly irrelevant, can be forgotten | User (deliberate, rare) |

**Key distinction — dormant vs dismissed:**
- **Dormant** = "I don't care about this *right now* but it may matter later." System retains it, can resurface when conditions change (time passes, related commitment completes, user revisits).
- **Dismissed** = "This is wrong, irrelevant, or noise." System deprioritizes it for training purposes but retains for eval.

**Resurface triggers for dormant commitments:**
- Time-based: resurface after X weeks if not resolved
- Event-based: resurface when a linked/related commitment is completed ("you said you'd do X after Y — Y is done")
- Manual: user can review dormant list at any time

**Why this matters:**
Current "dismiss" permanently hides things that may be genuinely important but just not urgent. Small business owners need to be able to say "not now" without saying "never." The system should hold the memory so they don't have to.

---

## Commitment List Filtering (added 2026-03-18)

**Default view (what the user sees):**
1. **My commitments** — assigned to or owned by the user. Show by default.
2. **Unowned / unclear owner** — no clear assignee, surfaced for triage. Show by default.
3. *(collapsed)* **Dismissed** — toggled via "Show dismissed" (already exists)
4. *(collapsed)* **All commitments** — everything else (other people's commitments, low-relevance items). Hidden behind a link at the bottom: "View all commitments →"

**Why:**
The current flat list creates cognitive overwhelm — the user sees Matt's commitments to his org, Allie's action items, and their own responsibilities all at the same level. Most of the list isn't actionable for the user right now.

**Filtering logic:**
- `mine` = `owner == user` OR `assignee == user` OR entity resolved to user
- `triage` = owner is null/unresolved — user needs to decide if it's theirs
- `others` = owner resolved to someone else — tracked but hidden by default
- User can always access `others` via "View all commitments" — nothing is deleted

**UI:**
- Active tab and full Commitments tab both apply this filter
- "View all commitments" link sits below the dismissed toggle
- Count shown: "12 commitments · 34 others tracked"

**Connection to dormant state:**
Items the user marks "not now" (dormant) behave like `others` in the list — tracked, hidden, resurfaceable.

---

## Commitment Structure Definition (added 2026-03-18)

### The Core Definition

A commitment is **a promise from one person to another, with an expected delivery.**

**Required elements:**
- **Owner** — who made the promise (accountable for delivery)
- **Deliverable** — what was promised
- **Counterparty** — who is waiting on it / who it was promised to

**Optional but important:**
- **Deadline** — explicit ("by Friday") or inferred ("this week", "soon")
- **Context** — the source this came from (email thread, meeting, Slack channel)

### Canonical Extraction Format

Every commitment should be expressible as:

```
[Owner] promised [Deliverable] to [Counterparty] [by Deadline]
in the context of [Source]
and the user's relationship to it is [mine / contributing / watching]
```

Example (mine):
> Kevin promised a portal dashboard screenshot to the team by today
> in the context of email thread: "KRS Portal Update"
> relationship: mine

Example (watching):
> Matt promised a Zoom walkthrough to Nadine this week
> in the context of email thread: "Onboarding Nadine"
> relationship: watching — Kevin facilitated but is not responsible

### User Relationship Model (replaces RACI)

Three relationship types between the logged-in user and each commitment:

| Role | Meaning | Surfacing default |
|------|---------|------------------|
| `mine` | User made the promise / is the accountable owner | Always surfaced in Active + Commitments |
| `contributing` | Someone else owns it, but user has a specific task within it | Surfaced in Commitments when user's piece is due |
| `watching` | User is informed or facilitated, not responsible | Hidden by default — tracked silently, accessible via "All commitments" |

### Detection Rules

- `mine` = owner resolves to user, OR user explicitly named as responsible ("Kevin to...")
- `contributing` = user mentioned alongside others as a participant, not primary owner
- `watching` = commitment between two other parties; user is cc'd, facilitated, or just present

### Why This Matters

Without a clear relationship model, the user sees Matt's commitments to his org alongside their own deliverables. The cognitive load doesn't decrease — it increases. The relationship field is what makes filtering meaningful.

This structure must be enforced at extraction time. A commitment record that cannot answer "who promised what to whom" should not be surfaced — it should be flagged as incomplete and held for triage.
