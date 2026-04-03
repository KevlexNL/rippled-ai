"""Prompt template for Stage 5 — Escalation resolver."""

TEMPLATE_ID = "escalation_resolver"
TEMPLATE_VERSION = "v1.0.0"

SYSTEM_PROMPT = """\
You are a senior commitment analyst reviewing a message that the initial \
classification pipeline could not resolve with high confidence.

You will receive the original message and the outputs from prior pipeline stages. \
Your job is to resolve the specific uncertainties flagged.

You must respond with ONLY valid JSON matching this schema:
{
  "resolved": <bool>,
  "updated_gate": <CandidateGateResult or null>,
  "updated_speech_act": <SpeechActResult or null>,
  "updated_extraction": <CommitmentExtractionResult or null>,
  "confidence_delta": <float or null>,
  "rationale_short": "<explanation of what you resolved>"
}

Where CandidateGateResult = {"candidate_type": "none" | "commitment_candidate" | "completion_candidate" | "ambiguous_action_candidate", "confidence": float, "rationale_short": str, "escalate_recommended": false}
Where SpeechActResult = {"speech_act": "request" | "self_commitment" | "acceptance" | "delegation" | "update" | "completion" | "suggestion" | "information" | "deadline_change" | "collective_commitment" | "unclear", "confidence": float, "actor_hint": "sender" | "recipient" | "other" | "unclear", "target_hint": "sender" | "recipient" | "other" | "unclear", "rationale_short": str, "ambiguity_flags": []}
Where CommitmentExtractionResult = {"candidate_present": bool, "owner_text": str|null, "owner_resolution": str, "deliverable_text": str|null, "timing_text": str|null, "target_text": str|null, "evidence_span": str|null, "evidence_source": str, "owner_confidence": float, "deliverable_confidence": float, "timing_confidence": float, "target_confidence": float, "ambiguity_flags": [], "due_precision": "day"|"week"|"month"|"vague"|null, "rationale_short": str}

RULES:
- Only override stage outputs where you have HIGHER confidence.
- If you cannot resolve the ambiguity, set resolved=false and leave updated_* as null.
- Do not fabricate information not in the original text.
- Be conservative — observe_quietly is better than a false positive.
"""


def build_user_prompt(
    latest_authored_text: str,
    prior_context_text: str | None,
    source_type: str,
    subject: str | None,
    gate_output: dict,
    speech_act_output: dict | None,
    extraction_output: dict | None,
    uncertainty_questions: list[str],
) -> str:
    parts = [
        f"Source type: {source_type}",
        f"\n--- Latest authored text ---\n{latest_authored_text}",
    ]
    if prior_context_text:
        parts.append(f"\n--- Prior context ---\n{prior_context_text[:800]}")
    if subject:
        parts.append(f"Subject: {subject}")
    parts.append("\n--- Prior stage outputs ---")
    parts.append(f"Gate: {gate_output}")
    if speech_act_output:
        parts.append(f"Speech act: {speech_act_output}")
    if extraction_output:
        parts.append(f"Extraction: {extraction_output}")
    if uncertainty_questions:
        parts.append("\n--- Specific uncertainties to resolve ---")
        for q in uncertainty_questions:
            parts.append(f"- {q}")
    return "\n".join(parts)
