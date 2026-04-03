"""Tests for orchestration stage contracts — schema validation."""

import pytest
from pydantic import ValidationError

from app.services.orchestration.contracts import (
    ActorHint,
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    EligibilityReason,
    EligibilityResult,
    EscalationResolution,
    EvidenceSource,
    OwnerResolution,
    PipelineResult,
    PipelineSpeechAct,
    RoutingAction,
    RoutingDecision,
    SpeechActResult,
)


class TestEligibilityResult:
    def test_eligible(self):
        r = EligibilityResult(eligible=True, reason=EligibilityReason.ok)
        assert r.eligible is True
        assert r.reason == EligibilityReason.ok

    def test_ineligible_missing_text(self):
        r = EligibilityResult(eligible=False, reason=EligibilityReason.missing_text)
        assert r.eligible is False
        assert r.reason.value == "missing_text"


class TestCandidateGateResult:
    def test_valid(self):
        r = CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.85,
            rationale_short="Sender says 'I will send'",
        )
        assert r.candidate_type == CandidateType.commitment_candidate
        assert r.confidence == 0.85
        assert r.escalate_recommended is False

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            CandidateGateResult(
                candidate_type=CandidateType.none,
                confidence=1.5,
                rationale_short="too high",
            )

        with pytest.raises(ValidationError):
            CandidateGateResult(
                candidate_type=CandidateType.none,
                confidence=-0.1,
                rationale_short="negative",
            )

    def test_from_dict(self):
        data = {
            "candidate_type": "commitment_candidate",
            "confidence": 0.7,
            "rationale_short": "test",
            "escalate_recommended": True,
        }
        r = CandidateGateResult.model_validate(data)
        assert r.candidate_type == CandidateType.commitment_candidate
        assert r.escalate_recommended is True


class TestSpeechActResult:
    def test_valid(self):
        r = SpeechActResult(
            speech_act=PipelineSpeechAct.self_commitment,
            confidence=0.9,
            actor_hint=ActorHint.sender,
            target_hint=ActorHint.recipient,
            rationale_short="I will do X",
        )
        assert r.speech_act == PipelineSpeechAct.self_commitment
        assert r.actor_hint == ActorHint.sender

    def test_defaults(self):
        r = SpeechActResult(
            speech_act=PipelineSpeechAct.unclear,
            confidence=0.3,
        )
        assert r.actor_hint == ActorHint.unclear
        assert r.ambiguity_flags == []

    def test_all_speech_acts(self):
        for act in PipelineSpeechAct:
            r = SpeechActResult(speech_act=act, confidence=0.5, rationale_short="test")
            assert r.speech_act == act


class TestCommitmentExtractionResult:
    def test_full_extraction(self):
        r = CommitmentExtractionResult(
            candidate_present=True,
            owner_text="Alice",
            owner_resolution=OwnerResolution.sender,
            deliverable_text="quarterly report",
            timing_text="by Friday",
            target_text="Bob",
            evidence_span="I'll send you the quarterly report by Friday",
            evidence_source=EvidenceSource.latest_authored_text,
            owner_confidence=0.95,
            deliverable_confidence=0.90,
            timing_confidence=0.85,
            target_confidence=0.80,
            rationale_short="Clear self-commitment",
        )
        assert r.candidate_present is True
        assert r.owner_resolution == OwnerResolution.sender

    def test_empty_extraction(self):
        r = CommitmentExtractionResult(candidate_present=False)
        assert r.owner_text is None
        assert r.owner_confidence == 0.0
        assert r.ambiguity_flags == []

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            CommitmentExtractionResult(candidate_present=True, owner_confidence=2.0)


class TestRoutingDecision:
    def test_all_actions(self):
        for action in RoutingAction:
            r = RoutingDecision(action=action, reason_code="test", summary="test")
            assert r.action == action

    def test_serialization(self):
        r = RoutingDecision(
            action=RoutingAction.create_candidate_record,
            reason_code="strong_extraction",
            summary="test",
        )
        d = r.model_dump()
        assert d["action"] == "create_candidate_record"


class TestEscalationResolution:
    def test_unresolved(self):
        r = EscalationResolution(resolved=False, rationale_short="Could not determine")
        assert r.resolved is False
        assert r.updated_gate is None

    def test_resolved_with_overrides(self):
        gate = CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.85,
            rationale_short="Escalation confirms",
        )
        r = EscalationResolution(resolved=True, updated_gate=gate, confidence_delta=0.25)
        assert r.resolved is True
        assert r.updated_gate.confidence == 0.85


class TestCandidateTypeNormalization:
    """LLMs sometimes return synonym values for candidate_type that must be normalized."""

    @pytest.mark.parametrize("raw_value", ["non_candidate", "not_a_candidate", "no_candidate", "not_candidate"])
    def test_candidate_type_synonyms_normalize_to_none(self, raw_value: str):
        r = CandidateGateResult.model_validate({
            "candidate_type": raw_value,
            "confidence": 0.9,
            "rationale_short": "test",
        })
        assert r.candidate_type == CandidateType.none

    def test_valid_candidate_type_unchanged(self):
        for ct in CandidateType:
            r = CandidateGateResult.model_validate({
                "candidate_type": ct.value,
                "confidence": 0.5,
                "rationale_short": "test",
            })
            assert r.candidate_type == ct


class TestSpeechActNormalization:
    """LLMs sometimes return synonym values for speech_act that must be normalized."""

    @pytest.mark.parametrize("raw_value,expected", [
        ("inform", PipelineSpeechAct.information),
        ("informational", PipelineSpeechAct.information),
        ("info", PipelineSpeechAct.information),
    ])
    def test_speech_act_synonyms_normalize(self, raw_value: str, expected: PipelineSpeechAct):
        r = SpeechActResult.model_validate({
            "speech_act": raw_value,
            "confidence": 0.8,
            "rationale_short": "test",
        })
        assert r.speech_act == expected

    def test_valid_speech_acts_unchanged(self):
        for sa in PipelineSpeechAct:
            r = SpeechActResult.model_validate({
                "speech_act": sa.value,
                "confidence": 0.5,
                "rationale_short": "test",
            })
            assert r.speech_act == sa


class TestEscalationEnumNormalization:
    """Escalation stage returns nested models — enum normalization must work through nesting."""

    def test_escalation_with_non_candidate_synonym(self):
        data = {
            "resolved": True,
            "updated_gate": {
                "candidate_type": "not_a_candidate",
                "confidence": 0.95,
                "rationale_short": "Not a commitment",
                "escalate_recommended": False,
            },
            "rationale_short": "Resolved via escalation",
        }
        r = EscalationResolution.model_validate(data)
        assert r.updated_gate.candidate_type == CandidateType.none

    def test_escalation_with_inform_synonym(self):
        data = {
            "resolved": True,
            "updated_speech_act": {
                "speech_act": "inform",
                "confidence": 0.9,
                "actor_hint": "sender",
                "target_hint": "recipient",
                "rationale_short": "Informational only",
                "ambiguity_flags": [],
            },
            "rationale_short": "Resolved via escalation",
        }
        r = EscalationResolution.model_validate(data)
        assert r.updated_speech_act.speech_act == PipelineSpeechAct.information


class TestPipelineResult:
    def test_minimal(self):
        r = PipelineResult(
            run_id="run-1",
            normalized_signal_id="sig-1",
            pipeline_version="v1.0.0",
            eligibility=EligibilityResult(eligible=False, reason=EligibilityReason.missing_text),
        )
        assert r.candidate_gate is None
        assert r.final_routing is None

    def test_full_pipeline(self):
        r = PipelineResult(
            run_id="run-1",
            normalized_signal_id="sig-1",
            pipeline_version="v1.0.0",
            eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
            candidate_gate=CandidateGateResult(
                candidate_type=CandidateType.commitment_candidate,
                confidence=0.8,
                rationale_short="test",
            ),
            routing=RoutingDecision(
                action=RoutingAction.create_candidate_record,
                reason_code="strong",
                summary="test",
            ),
            final_routing=RoutingDecision(
                action=RoutingAction.create_candidate_record,
                reason_code="strong",
                summary="test",
            ),
        )
        assert r.eligibility.eligible is True
        assert r.final_routing.action == RoutingAction.create_candidate_record
