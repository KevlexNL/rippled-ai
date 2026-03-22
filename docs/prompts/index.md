# Prompts

All LLM prompts used in Rippled, versioned and documented.

## Governance

Changes to any prompt require:
1. A version bump in the code
2. `[prompt-change]` in the git commit message
3. A new snapshot file in `ops/prompts/`
4. Kevin notified with: what changed, why, expected impact

Kevin can veto any prompt change. It's rolled back immediately.

**Changes requiring Kevin's approval:**
- What counts as a commitment (the definition)
- Confidence thresholds
- Output field additions or removals
- Canonical structure format

**Changes Mero can approve:**
- New exclusion examples (greetings, pleasantries)
- Minor wording that doesn't change behaviour
- Bug fixes for clearly wrong extractions

Source: `ops/prompts/PROMPT_GOVERNANCE.md`

---

## Active Prompts

| Prompt | Version | Location | Purpose |
|--------|---------|----------|---------|
| Detection | `ongoing-v4` | [View](detection-v4.md) | Real-time single commitment extraction |
| Seed | `seed-v3` | [View](seed-v3.md) | Bulk extraction over full email bodies |
| Judge | `judge-v1` | [View](judge.md) | Weekly quality review and scoring |
| Eval | `seed-v1` | Eval harness only | Regression testing (historical) |

---

## Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| ongoing-v1 | ~2026-03-09 | Trinity | Initial extraction prompt |
| ongoing-v2 | ~2026-03-13 | Trinity | Added confidence scoring |
| ongoing-v3 | ~2026-03-17 | Trinity | Added canonical structure enforcement |
| ongoing-v4 | 2026-03-18 | Trinity | Greeting exclusions, follow-up patterns, user_relationship, structure_complete |
| seed-v1 | ~2026-03-09 | Trinity | Initial bulk extraction |
| seed-v2 | ~2026-03-13 | Trinity | Confidence + urgency fields |
| seed-v3 | 2026-03-18 | Trinity | Greeting exclusions, follow-up patterns |
