"""Prompt template for Stage 2 — Speech-act classification."""

from app.services.orchestration.prompts.slack_overlay import (
    SPEECH_ACT_HINTS,
    SYSTEM_ADDENDUM,
)

TEMPLATE_ID = "speech_act_classifier"
TEMPLATE_VERSION = "v1.1.0"

SYSTEM_PROMPT = """\
You are a speech-act classifier for business communications. Classify the \
communicative intent of the message.

You must respond with ONLY valid JSON matching this schema:
{
  "speech_act": "request" | "self_commitment" | "acceptance" | "delegation" | "update" | "completion" | "suggestion" | "information" | "deadline_change" | "collective_commitment" | "unclear",
  "confidence": <float 0.0-1.0>,
  "actor_hint": "sender" | "recipient" | "other" | "unclear",
  "target_hint": "sender" | "recipient" | "other" | "unclear",
  "rationale_short": "<1 sentence>",
  "ambiguity_flags": [<list of string flags>]
}

RULES:
- "request" = someone asking another to do something. A request is NOT automatically a commitment.
- "self_commitment" = the sender commits themselves to an action ("I will...", "I'll send...").
- "acceptance" = the sender agrees to a previously requested action. May imply commitment.
- "delegation" = the sender assigns a task to someone else.
- "update" = status report on ongoing work. An update is NOT the same as "completion".
- "completion" = explicit claim that something is done/delivered.
- "suggestion" = proposing an idea without committing.
- "information" = purely sharing facts, no action implied.
- "deadline_change" = a deadline or due date is being moved, rescheduled, or updated. Examples: \
"The deadline has moved to March 15th", "Can we push the deadline to next week?", \
"Rescheduling the delivery to Friday", "The due date has been extended to April 1st". \
This is NOT the same as "request" — a deadline change announces or proposes a new date for \
an existing commitment.
- "collective_commitment" = first-person plural phrasing where a group commits to action \
without a clear individual owner. Examples: "We need to schedule a call", "We should finalize \
the proposal", "We'll all need to review this before Friday". The key signal is "we" as the \
actor with no single person taking ownership. Flag "collective_we" in ambiguity_flags and set \
actor_hint to "unclear" when the individual owner cannot be determined.
- "unclear" = cannot determine intent.
- actor_hint: who is performing the action (sender, recipient, other, unclear).
- target_hint: who benefits from or receives the action.
- ambiguity_flags: note any ambiguities like "passive_voice", "conditional_language", "implicit_actor", "collective_we".
"""


def build_system_prompt(source_type: str) -> str:
    """Return the system prompt, with Slack addendum when applicable."""
    if source_type == "slack":
        return SYSTEM_PROMPT + SYSTEM_ADDENDUM
    return SYSTEM_PROMPT


def build_user_prompt(
    latest_authored_text: str,
    prior_context_text: str | None,
    source_type: str,
    subject: str | None,
    direction: str | None,
    candidate_type: str,
    gate_confidence: float,
    participants: list[str] | None = None,
) -> str:
    parts = [
        f"Source type: {source_type}",
        f"Candidate classification: {candidate_type} (confidence: {gate_confidence:.2f})",
    ]
    if subject:
        parts.append(f"Subject: {subject}")
    if direction:
        parts.append(f"Direction: {direction}")
    if source_type == "meeting" and participants:
        parts.append(f"Meeting participants: {', '.join(participants)}")
    parts.append(f"\n--- Latest authored text ---\n{latest_authored_text}")
    if prior_context_text:
        parts.append(f"\n--- Prior context (quoted/thread) ---\n{prior_context_text[:500]}")
    if source_type == "slack":
        parts.append(f"\n{SPEECH_ACT_HINTS}")
    return "\n".join(parts)
