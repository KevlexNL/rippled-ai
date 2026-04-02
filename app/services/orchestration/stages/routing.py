"""Stage 4 — Deterministic routing decision engine.

No LLM dependency. Takes stage outputs and decides the system's next action.
All policy thresholds come from OrchestrationConfig.
"""

from __future__ import annotations

from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import (
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    PipelineSpeechAct,
    RoutingAction,
    RoutingDecision,
    SpeechActResult,
)


def compute_routing_decision(
    gate_result: CandidateGateResult,
    speech_act_result: SpeechActResult | None = None,
    extraction_result: CommitmentExtractionResult | None = None,
) -> RoutingDecision:
    """Deterministic routing based on stage outputs and config thresholds."""
    config = get_orchestration_config()
    thresholds = config.gate_thresholds
    sufficiency = config.structural_sufficiency
    escalation = config.escalation_thresholds

    # Rule 1: Gate confidence too low => discard
    if gate_result.confidence < thresholds.discard_below:
        return RoutingDecision(
            action=RoutingAction.discard,
            reason_code="gate_confidence_low",
            summary=f"Gate confidence {gate_result.confidence:.2f} below discard threshold {thresholds.discard_below}",
        )

    # Rule 2: Gate says none and no speech-act overrides => discard
    if gate_result.candidate_type == CandidateType.none:
        return RoutingDecision(
            action=RoutingAction.discard,
            reason_code="gate_type_none",
            summary="Gate classified as no candidate",
        )

    # Rule 3: Speech act is purely informational => discard
    if speech_act_result and speech_act_result.speech_act == PipelineSpeechAct.information:
        return RoutingDecision(
            action=RoutingAction.discard,
            reason_code="speech_act_information",
            summary="Speech act classified as pure information",
        )

    # Rule 4: Completion candidate => create completion record
    if gate_result.candidate_type == CandidateType.completion_candidate:
        return RoutingDecision(
            action=RoutingAction.create_completion_candidate,
            reason_code="completion_signal",
            summary="Completion candidate detected",
        )

    # Rule 5: Check if escalation is warranted
    needs_escalation = False
    escalation_reasons = []

    if escalation.gate_confidence_floor <= gate_result.confidence <= escalation.gate_confidence_ceiling:
        needs_escalation = True
        escalation_reasons.append("gate_mid_confidence")

    if speech_act_result and speech_act_result.confidence < escalation.speech_act_confidence_floor:
        needs_escalation = True
        escalation_reasons.append("speech_act_low_confidence")

    if extraction_result:
        if extraction_result.owner_confidence < escalation.extraction_owner_confidence_floor:
            needs_escalation = True
            escalation_reasons.append("owner_low_confidence")
        if extraction_result.deliverable_confidence < escalation.extraction_deliverable_confidence_floor:
            needs_escalation = True
            escalation_reasons.append("deliverable_low_confidence")

    # Rule 6: If extraction ran and has strong structure => create candidate record
    if extraction_result and extraction_result.candidate_present:
        has_owner = extraction_result.owner_confidence >= sufficiency.owner_confidence_min
        has_deliverable = extraction_result.deliverable_confidence >= sufficiency.deliverable_confidence_min

        if has_owner and has_deliverable:
            # Extraction completeness gate: at least one of owner_text or
            # deliverable_text must be non-empty. High confidence with no
            # actual extracted text is a hallucination from marketing content.
            owner_text_present = bool(
                extraction_result.owner_text and extraction_result.owner_text.strip()
            )
            deliverable_text_present = bool(
                extraction_result.deliverable_text and extraction_result.deliverable_text.strip()
            )

            if not owner_text_present and not deliverable_text_present:
                return RoutingDecision(
                    action=RoutingAction.discard,
                    reason_code="extraction_text_empty",
                    summary="High confidence but no actual owner or deliverable text extracted",
                )

            return RoutingDecision(
                action=RoutingAction.create_candidate_record,
                reason_code="strong_extraction",
                summary=f"Owner ({extraction_result.owner_confidence:.2f}) and deliverable ({extraction_result.deliverable_confidence:.2f}) above sufficiency thresholds",
            )

        # Meaningful but incomplete => observe or escalate
        if needs_escalation and gate_result.escalate_recommended:
            return RoutingDecision(
                action=RoutingAction.escalate_model,
                reason_code=",".join(escalation_reasons),
                summary="Extraction incomplete, escalation recommended",
            )

        return RoutingDecision(
            action=RoutingAction.observe_quietly,
            reason_code="extraction_incomplete",
            summary="Candidate present but structure insufficient for record creation",
        )

    # Rule 7: Gate flagged escalation
    if needs_escalation and gate_result.escalate_recommended:
        return RoutingDecision(
            action=RoutingAction.escalate_model,
            reason_code=",".join(escalation_reasons),
            summary="Ambiguity warrants stronger model review",
        )

    # Rule 8: Ambiguous action with mid confidence => observe
    if gate_result.candidate_type == CandidateType.ambiguous_action_candidate:
        return RoutingDecision(
            action=RoutingAction.observe_quietly,
            reason_code="ambiguous_action",
            summary="Ambiguous action language, observing quietly",
        )

    # Default: observe
    return RoutingDecision(
        action=RoutingAction.observe_quietly,
        reason_code="default_observe",
        summary="No strong signal for action, observing",
    )
