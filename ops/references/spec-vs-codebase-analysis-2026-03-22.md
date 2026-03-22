# Spec vs Codebase Analysis — 2026-03-22

**Source docs:** `ops/signal-and-commitment-processing/`  
**Analysed by:** Mero  
**Purpose:** Compare Kevin's future architecture docs against what Rippled actually has, identify gaps, and propose Work Orders.

---

## Part 1: What's Already There (Better Than The Docs Assume)

### Lifecycle states
The spec defines: `proposed → active → in_progress → delivered → completed → canceled → closed`

The codebase has: `proposed, needs_clarification, active, confirmed, dormant, delivered, closed, discarded`

Close but not identical — `in_progress` and `canceled` are missing. `confirmed` and `dormant` are additions the spec doesn't cover yet.

### Completion detection
Fully implemented: `services/completion/` with matcher, scorer, updater, detector. Already distinguishes `delivered` vs `closed`. The Completion Detection Brief describes this as a future build — it's live and working.

### Ambiguity/clarification types
Rich `AmbiguityType` enum already covers:
- owner_missing, owner_vague_collective, owner_multiple_candidates, owner_conflicting
- timing_missing, timing_vague, timing_conflicting, timing_changed, timing_inferred_weak
- deliverable_unclear, target_unclear
- commitment_unclear, status_unclear

Aligns closely with the Clarification Brief.

### Signal roles
`SignalRole` enum: origin, clarification, progress, delivery, closure, conflict, reopening. Maps well to the spec's lifecycle linking stage.

### Slack connector
Exists and normalizes Slack events. Thread context handling partially there.

### Commitment candidate model
`CommitmentCandidate` table exists in the DB. Not yet fully aligned with the spec's candidate contract but the concept is there.

### Confidence fields
6 separate confidence scores exist: `confidence_commitment, confidence_owner, confidence_deadline, confidence_delivery, confidence_closure, confidence_actionability`. More granular than what the spec asks for.

---

## Part 2: What's Missing or Misaligned

### 1. No `NormalizedSignal` contract — CRITICAL

The docs define a shared normalized signal object that every connector must produce:

```
NormalizedSignal
- signal_id
- source_type
- source_thread_id
- source_message_id
- occurred_at / authored_at
- actor_participants[]         // who authored/spoke
- addressed_participants[]     // direct recipients / audience
- visible_participants[]       // all participants visible in context
- latest_authored_text         // only the current authored block
- prior_context_text           // optional, bounded
- attachments[]
- links[]
- metadata{}
```

**What exists instead:** Each connector normalizes directly to `SourceItemCreate` (the DB model). There's no intermediate shared signal object. This means email, Slack, and meetings produce structurally different inputs to the detection pipeline. The detection model has no way to know whether `prior_context_text` is clean or whether the full body still contains quoted history.

**Why it matters:** Without a shared contract, every detection quality improvement has to be applied three times in three different places. With a shared contract, improvements apply once.

---

### 2. No `speech_act` classification — HIGH

The spec defines 9 speech acts as the primary semantic classification:
- `request` — someone is asking for something
- `self_commitment` — speaker commits to something themselves
- `acceptance` — speaker accepts ownership of a request
- `status_update` — progress report, no new obligation
- `completion` — signals delivery or done
- `cancellation` — withdrawing a commitment
- `decline` — refusing a request
- `reassignment` — transferring ownership
- `informational` — no commitment content at all

**What exists instead:** `CommitmentType` (verb-based: send, review, deliver, follow_up, investigate...). This classifies *what* the deliverable is, not *what the speaker is doing*. The system cannot distinguish "Kevin asked Matt to do X" from "Kevin committed to do X" — both land as the same commitment object. This is the root cause of many false positives where requests are extracted as commitments.

---

### 3. `requester_party` and `beneficiary_party` don't exist — HIGH

The spec adds:
- `requester_party_id` — who originally asked for the thing
- `beneficiary_party_id` — who ultimately benefits from the delivery

**What exists:** `resolved_owner`, `suggested_owner`, `counterparty_name`, `counterparty_email`. Only one "other party" field, which conflates requester and beneficiary.

**Why it matters:** "Matt asked Kevin to prepare the portal demo for Nadine" has three distinct parties: requester (Matt), owner (Kevin), beneficiary (Nadine). Currently the system can only represent two of them. This affects the `user_relationship` classification (mine/contributing/watching) and filtering logic.

---

### 4. Email quoted-text isolation not enforced — HIGH

The spec is explicit: "isolate only the latest authored message" and "do not detect new commitments from quoted text." Quoted history is only available as `prior_context_text` for linking, not for new candidate creation.

**What exists:** The email normalizer stores `content` and `content_normalized` in `source_items` but does not strip quoted history before passing to detection. The full email body (including all quoted reply chains) goes to the LLM. This is a significant source of false positives — old commitments from quoted emails get re-detected as new ones.

---

### 5. `due_precision` missing — MEDIUM

The spec defines: `due_precision: exact | day | week | vague | none`

**What exists:** `resolved_deadline` (timestamp), `vague_time_phrase` (text), `timing_ambiguity` (enum). No precision tier. The distinction between "Friday at 3pm" (exact) vs "sometime this week" (week) vs "soon" (vague) is currently only captured in the free-text `vague_time_phrase`, not as a structured field.

---

### 6. Lifecycle state misalignment — MEDIUM

| Spec state | Codebase state | Status |
|-----------|----------------|--------|
| proposed | proposed | ✅ Match |
| active | active | ✅ Match |
| in_progress | — | ❌ Missing |
| delivered | delivered | ✅ Match |
| completed | — | ❌ Missing (closed ≠ completed) |
| canceled | — | ❌ Missing |
| closed | closed | ✅ Match |
| — | confirmed | Extra (maps to active behavior) |
| — | dormant | Extra (valid product concept, not in spec) |
| — | needs_clarification | Extra (valid, should stay) |
| — | discarded | Extra (valid) |

`in_progress` and `canceled` are gaps. `completed` and `closed` are distinct in the spec but merged in the codebase.

---

### 7. Slack thread enrichment not implemented — MEDIUM

The spec requires: later thread replies can enrich earlier signals — a "done" reply in a thread should close the parent commitment. The Slack normalizer processes messages in isolation. No mechanism exists to look back at the thread parent or update a prior signal when a reply comes in.

---

### 8. Meeting processing spec is blank — LOW (for now)

`4. Meeting Processing.md` is empty. Until it's written, nothing to implement. The meeting normalizer exists and ingests transcript data — it just hasn't been updated to enforce the NormalizedSignal contract yet.

---

### 9. Confidence as a single `confidence_overall` score — LOW

The spec proposes one canonical overall confidence score for surfacing decisions. Currently there are 6 separate confidence fields plus `confidence_for_surfacing` (a derived seventh). The codebase is actually more granular than what the spec asks for — this isn't a problem, just worth noting that the surfacing logic should continue to use `confidence_for_surfacing` as the single decision point.

---

## Part 3: What the Docs Make Clearer

**The three-stage output is explicit**
The spec locks the final routing outcomes to: `no commitment / observe only / commitment`. The current code has no explicit routing step — detection results flow directly to commitment creation. The "observe only" path (track silently without surfacing) needs to be a first-class outcome, not just a side effect of low confidence.

**Quoted history rule is now locked**
"Do not create candidates from quoted text" is explicit for the first time. This should be enforced at the normalizer level, not left to the LLM to figure out.

**Speech act as the primary classification**
More useful than `CommitmentType` for filtering and surfacing. A `request` that was never accepted should behave differently from a `self_commitment`. The current system can't make that distinction.

**Completion evidence has strength bands**
The Completion Detection Brief defines strong/medium/weak evidence bands clearly. The existing scorer has similar logic but it's implicit — the spec makes it explicit and auditable.

**Clarification is rare and well-timed**
The Clarification Brief gives clear rules: clarification happens *after* candidate detection and preliminary resolution, not during extraction. The current clarification service fires too early in some paths.

**The three-party model**
Owner / requester / beneficiary as distinct fields is a cleaner model than the current single-counterparty approach. Especially important for commitment filtering (should I see this? am I the owner, or just the person who was asked?).

---

## Part 4: Recommended Actions

### Approve for Work Orders:

**WO-1: Commit the spec docs to the repo**
Move `ops/signal-and-commitment-processing/` into git. These docs should be version-controlled alongside the code they describe. Low effort, high value.

**WO-2: NormalizedSignal contract (CRITICAL)**
Create a shared `NormalizedSignal` dataclass. Update email, Slack, and meeting connectors to output this object before hitting detection. This unblocks WO-3 and WO-4 and is a prerequisite for proper quoted-text handling.
- Scope: 3 connectors + shared dataclass + detection service update
- Risk: Medium (touching connectors, but additive not breaking)

**WO-3: Email quoted-text stripping (HIGH)**
Update the email normalizer to isolate only the latest authored block. Store quoted history separately as `prior_context_text`. This reduces false positives significantly without touching the detection prompt.
- Scope: `email/normalizer.py` + IMAP poller
- Depends on: WO-2 (or can be done in parallel as a preparatory step)

**WO-4: Speech act classification (HIGH)**
Add `speech_act` as a new field to `CommitmentCandidate`. Update the detection prompt (v5) to classify one of the 9 speech acts. Update filtering and surfacing logic to treat `request` differently from `self_commitment`.
- Scope: migration + prompt update + surfacing logic
- Risk: Medium (prompt change + schema change)

**WO-5: Requester + beneficiary fields (MEDIUM)**
Add `requester_party_id` and `beneficiary_party_id` to commitments schema. Update detection prompt to populate them. Update `user_relationship` logic to use all three parties.
- Scope: migration + prompt + identity resolution
- Depends on: WO-4 (can be bundled into same migration)

**WO-6: Lifecycle state alignment (MEDIUM)**
Add `in_progress` and `canceled` states. Clarify `completed` vs `closed` semantics. Document that `confirmed` maps to `active` behavior, `dormant` and `needs_clarification` stay.
- Scope: enum migration + transition logic update
- Risk: Low (additive)

### Defer (backlog):

**Backlog: Slack thread enrichment**
Complex, not blocking. Requires event ordering, thread linking, and signal-to-commitment matching. Add to backlog after WO-2 lands.

**Backlog: `due_precision` field**
Nice-to-have for UX ("due this week" vs "due Friday 3pm"). Not blocking any core functionality. Add to backlog.

**Backlog: Meeting processing spec**
Can't implement until the doc is written. Flag for Kevin to complete.

---

## Summary

| Area | Status | Action |
|------|--------|--------|
| NormalizedSignal contract | ❌ Missing | WO-2 |
| Speech act classification | ❌ Missing | WO-4 |
| Requester/beneficiary | ❌ Missing | WO-5 |
| Email quoted-text stripping | ❌ Not enforced | WO-3 |
| Lifecycle in_progress/canceled | ❌ Missing | WO-6 |
| Completion detection | ✅ Exists | No action |
| Ambiguity/clarification types | ✅ Exists | No action |
| Signal roles | ✅ Exists | WO-1 (docs only) |
| Slack connector | ✅ Partial | Backlog |
| Meeting processing spec | ⚠️ Doc blank | Kevin to write |
| due_precision | ⚠️ Missing | Backlog |
| Spec docs in git | ❌ Not committed | WO-1 |
