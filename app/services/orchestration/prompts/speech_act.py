"""Prompt template for Stage 2 — Speech-act classification."""

TEMPLATE_ID = "speech_act_classifier"
TEMPLATE_VERSION = "v1.0.0"

SYSTEM_PROMPT = """\
You are a speech-act classifier for business communications. Classify the \
communicative intent of the message.

You must respond with ONLY valid JSON matching this schema:
{
  "speech_act": "request" | "self_commitment" | "acceptance" | "delegation" | "update" | "completion" | "suggestion" | "information" | "unclear",
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
- "unclear" = cannot determine intent.
- actor_hint: who is performing the action (sender, recipient, other, unclear).
- target_hint: who benefits from or receives the action.
- ambiguity_flags: note any ambiguities like "passive_voice", "conditional_language", "implicit_actor".
"""


def build_user_prompt(
    latest_authored_text: str,
    prior_context_text: str | None,
    source_type: str,
    subject: str | None,
    direction: str | None,
    candidate_type: str,
    gate_confidence: float,
) -> str:
    parts = [
        f"Source type: {source_type}",
        f"Candidate classification: {candidate_type} (confidence: {gate_confidence:.2f})",
    ]
    if subject:
        parts.append(f"Subject: {subject}")
    if direction:
        parts.append(f"Direction: {direction}")
    parts.append(f"\n--- Latest authored text ---\n{latest_authored_text}")
    if prior_context_text:
        parts.append(f"\n--- Prior context (quoted/thread) ---\n{prior_context_text[:500]}")
    return "\n".join(parts)
