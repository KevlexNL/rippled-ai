# WO-RIPPLED-SLACK-SPECIFIC-PROMPT-OVERLAY

**Status:** PENDING
**Priority:** High
**Owner:** Trinity
**Created:** 2026-03-29
**Scope:** Rippled codebase — LLM prompt layer for Slack signals

---

## Objective

Develop a Slack-specific prompt overlay that guides the LLM's interpretation of Slack signals, addressing the unique communication patterns of Slack (implicit language, emoji, thread context, informal shorthand) to improve commitment detection accuracy.

---

## Context

Slack communication is fundamentally different from email and meeting transcripts:
- Heavy use of informal shorthand ("will do", "👍", "on it", "lmk")
- Commitments often implicit, buried in casual conversation
- Thread replies are responses to specific requests — context is essential
- Emoji reactions can signal acceptance or completion
- Channel context matters (e.g. #general vs #engineering vs #client-name)

The current LLM prompt is tuned for email/meeting patterns. A Slack overlay ensures the model interprets Slack signals correctly without degrading email/meeting detection.

---

## Research Phase (Required First)

1. Review current prompt system at `app/services/detection/` — understand how prompts are structured and how source type is passed
2. Review `WO-RIPPLED-LLM-ORCHESTRATION` implementation — confirm how the staged pipeline allows source-specific prompt injection
3. Sample 10–20 real Slack `NormalizedSignal` objects from the DB — identify the most common false positive/negative patterns
4. Document findings before writing any prompt content

---

## Phases

### Phase 1 — Prompt Overlay Structure
- Create `app/services/detection/prompts/slack_overlay.py`
- Define a `SlackPromptOverlay` class with:
  - `system_addendum` — extra context appended to base system prompt for Slack signals
  - `extraction_hints` — Slack-specific extraction guidance (how to handle emoji, shorthand, threads)
  - `false_positive_guards` — patterns to explicitly NOT treat as commitments (casual reactions, social messages)

### Phase 2 — Slack-Specific Guidance Content

**Include guidance for:**
- `👍`, `✅`, `will do`, `on it`, `noted` → likely acceptance of a request → track as commitment candidate
- `lmk`, `let me know` → NOT a commitment — it's a request for follow-up
- `sounds good` alone → NOT a commitment — acknowledgement only
- Thread reply to a direct question → higher probability of commitment/acceptance
- Emoji-only replies → low confidence, observe silently
- `@mention` + task description → stronger ownership signal
- Channel type inference: DM → personal commitment; public channel → may be delegation

### Phase 3 — Integration with Detection Pipeline
- In `app/services/detection/orchestrator.py` (or equivalent): detect `source_type == "slack"` and inject `SlackPromptOverlay` before LLM call
- Ensure overlay is additive (appended to base prompt, not replacing it)
- Version the overlay: `slack_overlay_v1`
- Follow prompt governance rules: version bump + `[prompt-change]` in commit + new snapshot file + notify Mero

### Phase 4 — Evaluation
- Run detection on 20 sampled Slack signals with and without overlay
- Compare: false positive rate, false negative rate, confidence scores
- Document results in `ops/research/slack-prompt-overlay-eval.md`

---

## Success Criteria

- [ ] `SlackPromptOverlay` implemented and integrated into detection pipeline
- [ ] Prompt versioned as `slack_overlay_v1` with snapshot file
- [ ] Evaluation doc written with before/after comparison
- [ ] No regression on email/meeting detection (run existing test suite)
- [ ] Prompt governance rules followed (commit tagged `[prompt-change]`)

---

## Files to Create/Modify

- `app/services/detection/prompts/slack_overlay.py` — new overlay
- `app/services/detection/orchestrator.py` — integrate overlay
- `ops/prompts/snapshots/slack_overlay_v1.md` — snapshot
- `ops/research/slack-prompt-overlay-eval.md` — evaluation results

---

## Dependencies

- `WO-RIPPLED-SLACK-THREAD-ENRICHMENT` (must be complete first — overlay needs thread context in signals)
- `WO-RIPPLED-LLM-ORCHESTRATION` (completed)

---

## Notify When Done

Mero + Kevin via Rippled Telegram group
