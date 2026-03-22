"""Stage 5 — Escalation executor.

Uses a stronger model to resolve ambiguity when the cheap path cannot.
"""

from __future__ import annotations

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import (
    CandidateGateResult,
    CommitmentExtractionResult,
    EscalationResolution,
    SpeechActResult,
)
from app.services.orchestration.prompts import escalation as prompt
from app.services.orchestration.stages.llm_caller import LLMCallResult, call_llm_structured


def build_uncertainty_questions(
    gate_result: CandidateGateResult,
    speech_act_result: SpeechActResult | None,
    extraction_result: CommitmentExtractionResult | None,
) -> list[str]:
    """Generate specific uncertainty questions for the escalation model."""
    questions = []
    config = get_orchestration_config()
    esc = config.escalation_thresholds

    if gate_result.confidence < esc.gate_confidence_ceiling:
        questions.append(
            f"Is this message truly a business commitment candidate? Gate confidence was only {gate_result.confidence:.2f}."
        )

    if speech_act_result and speech_act_result.confidence < esc.speech_act_confidence_floor:
        questions.append(
            f"What is the correct speech act? Classification confidence was {speech_act_result.confidence:.2f}."
        )

    if extraction_result:
        if extraction_result.owner_confidence < esc.extraction_owner_confidence_floor:
            questions.append("Who is the owner of this commitment? The owner could not be confidently determined.")
        if extraction_result.deliverable_confidence < esc.extraction_deliverable_confidence_floor:
            questions.append("What exactly is being committed to? The deliverable is unclear.")
        if extraction_result.ambiguity_flags:
            questions.append(f"Resolve these ambiguities: {', '.join(extraction_result.ambiguity_flags)}")

    return questions or ["General ambiguity — review all prior stage outputs for accuracy."]


def execute_escalation(
    signal: NormalizedSignal,
    gate_result: CandidateGateResult,
    speech_act_result: SpeechActResult | None = None,
    extraction_result: CommitmentExtractionResult | None = None,
) -> LLMCallResult:
    """Run the escalation stage with a stronger model."""
    config = get_orchestration_config()
    model_cfg = config.model_routing.escalation

    questions = build_uncertainty_questions(gate_result, speech_act_result, extraction_result)

    user_prompt = prompt.build_user_prompt(
        latest_authored_text=signal.latest_authored_text,
        prior_context_text=signal.prior_context_text,
        source_type=signal.source_type,
        subject=signal.subject,
        gate_output=gate_result.model_dump(),
        speech_act_output=speech_act_result.model_dump() if speech_act_result else None,
        extraction_output=extraction_result.model_dump() if extraction_result else None,
        uncertainty_questions=questions,
    )

    return call_llm_structured(
        system_prompt=prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_type=EscalationResolution,
        model_name=model_cfg.primary,
        fallback_model=model_cfg.fallback,
    )


def get_prompt_metadata() -> dict:
    return {
        "template_id": prompt.TEMPLATE_ID,
        "version": prompt.TEMPLATE_VERSION,
    }
