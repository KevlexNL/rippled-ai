"""Stage 2 — Speech-act classification executor."""

from __future__ import annotations

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import CandidateGateResult, SpeechActResult
from app.services.orchestration.prompts import speech_act as prompt
from app.services.orchestration.stages.llm_caller import LLMCallResult, call_llm_structured


def execute_speech_act(
    signal: NormalizedSignal,
    gate_result: CandidateGateResult,
) -> LLMCallResult:
    """Run the speech-act classification stage."""
    config = get_orchestration_config()
    model_cfg = config.model_routing.speech_act

    user_prompt = prompt.build_user_prompt(
        latest_authored_text=signal.latest_authored_text,
        prior_context_text=signal.prior_context_text,
        source_type=signal.source_type,
        subject=signal.subject,
        direction=signal.direction.value if signal.direction else None,
        candidate_type=gate_result.candidate_type.value,
        gate_confidence=gate_result.confidence,
    )

    return call_llm_structured(
        system_prompt=prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_type=SpeechActResult,
        model_name=model_cfg.primary,
        fallback_model=model_cfg.fallback,
    )


def get_prompt_metadata() -> dict:
    return {
        "template_id": prompt.TEMPLATE_ID,
        "version": prompt.TEMPLATE_VERSION,
    }
