"""Slack-specific prompt overlay — WO-RIPPLED-SLACK-SPECIFIC-PROMPT-OVERLAY.

Appended to base prompts when source_type == "slack" to improve
commitment detection accuracy for Slack's informal communication style.
"""

VERSION = "slack_overlay_v1"

SYSTEM_ADDENDUM = """

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
"""

EXTRACTION_HINTS = (
    "Note: This is a Slack message. Use prior_context_text (thread parent) "
    "to understand the full request before determining commitment ownership."
)

SPEECH_ACT_HINTS = (
    "Note: Slack shorthand like 'will do', 'on it', 'yep' in reply to a task "
    "request should be classified as COMMIT. Casual reactions should be "
    "classified as OTHER."
)
