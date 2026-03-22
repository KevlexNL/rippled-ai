# Decision Log

Key architectural and product decisions, with rationale.

---

## 2026-03-22 — Shared NormalizedSignal contract

**Decision:** All connectors must output a `NormalizedSignal` before detection.  
**Why:** Connectors were producing structurally different inputs. Detection improvements required applying the same change in 3 places. With a shared contract they apply once.  
**Source:** WO-RIPPLED-NORMALIZED-SIGNAL-CONTRACT

---

## 2026-03-22 — Speech act as primary classification

**Decision:** Add `speech_act` field with 9 values (request, self_commitment, acceptance...).  
**Why:** `CommitmentType` (send, review, deliver) classifies what the deliverable is, not what the speaker is doing. Can't distinguish "Kevin asked Matt" from "Kevin committed to." Root cause of many false positives.  
**Source:** WO-RIPPLED-SPEECH-ACT-CLASSIFICATION

---

## 2026-03-19 — Commitment domain policy

**Decision:** Locked 6 product decisions governing requests vs commitments, delegation, schedule actions, minimum structure, clarification defaults, and completion linking.  
**Source:** `ops/COMMITMENT_DOMAIN_POLICY.md`

---

## 2026-03-18 — Dormant ≠ dismissed

**Decision:** Dismiss should not permanently remove a commitment. Introduced `dormant` state ("not now but real") vs `discarded` ("wrong/noise").  
**Why:** Users lose real commitments if dismiss is destructive. Dormant enables silent tracking with future resurfacing.

---

## 2026-03-18 — User identity profile system

**Decision:** Created `user_identity_profiles` table mapping name/email aliases to user_id. Ownership resolution uses fuzzy matching against confirmed profiles.  
**Why:** `suggested_owner = "Kevin Beeftink"` had no way to resolve to `user_id`. The "My commitments" filter showed nothing.

---

## 2026-03-18 — mine / contributing / watching relationship model

**Decision:** Three relationship types instead of RACI.  
**Why:** RACI is corporate overhead. For a single-user tool, the only question is "does this require action from me?" Three values answer that cleanly.

---

## 2026-03-17 — Subscription over API key

**Decision:** All agents run on Anthropic Max subscription, not API key.  
**Why:** API key billing was ~$5/day. Subscription eliminates most of that cost for the same models.  
**How:** Keymaker set `agents.defaults.auth: "anthropic:subscription"`. ANTHROPIC_API_KEY removed from `.env`.

---

## 2026-03-17 — Rippled is single-user, not team

**Decision:** Rippled is built for one user's scope. Multi-user adds complexity that explodes.  
**Why:** If AI works for User A and User B in the same system, they can start making assumptions on each other's behalf. It gets messy. The value prop for one user is already strong.  
**Quote:** "The complexity explodes because now I have AI working for me, working for another person." — Kevin, 2026-03-17

---

## 2026-03-01 — Small business operators as ICP

**Decision:** Target hustle-mentality operators, not corporate teams.  
**Why:** Corporate environments have built-in loop-closing infrastructure (staff, systems, budget). Small businesses don't. That's where the forgetting happens.
