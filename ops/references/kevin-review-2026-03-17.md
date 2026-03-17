# Kevin's First Live Review — 2026-03-17
*Source: Loom recording + transcript, first review of 108 detected commitments*

---

## 🔴 Bugs (blocking basic use)

### B1 — Dismiss gives no visual feedback
Clicking Dismiss appeared to do nothing. Item stayed visible. Kevin thought it failed. Checking "Show dismissed" at bottom revealed it did work — the item was dismissed. **Fix: immediate visual removal or animation on dismiss.**

### B2 — Confirm button non-functional
Both the right pane confirm button and the center console confirm button did nothing. **Fix: wire confirm action to backend.**

### B3 — Source not visible on commitment cards
Kevin cannot see where a commitment came from (which email, which meeting, which sender). Without source context, triage is nearly impossible. **Fix: show source email subject/sender or meeting title on every card. Make it tappable to open source.**

---

## 🟡 Detection Quality Issues

### D1 — Timestamp shows processing date not signal date
Commitments show "today" as date because they were processed today. Kevin noted: *"it doesn't mean that the signal should be flagged for today — it should have a very specific date and time that we ingest from the source."* **Fix: use `occurred_at` (original email/meeting date) for display, not `created_at`.**

### D2 — "Recipient" instead of resolved name
Several commitments say "recipient" where a real name should appear. Kevin couldn't tell if he or Mitch was responsible. **Fix: improve entity resolution — when the model can't identify the person, use the email To: field or sender as fallback. Never show "recipient" as an owner.**

### D3 — Samantha/Savannah transcription artifact
Read.ai transcribed "Samantha" as "Savannah" in some meeting transcripts. Rippled's model carried this through without catching it. Kevin noticed: "that may be a transcription challenge." **Fix: cross-reference names against known contacts (people/Niobe data) to catch transcription errors in meeting source items.**

### D4 — Context-free commitments are noise
Several items were too vague without seeing the source: "Provide update on rough draft of manager's newsletter", "Wrap up projects, run pods, present materials." Kevin couldn't act on these. Root cause: these are likely extracted without enough surrounding context. **Fix: require minimum context window around trigger phrase before creating a commitment. If content is too thin, lower confidence and hold from surfacing.**

---

## 🟢 Product Insights (bigger concepts)

### P1 — Commitments need to cluster into "epics"
Multiple commitments are sub-items of the same parent goal: "Run CSV imports", "Full demo Wednesday", "Build gap analysis" all belong to *Wednesday RevEngine demo delivery*. Kevin described these as "epics rather than features." **The context layer (`commitment_contexts`) already exists for this — but contexts need to be auto-assigned via semantic clustering, not manually. This is the next major product unlock.**

### P2 — Conditional/dependent commitments
"Prepare pilot playbook for Nadine" should be dormant until "Demo to Matt" is delivered. Kevin said: *"I'd love to be reminded of this once I unblock the previous action — hey, this is what you promised after this action."* **Feature: commitment dependencies. When a commitment is marked as conditional on another, activate it (and notify) when the predecessor is completed.**

### P3 — Commercial weight affects priority
Kevin dismissed the "continue Rippled development, revisit in 3 months" commitment because there's no commercial agreement with Matt around it yet. The model detected a real commitment but Kevin doesn't want to track it. **Implication: commitment importance should be weighted by relationship type + commercial context. A commitment to Matt about client work outranks a speculative future conversation.**

### P4 — "Silently track" mode
Several commitments (Adam's dashboard revisions, schedule review meeting, build first dashboard draft) Kevin said: *"not something I care about now but want to silently track and flag later."* **Feature: a "watch" state — commitment is tracked but not surfaced until triggered by time or related event. Different from dismiss (gone) and active (surfaced).**

---

## Summary Assessment
Detection quality: **good** — real commitments were found, the core extraction works.
Presentation quality: **needs work** — source visibility, timestamp display, and button functionality are blocking effective review.
Most valuable next build: **source visibility + correct timestamps** (B3 + D1). These two alone would make the list 2x more useful.
Biggest product insight: **the epic/context clustering** (P1) — auto-assigning contexts is the highest-leverage improvement after the bugs are fixed.
