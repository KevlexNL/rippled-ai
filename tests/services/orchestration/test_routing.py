"""Tests for Stage 4 — Deterministic routing decision engine."""

import pytest

from app.services.orchestration.contracts import (
    ActorHint,
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    EvidenceSource,
    OwnerResolution,
    PipelineSpeechAct,
    RoutingAction,
    SpeechActResult,
)
from app.services.orchestration.stages.routing import compute_routing_decision


def _gate(candidate_type="commitment_candidate", confidence=0.75, escalate=False):
    return CandidateGateResult(
        candidate_type=CandidateType(candidate_type),
        confidence=confidence,
        rationale_short="test",
        escalate_recommended=escalate,
    )


def _speech(speech_act="self_commitment", confidence=0.8):
    return SpeechActResult(
        speech_act=PipelineSpeechAct(speech_act),
        confidence=confidence,
        rationale_short="test",
    )


def _extraction(present=True, owner_conf=0.8, deliverable_conf=0.8, **kwargs):
    return CommitmentExtractionResult(
        candidate_present=present,
        owner_text=kwargs.get("owner_text", "Alice"),
        owner_resolution=OwnerResolution(kwargs.get("owner_resolution", "sender")),
        deliverable_text=kwargs.get("deliverable_text", "the report"),
        timing_text=kwargs.get("timing_text", "by Friday"),
        evidence_source=EvidenceSource.latest_authored_text,
        owner_confidence=owner_conf,
        deliverable_confidence=deliverable_conf,
        timing_confidence=0.5,
        target_confidence=0.5,
        rationale_short="test",
    )


class TestRoutingDecisionGateRules:
    def test_low_gate_confidence_discards(self):
        result = compute_routing_decision(_gate(confidence=0.2))
        assert result.action == RoutingAction.discard
        assert result.reason_code == "gate_confidence_low"

    def test_gate_type_none_discards(self):
        result = compute_routing_decision(_gate(candidate_type="none", confidence=0.5))
        assert result.action == RoutingAction.discard
        assert result.reason_code == "gate_type_none"


class TestRoutingSpeechActRules:
    def test_information_speech_act_discards(self):
        result = compute_routing_decision(
            _gate(),
            _speech(speech_act="information", confidence=0.9),
        )
        assert result.action == RoutingAction.discard
        assert result.reason_code == "speech_act_information"


class TestRoutingCompletionRules:
    def test_completion_candidate_creates_record(self):
        result = compute_routing_decision(
            _gate(candidate_type="completion_candidate", confidence=0.8),
        )
        assert result.action == RoutingAction.create_completion_candidate
        assert result.reason_code == "completion_signal"


class TestRoutingExtractionRules:
    def test_strong_extraction_creates_record(self):
        result = compute_routing_decision(
            _gate(), _speech(), _extraction(owner_conf=0.8, deliverable_conf=0.8),
        )
        assert result.action == RoutingAction.create_candidate_record
        assert result.reason_code == "strong_extraction"

    def test_weak_extraction_observes(self):
        result = compute_routing_decision(
            _gate(), _speech(), _extraction(owner_conf=0.3, deliverable_conf=0.3),
        )
        assert result.action in (RoutingAction.observe_quietly, RoutingAction.escalate_model)

    def test_no_candidate_present_observes(self):
        result = compute_routing_decision(
            _gate(), _speech(), _extraction(present=False),
        )
        assert result.action == RoutingAction.observe_quietly


class TestRoutingEscalationRules:
    def test_mid_confidence_with_escalate_flag(self):
        result = compute_routing_decision(
            _gate(confidence=0.45, escalate=True),
            _speech(confidence=0.4),
        )
        assert result.action == RoutingAction.escalate_model

    def test_mid_confidence_without_escalate_flag_observes(self):
        result = compute_routing_decision(
            _gate(candidate_type="ambiguous_action_candidate", confidence=0.45, escalate=False),
            _speech(confidence=0.8),
        )
        assert result.action == RoutingAction.observe_quietly


class TestRoutingAmbiguousAction:
    def test_ambiguous_action_observes(self):
        result = compute_routing_decision(
            _gate(candidate_type="ambiguous_action_candidate", confidence=0.7),
            _speech(speech_act="suggestion", confidence=0.7),
        )
        assert result.action == RoutingAction.observe_quietly
