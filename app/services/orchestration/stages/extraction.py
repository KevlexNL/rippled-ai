"""Stage 3 — Commitment field extraction executor."""

from __future__ import annotations

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import (
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    PipelineSpeechAct,
    SpeechActResult,
)
from app.services.orchestration.prompts import extraction as prompt
from app.services.orchestration.stages.llm_caller import LLMCallResult, call_llm_structured

# Speech acts that indicate commitment-bearing intent
_COMMITMENT_BEARING_ACTS = {
    PipelineSpeechAct.self_commitment,
    PipelineSpeechAct.acceptance,
    PipelineSpeechAct.delegation,
    PipelineSpeechAct.request,
}


def should_run_extraction(
    gate_result: CandidateGateResult,
    speech_act_result: SpeechActResult,
) -> bool:
    """Determine if extraction stage should run based on prior stages."""
    if gate_result.candidate_type in (
        CandidateType.commitment_candidate,
        CandidateType.ambiguous_action_candidate,
    ):
        return True
    if speech_act_result.speech_act in _COMMITMENT_BEARING_ACTS:
        return True
    return False


def execute_extraction(
    signal: NormalizedSignal,
    gate_result: CandidateGateResult,
    speech_act_result: SpeechActResult,
) -> LLMCallResult:
    """Run the commitment field extraction stage."""
    config = get_orchestration_config()
    model_cfg = config.model_routing.extraction

    user_prompt = prompt.build_user_prompt(
        latest_authored_text=signal.latest_authored_text,
        prior_context_text=signal.prior_context_text,
        source_type=signal.source_type,
        subject=signal.subject,
        direction=signal.direction.value if signal.direction else None,
        speech_act=speech_act_result.speech_act.value,
        speech_act_confidence=speech_act_result.confidence,
        candidate_type=gate_result.candidate_type.value,
    )

    return call_llm_structured(
        system_prompt=prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_type=CommitmentExtractionResult,
        model_name=model_cfg.primary,
        fallback_model=model_cfg.fallback,
    )


def get_prompt_metadata() -> dict:
    return {
        "template_id": prompt.TEMPLATE_ID,
        "version": prompt.TEMPLATE_VERSION,
    }
