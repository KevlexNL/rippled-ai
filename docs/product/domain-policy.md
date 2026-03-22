# Commitment Domain Policy

Resolved product decisions that shape prompt design, schema, surfacing logic, and lifecycle behavior. These are locked. Changes require Kevin's approval.

Source: `ops/COMMITMENT_DOMAIN_POLICY.md`

---

## 1. When does a request become a commitment?

A request becomes a commitment only when ownership is **explicitly or implicitly accepted** by the assignee.

- "Can you send me the report?" → **request** (not a commitment)
- "Can you send me the report?" + "Sure, I'll send it over today." → **commitment**
- "John to review before EOD" → commitment if John is the speaker or clearly assigned; request if aspirational

Requests without acceptance are tracked (`watching`) but not surfaced to the user by default.

---

## 2. Are delegated asks tracked before acceptance?

**Yes.** Delegated asks are tracked from the moment of delegation.

In small business environments, tasks are often delegated without a formal acceptance loop. If Rippled only tracks commitments after acceptance, it will miss most real-world delegation patterns.

Delegated asks start as `proposed`. If acceptance is later detected → promoted to confirmed. If no acceptance within observation window → surfaced for triage.

---

## 3. Are schedule actions commitments?

**No.** Schedule actions are a separate signal family.

"Let's meet Tuesday" is coordination, not a delivery promise. It resolves when the meeting happens, not when a deliverable is sent.

Schedule actions:
- Not surfaced in Active or Commitments tab by default
- Accessible via "All commitments"
- Auto-close when scheduled time passes

Exception: if a scheduled action contains an embedded commitment ("I'll send the proposal before we meet Tuesday"), extract the embedded commitment separately.

---

## 4. Minimum structure required to surface

To appear in Active or Commitments tab, a commitment must have:
- **owner** — resolved or strongly suggested
- **deliverable** — what was promised (even if vague)

Counterparty and deadline are desirable but not required.

| Missing field | Behaviour |
|-------------|----------|
| owner | Hold in triage, do not surface |
| deliverable | Hold in triage, do not surface |
| counterparty | Surface with lower confidence, mark incomplete |
| deadline | Surface, no deadline shown |

---

## 5. Incomplete structure: clarification or silent observation?

**Default: silent observation.** Clarification is opt-in, not automatic.

Prompting the user to clarify every incomplete signal would recreate the cognitive load problem Rippled is solving.

Rules:
- High confidence + `mine` + incomplete → surface with "source only, details unclear" note
- Medium confidence → observe silently, resurface after 7 days if still open
- Low confidence → observe silently, never auto-surface
- User actively reviews a commitment → clarification is appropriate at that moment

---

## 6. How do completion signals link to prior commitments?

Matching order:
1. **Thread match** — same email thread / Slack thread → high confidence
2. **Semantic match** — deliverable text similarity above threshold → medium confidence
3. **Manual match** — user confirms via UI → explicit

On match: commitment → `delivered`. User confirms → `completed`.

**Delivered ≠ closed:**
- `delivered` = action taken, system-detected
- `closed` = obligation no longer needs attention, user-confirmed or auto-closed

---

## Open Questions (pending Kevin's answers)

- [ ] Should `requested_action` signals surface at all, or only track silently until accepted?
- [ ] Observation window for delegated asks with no acceptance: 7 days? 14 days?
- [ ] Should schedule actions auto-close after scheduled time, or require user confirmation?
- [ ] At what confidence threshold does completion evidence trigger auto-delivery vs triage?
