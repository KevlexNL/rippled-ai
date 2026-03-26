"""Prompt template for Stage 3 — Commitment field extraction."""

TEMPLATE_ID = "commitment_extractor"
TEMPLATE_VERSION = "v1.0.0"

SYSTEM_PROMPT = """\
You are a commitment field extractor. Given a business message that likely \
contains a commitment or action item, extract the structured fields.

You must respond with ONLY valid JSON matching this schema:
{
  "candidate_present": <bool>,
  "owner_text": "<who is committing>" | null,
  "owner_resolution": "sender" | "recipient" | "third_party" | "unknown" | "not_applicable",
  "deliverable_text": "<what is being committed to>" | null,
  "timing_text": "<when>" | null,
  "target_text": "<who benefits or receives>" | null,
  "evidence_span": "<exact quote from the text>" | null,
  "evidence_source": "latest_authored_text" | "prior_context_text" | "mixed" | "unknown",
  "owner_confidence": <float 0.0-1.0>,
  "deliverable_confidence": <float 0.0-1.0>,
  "timing_confidence": <float 0.0-1.0>,
  "target_confidence": <float 0.0-1.0>,
  "ambiguity_flags": [<list of string flags>],
  "rationale_short": "<1 sentence>"
}

CRITICAL RULES:
1. PRIORITIZE the latest authored text. Only reference prior context as supporting evidence.
2. If evidence comes from prior context, flag it in evidence_source and lower confidence.
3. Do NOT invent information not present in the text.
4. Do NOT transform vague timing ("soon", "next week") into exact timestamps.
5. Keep deliverable_text concise and specific.
6. If no commitment is present despite earlier stages suggesting one, set candidate_present=false.
7. owner_resolution maps the owner to their role: "sender" if the message author commits themselves, "recipient" if they're asking the reader, "third_party" if about someone else.
"""


def build_user_prompt(
    latest_authored_text: str,
    prior_context_text: str | None,
    source_type: str,
    subject: str | None,
    direction: str | None,
    speech_act: str,
    speech_act_confidence: float,
    candidate_type: str,
    participants: list[str] | None = None,
) -> str:
    parts = [
        f"Source type: {source_type}",
        f"Speech act: {speech_act} (confidence: {speech_act_confidence:.2f})",
        f"Candidate type: {candidate_type}",
    ]
    if subject:
        parts.append(f"Subject: {subject}")
    if direction:
        parts.append(f"Direction: {direction}")
    if source_type == "meeting" and participants:
        parts.append(f"Meeting participants: {', '.join(participants)}")
    parts.append(f"\n--- Latest authored text ---\n{latest_authored_text}")
    if prior_context_text:
        parts.append(f"\n--- Prior context (quoted/thread) ---\n{prior_context_text[:800]}")
    return "\n".join(parts)
