# Rippled — Commitment Domain Policy

**Status:** DRAFT — for Kevin's review and correction  
**Date:** 2026-03-19  
**Purpose:** Resolve the product decisions that must be explicit before ontology unification begins. These answers shape prompt design, schema, surfacing logic, and lifecycle behavior. Trinity works from this doc.

---

## 1. When does a request become a commitment?

**Decision:** A request becomes a commitment only when ownership is explicitly or implicitly accepted by the assignee.

- "Can you send me the report?" → **request** (not a commitment)
- "Can you send me the report?" + "Sure, I'll send it over today." → **commitment** (the reply creates it)
- "John to review before EOD" in a meeting → **commitment** if John is the speaker or clearly assigned; **request** if it's aspirational from someone else

**Rule for the model:** Extract the signal. Classify as `requested_action` if ownership is not accepted. Promote to `self_commitment` or `delegated_action` only when acceptance is explicit or strongly implied.

**Implication:** Requests without acceptance are tracked (`watching`) but not surfaced to the user by default.

---

## 2. Are delegated asks first-class signals before acceptance?

**Decision:** Yes — delegated asks are tracked from the moment of delegation, not only when accepted.

**Rationale:** In small business environments, tasks are often delegated without a formal acceptance loop. If Rippled only tracks commitments after acceptance, it will miss most real-world delegation patterns.

**Lifecycle:** Delegated asks start as `proposed`. If acceptance is later detected → promote to confirmed commitment. If no acceptance detected within observation window → surface for user triage.

**Rule for the model:** Extract delegations as `delegated_action` signal type. Mark `user_relationship` as:
- `mine` if the user is the one delegating AND cares about the outcome
- `watching` if a third party is delegating to another third party
- `contributing` if the user is one of multiple assignees

---

## 3. Are schedule actions part of the same commitment family, or separate?

**Decision:** Schedule actions are a separate signal family — tracked but not treated as deliverable commitments.

**Rationale:** "Let's meet Tuesday" is coordination, not a promise to deliver something. It has different lifecycle behavior: it resolves when the meeting happens (or doesn't), not when a deliverable is sent.

**Classification:** `schedule_action` signal type. Stored, observable, but:
- Not surfaced in Active tab
- Not surfaced in Commitments tab by default
- Accessible via "All commitments"
- Auto-closes when the scheduled time passes (regardless of whether meeting happened)

**Exception:** If a scheduled action carries an embedded commitment ("Let's meet Tuesday to review the proposal I'm sending you beforehand"), extract the embedded commitment separately.

---

## 4. What minimum structure is required to surface a signal?

**Decision:** To be surfaced (Active or Commitments tab), a signal must have at minimum:
- **owner** — resolved or strongly suggested
- **deliverable** — what was promised (even if vague)

Counterparty and deadline are desirable but not required for surfacing.

**If structure is incomplete:**
- `owner` missing → hold in triage, classify as `watching` or unowned
- `deliverable` missing → hold in triage, do not surface
- `counterparty` missing → surface with lower confidence, mark as incomplete
- `deadline` missing → surface, no deadline shown

**`structure_complete = true`** requires all three: owner + deliverable + counterparty.  
**Surfaceable but incomplete** = owner + deliverable present, counterparty missing.

---

## 5. When does incomplete structure trigger clarification vs silent observation?

**Decision:** Default to silent observation. Clarification is opt-in, not automatic.

**Rationale:** Rippled's value is cognitive load *reduction*. Prompting the user to clarify every incomplete signal would recreate the problem it's trying to solve.

**Rules:**
- Incomplete signal + high confidence (>0.75) + `mine` → surface with "Source only, details unclear" note
- Incomplete signal + medium confidence (0.5–0.75) → silent observation, resurface after 7 days if still open
- Incomplete signal + low confidence (<0.5) → silent observation, never auto-surface
- User explicitly reviews a commitment → clarification prompt is appropriate at that moment (not proactively)

**Future:** Clarification flow (asking the user "did you mean X?") is a Phase 2 feature, not MVP.

---

## 6. How do completion signals attach to prior open commitments?

**Decision:** Completion signals are detected separately, then matched against open commitments by thread/conversation context and semantic similarity.

**Matching logic (in priority order):**
1. **Thread match** — completion signal in same email thread / Slack thread as the original commitment → high confidence match
2. **Semantic match** — deliverable text similarity above threshold → medium confidence match
3. **Manual match** — user confirms "this closed commitment X" via UI → explicit match

**On match:**
- Open commitment transitions to `delivered` state
- If user confirms delivery → transitions to `closed`
- If no match found → completion signal stored as `completion_evidence` type, held for triage

**`delivered` vs `closed` distinction:**
- `delivered` = the action was taken / thing was sent / handoff made (system detected)
- `closed` = the obligation no longer requires attention (user confirmed or auto-closed after review period)

These are distinct because delivery can be detected automatically, but closure is a judgment call that should involve the user (at least initially).

---

## Summary Table

| Decision | Answer |
|----------|--------|
| When is a request a commitment? | When ownership is accepted (explicitly or implicitly) |
| Are delegated asks tracked before acceptance? | Yes — as `delegated_action`, promoted on acceptance |
| Are schedule actions commitments? | No — separate `schedule_action` family, different lifecycle |
| Minimum structure to surface? | Owner + deliverable required; counterparty desirable |
| Incomplete structure → clarification or silent? | Silent by default; clarification only when user actively reviews |
| How do completion signals attach? | Thread match → semantic match → manual; delivered ≠ closed |

---

## What This Means for the Canonical Schema

Based on these decisions, every signal object needs:

```json
{
  "signal_type": "self_commitment | delegated_action | requested_action | follow_up_intent | schedule_action | completion_evidence | status_update_only | non_commitment",
  "owner": { "value": "...", "confidence": 0.0, "source": "explicit|inferred|unknown" },
  "deliverable": { "value": "...", "confidence": 0.0, "source": "explicit|inferred|unknown" },
  "counterparty": { "value": "...", "confidence": 0.0, "source": "explicit|inferred|unknown" },
  "deadline": { "value": "...", "normalized": null, "confidence": 0.0, "source": "explicit|relative|inferred|unknown" },
  "user_relationship": "mine | contributing | watching",
  "structure_complete": true | false,
  "surfaceable": true | false,
  "needs_clarification": false,
  "clarification_reasons": [],
  "evidence_text": "exact span that triggered detection",
  "linked_commitment_id": null
}
```

This schema applies to **both seed and real-time flows**. The seed pass returns an array of these objects. The real-time flow returns one. Same shape, same fields, same contracts.

---

## Open Questions (not yet decided)

- [ ] Should `requested_action` signals be surfaced to the user at all? Or only tracked silently until acceptance?
- [ ] What is the observation window for delegated asks with no acceptance signal? (7 days? 14 days?)
- [ ] Should schedule actions auto-close after the scheduled time, or require user confirmation?
- [ ] At what confidence threshold does a `completion_evidence` signal trigger auto-delivery vs triage?

**Kevin to answer these — they are not blocking the schema work but will shape surfacing behavior.**
