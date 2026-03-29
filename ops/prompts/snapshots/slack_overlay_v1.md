# Prompt Snapshot: slack_overlay_v1

**Version:** slack_overlay_v1
**Date created:** 2026-03-29
**Module:** `app/services/orchestration/prompts/slack_overlay.py`

---

## System Addendum

Appended to the base system prompt for all stages when `source_type == "slack"`.

```
SLACK_CONTEXT:
You are analyzing a Slack message. Slack uses informal language. Apply these rules:

STRONG commitment signals:
- "will do", "on it", "I'll handle", "@mention + task" -> treat as commitment candidate
- Thumbs up emoji (👍), check mark (✅) in reply to a request -> likely acceptance
- Thread reply that directly responds to a question with affirmation -> higher confidence

NOT commitments (false positive guards):
- "lmk", "let me know", "can you..." -> these are REQUESTS, not commitments
- "sounds good" alone without context -> acknowledgement only, not a commitment
- Emoji-only replies with no text -> low confidence, do not promote
- Casual reactions like "haha", "nice", "👏" -> social, not commitments

Channel context hints:
- DM message -> personal commitment, higher ownership confidence
- Public channel with @mention -> may be delegation, adjust owner_resolution accordingly
- Thread reply -> context comes from parent message (provided in prior_context_text)
```

## Extraction Hints

Appended to user prompt in the extraction stage for Slack signals.

```
Note: This is a Slack message. Use prior_context_text (thread parent) to understand the full request before determining commitment ownership.
```

**Rationale:** Slack thread replies are often terse ("will do") — the actual task context lives in the parent message. Without this hint, the model may fail to resolve ownership or deliverable from the reply alone.

## Speech Act Hints

Appended to user prompt in the speech-act classification stage for Slack signals.

```
Note: Slack shorthand like 'will do', 'on it', 'yep' in reply to a task request should be classified as COMMIT. Casual reactions should be classified as OTHER.
```

**Rationale:** The base speech-act classifier is trained on formal email/meeting text. Slack shorthand like "on it" is ambiguous without explicit guidance — it could be classified as `information` or `unclear` instead of `acceptance`/`self_commitment`.

## Guidance Rule Rationale

| Rule | Rationale |
|------|-----------|
| "will do"/"on it" = commitment | These are the most common Slack acceptance patterns, consistently missed by the base prompt |
| 👍/✅ in reply to request = acceptance | Emoji-as-reply is Slack-native behavior — the base prompt has no emoji handling |
| "lmk"/"can you" = request, not commitment | High false-positive source — these are asks, not acceptances |
| "sounds good" alone = not commitment | Without follow-up action language, this is social acknowledgement |
| Emoji-only = low confidence | Too ambiguous to promote without text context |
| DM = higher ownership | DMs imply personal accountability (no audience diffusion) |
| @mention + task = delegation signal | Explicit mention with action language is a strong delegation pattern in Slack |
| Thread reply context | Thread parent provides the request; reply provides the acceptance — both are needed |
