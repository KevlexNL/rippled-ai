# Rippled Prompt Governance

**Owner:** Kevin Beeftink (final approval on all prompt changes)
**PM:** Mero (reviews changes, notifies Kevin)
**Developer:** Trinity (proposes changes via WO, must flag in commit message)

---

## Rule: No silent prompt changes

Every prompt change must:
1. Bump the version in `model_detection.py` (e.g. `ongoing-v4` → `ongoing-v5`)
2. Include `[prompt-change]` in the git commit message
3. Update `ops/prompts/detection-prompt-vX.md` with the new version
4. Mero notifies Kevin with: current version, what changed, why

Kevin can veto any prompt change. Rolled back immediately if vetoed.

---

## Active Prompt Registry

| Version | Date | Author | Summary of Change |
|---------|------|--------|------------------|
| v1 | ~2026-03-09 | Trinity | Initial extraction prompt |
| v2 | ~2026-03-13 | Trinity | Added confidence scoring |
| v3 | ~2026-03-17 | Trinity | Added canonical structure enforcement ([Owner] promised [Deliverable] to [Counterparty]) |
| v4 | 2026-03-18 | Trinity | Added greeting/pleasantry exclusions, bare follow-up patterns, user_relationship field |
| v5 | 2026-03-19 | Trinity | Strengthened follow-up topic examples, checking-in-on pattern, classification label exclusions |
| v6 | 2026-03-20 | Trinity | Self-validation step, critical follow-up rule, judge quality rubric (WO-RIPPLED-PROMPT-IMPROVEMENT) |
| v7 (current) | 2026-03-22 | Trinity | Added speech_act classification field — ongoing-v9, seed-v8 (WO-RIPPLED-SPEECH-ACT-CLASSIFICATION) |

---

## Current Active Prompt: ongoing-v9 / seed-v8

File: `ops/prompts/detection-prompt-v7.md`

---

## How to Propose a Prompt Change (Trinity)

1. Write a WO or note describing: what to change, why, expected impact
2. Mero reviews — approves or escalates to Kevin
3. If approved: implement, bump version, update this registry, commit with `[prompt-change]`
4. Mero notifies Kevin same day

**Changes that always require Kevin's approval:**
- Changing what counts as a commitment (the definition)
- Changing confidence thresholds
- Changing the canonical structure format
- Adding/removing output fields

**Changes Mero can approve without Kevin:**
- Adding exclusion examples (e.g. new greeting patterns)
- Minor wording improvements that don't change behavior
- Bug fixes where a clearly wrong extraction is being corrected
