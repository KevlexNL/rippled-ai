# ChatGPT Brief vs Current Rippled Architecture — Gap Analysis

**Date:** 2026-03-19  
**Author:** Mero  
**Source brief:** rippled_prompt_and_architecture_brief (ChatGPT)  
**Purpose:** Evaluate ChatGPT's recommendations against what Rippled actually has today. Identify what's already done, what's partially done, and what's genuinely missing.

---

## TL;DR

The brief is directionally correct and well-structured. **Much of what it recommends already exists in Rippled's data model** — often more completely than the brief assumed. The real gaps are at the prompt layer and evaluation layer, not the schema layer. The most valuable recommendations are:
1. Split detection from extraction (staged pipeline)
2. Source-specific prompt overlays
3. Upgraded judge with failure taxonomy
4. Completion/closure detection as a separate stage

---

## What Already Exists (Better Than The Brief Assumes)

### Field-level confidence ✅ (already in schema)
The brief recommends storing confidence per field (owner, deliverable, counterparty, deadline). Rippled already has:
- `confidence_commitment`
- `confidence_owner`
- `confidence_deadline`
- `confidence_delivery`
- `confidence_closure`
- `confidence_actionability`
- `confidence_for_surfacing`

**Verdict:** Already done. No action needed here.

### Source type awareness ✅ (already in schema)
The brief recommends source-specific overlays for email, Slack, meetings. The `source_items` table already tracks `source_type` (email / slack / meeting). Connectors exist for all three. Currently only email is in use.

**Verdict:** Infrastructure exists. What's missing is source-specific prompt overlays — the prompts currently treat all sources the same.

### Lifecycle states ✅ (partially)
Current enum: `proposed`, `discarded`, `dormant`, `confirmed`, `completed`, `dismissed` (dormant and confirmed added 2026-03-18). The brief also wants `delivered` and `closed` as distinct states.

**Verdict:** Mostly covered. The `delivered` / `closed` distinction is the one gap.

### Scoring fields ✅ (already in schema)
The brief recommends moving urgency/prioritization out of prompts and into app logic. Rippled already has:
- `priority_score`
- `timing_strength`
- `business_consequence`
- `cognitive_burden`
- `priority_class` (small_commitment / big_promise)

**Verdict:** The architecture is right. The prompts still include some product-level fields (urgency in seed-v3) that should be removed.

### Counterparty / user relationship ✅ (just added)
The brief recommends `counterparty`, `user_relationship` (mine/contributing/watching). Both were added in v4 (2026-03-18).

**Verdict:** Done.

### Structure completeness ✅ (just added)
The brief recommends `structure_complete` to preserve incomplete-but-useful candidates. Added in v4.

**Verdict:** Done.

### Evidence text / trigger phrase ✅ (partial)
The seed prompt already extracts `trigger_phrase` (the exact words that triggered detection). The real-time prompt does not capture `evidence_text`. The `detection_audit` table stores `matched_phrase`.

**Verdict:** Partially there. Evidence text is in seed pass and audit, not in the canonical commitment object.

### Lifecycle transitions ✅ (exists)
`lifecycle_transition` table exists, tracks `from_state` / `to_state` with timestamp.

**Verdict:** Done.

---

## What's Genuinely Missing (Real Gaps)

### ❌ Schema mismatch between real-time and seed prompts (HIGH PRIORITY)
This is the most important finding in the brief and it's correct.

- **Seed prompt (seed-v3)** extracts: `trigger_phrase`, `who_committed`, `directed_at`, `urgency`, `commitment_type`, `title`, `is_external`, `confidence`
- **Real-time prompt (ongoing-v4)** extracts: `owner`, `deliverable`, `counterparty`, `deadline`, `user_relationship`, `structure_complete`, `confidence`

These are fundamentally different objects. You cannot reliably compare, deduplicate, or evaluate across them. The eval harness (`seed-v1`) uses a third schema.

**Action:** Unify to one canonical signal schema. Seed pass should produce the same object shape as real-time, just in an array.

---

### ❌ No signal_type classification (MEDIUM PRIORITY)
The brief recommends classifying signals into: `self_commitment`, `delegated_action`, `requested_action`, `follow_up_intent`, `schedule_action`, `completion_evidence`, `status_update_only`, `non_commitment`.

Currently Rippled has `commitment_type` (send, review, follow_up, deliver, etc.) which is a verb taxonomy, not a semantic classification. It doesn't distinguish between "Kevin committed to do X" vs "Kevin asked Matt to do X" — both would land as commitments right now.

**Action:** Add `signal_type` to the schema and extraction prompt. This is the biggest product-quality improvement available.

---

### ❌ Staged pipeline: detection → extraction not implemented (MEDIUM PRIORITY)
Currently detection and extraction happen in one LLM call. The brief is right that this creates false negatives: if the model can't fill all fields confidently, it may reject a real commitment rather than preserve it as incomplete.

The proposed fix: separate "is this a commitment candidate?" from "extract the full structure." Stage 1 casts a wide net, Stage 2 fills in the details.

**Caveat:** This doubles LLM calls per source item. Cost implication is real. Worth piloting on the seed pass first before applying to real-time flow.

**Action:** Pilot staged pipeline on seed pass. Evaluate whether recall improves enough to justify cost.

---

### ❌ No source-specific prompt overlays (MEDIUM PRIORITY)
All sources (email, Slack, meeting transcripts) currently use the same prompt. The brief is right that they behave differently:
- Email: quoted/forwarded history should not generate new commitments
- Slack: "on it" is only meaningful in thread context
- Meetings: shorthand end-of-meeting action items need different treatment

**Action:** Add compact source-specific overlays injected into the base prompt based on `source_type`. Email first (that's all we have), Slack and meeting when those come online.

---

### ❌ No completion/closure detection (MEDIUM PRIORITY)
If someone sends "Done" or "Sent above" in reply to a thread, Rippled currently either ignores it or creates a new commitment. There is no mechanism to match it against an existing open commitment and mark it delivered.

This is a lifecycle problem that needs a separate detection stage: "does this message indicate an existing commitment has been fulfilled?"

**Action:** Separate WO for completion detection. Requires commitment context to be passed alongside the new message.

---

### ❌ LLM judge lacks failure taxonomy (LOW-MEDIUM PRIORITY)
Current judge prompt asks for: misses, false positives, quality score 1-5, one suggestion. The brief recommends classifying failures by type:
- `implicit_commitment_missed`
- `request_vs_commitment_confusion`
- `quoted_text_contamination`
- `owner_resolution_error`
- etc.

This is valuable for systematic improvement but not urgent. The judge already produces useful signal.

**Action:** Upgrade judge prompt to v2 with failure taxonomy. Lower priority — do after schema unification.

---

### ❌ Urgency still in seed prompt (LOW PRIORITY)
`seed-v3` still asks the LLM to rate urgency (high/medium/low). The brief is right that urgency is a product-level output, not a first-order extraction truth. It should be computed from extracted fields (deadline proximity, confidence, business consequence) not guessed by the LLM.

**Action:** Remove urgency from seed prompt in next version. Use existing `timing_strength` + `business_consequence` scoring fields instead.

---

## Decisions the Brief Says Should Be Made First

These are the 7 product decisions the brief recommends making before refactoring anything. Current answers where known:

| Decision | Current State |
|----------|--------------|
| Are delegated asks first-class commitments, or only once accepted? | **Unclear** — seed prompt treats delegations as commitments. Real-time prompt doesn't distinguish. Needs a decision. |
| Are schedule actions treated as commitments or a separate family? | **Unclear** — "Let's meet Tuesday" would currently be extracted as a commitment. Probably should be separate. |
| How should incomplete but high-probability commitments be surfaced? | **Partially decided** — `structure_complete=false` holds them from surfacing. But no clarification flow exists yet. |
| What minimum structure is required for a user-visible signal? | **Not explicit** — currently threshold is confidence_for_surfacing > some value. Not tied to structure quality. |
| What confidence thresholds differ by signal type and channel? | **Not implemented** — single threshold applies to all. |
| What is the lifecycle distinction between delivered and closed? | **Not implemented** — both would currently be `completed`. Need separate states. |
| How should completion evidence link to prior commitments? | **Not implemented** — no completion detection exists. |

---

## Recommended Implementation Sequence (adjusted for Rippled's current state)

Given what already exists, the priority order is:

1. **Unify ontology** — make seed and real-time prompts produce the same schema. Highest leverage, prerequisite for everything else.

2. **Add signal_type** — self_commitment vs delegated vs request is a product-quality unlock. Affects filtering, surfacing, and user experience immediately.

3. **Source overlays** — email first. Add quoted-text protection and email-specific handling. Slack/meeting can wait until those sources are live.

4. **Staged pipeline (seed pass only)** — pilot on seed. If recall improves, extend to real-time.

5. **Completion detection** — separate stage. Medium complexity, high value once more source items are in the system.

6. **Judge upgrade** — failure taxonomy. Lower priority, do after schema is stable.

7. **Urgency removal from prompts** — quick win, low risk.

---

## What the Brief Gets Wrong (or overstates)

- **The schema gap is smaller than it appears.** The brief suggests the data model needs a major overhaul. In reality, `commitments` already has most proposed fields (field-level confidence, lifecycle transitions, scoring fields, counterparty, user_relationship). The real gap is prompt-to-schema alignment, not schema design.

- **Two-stage LLM pipeline has a cost.** The brief doesn't mention that splitting detection from extraction doubles API calls. At scale this is non-trivial. Worth validating on seed pass before committing to it everywhere.

- **Eval harness (seed-v1) is already isolated.** The brief treats this as a live concern. It's only used for regression testing, not production. Lower urgency than implied.

---

## Bottom Line

The brief is a good external sanity check. It validates the architecture direction and correctly identifies the real weak spots. The most actionable recommendation is **ontology unification** — getting the seed and real-time prompts to produce the same schema. Everything else builds on that.

None of this requires throwing away what exists. It's evolution, not a rewrite.
