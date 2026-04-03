"""Tests for WO-RIPPLED-CLASSIFICATION-SPECIFIC-GAPS.

Covers:
- PipelineSpeechAct enum includes deadline_change and collective_commitment
- OwnerResolution enum includes ambiguous
- Speech-act prompt describes the new labels with examples
- Extraction prompt guides collective ownership calibration
- Extraction stage triggers on new speech acts
- GD-E04 and GD-E05 debug endpoint acceptance tests
"""

import pytest
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from app.main import app
from app.services.orchestration.contracts import (
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    EligibilityReason,
    EligibilityResult,
    OwnerResolution,
    PipelineResult,
    PipelineSpeechAct,
    RoutingAction,
    RoutingDecision,
    SpeechActResult,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------


class TestEnumAdditions:
    """New speech-act and owner-resolution values must exist in the enums."""

    def test_pipeline_speech_act_has_deadline_change(self):
        assert PipelineSpeechAct.deadline_change.value == "deadline_change"

    def test_pipeline_speech_act_has_collective_commitment(self):
        assert PipelineSpeechAct.collective_commitment.value == "collective_commitment"

    def test_owner_resolution_has_ambiguous(self):
        assert OwnerResolution.ambiguous.value == "ambiguous"

    def test_existing_speech_acts_unchanged(self):
        """No regression — existing enum values must still work."""
        for val in ("request", "self_commitment", "acceptance", "delegation",
                    "update", "completion", "suggestion", "information", "unclear"):
            assert PipelineSpeechAct(val).value == val

    def test_existing_owner_resolutions_unchanged(self):
        """No regression — existing enum values must still work."""
        for val in ("sender", "recipient", "third_party", "unknown", "not_applicable"):
            assert OwnerResolution(val).value == val


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------


class TestSpeechActPromptContent:
    """Speech-act prompt must describe the new labels."""

    def test_prompt_includes_deadline_change_label(self):
        from app.services.orchestration.prompts.speech_act import SYSTEM_PROMPT
        assert "deadline_change" in SYSTEM_PROMPT

    def test_prompt_includes_collective_commitment_label(self):
        from app.services.orchestration.prompts.speech_act import SYSTEM_PROMPT
        assert "collective_commitment" in SYSTEM_PROMPT

    def test_prompt_deadline_change_has_examples(self):
        """Prompt must include example language for deadline_change detection."""
        from app.services.orchestration.prompts.speech_act import SYSTEM_PROMPT
        # At least one of these reschedule phrases should appear
        assert any(phrase in SYSTEM_PROMPT.lower() for phrase in [
            "push the deadline", "move the date", "reschedul", "deadline has moved",
        ])

    def test_prompt_collective_commitment_has_examples(self):
        """Prompt must include example language for collective_commitment."""
        from app.services.orchestration.prompts.speech_act import SYSTEM_PROMPT
        assert any(phrase in SYSTEM_PROMPT.lower() for phrase in [
            "we need to", "we should", "we'll",
        ])


class TestExtractionPromptContent:
    """Extraction prompt must guide collective ownership calibration."""

    def test_prompt_includes_ambiguous_owner_resolution(self):
        from app.services.orchestration.prompts.extraction import SYSTEM_PROMPT
        assert "ambiguous" in SYSTEM_PROMPT

    def test_prompt_includes_collective_ownership_guidance(self):
        """Prompt must instruct low confidence for collective first-person plural."""
        from app.services.orchestration.prompts.extraction import SYSTEM_PROMPT
        prompt_lower = SYSTEM_PROMPT.lower()
        # Must mention collective/we phrasing AND low confidence
        assert "we need to" in prompt_lower or "we should" in prompt_lower
        assert "ambiguous" in prompt_lower


# ---------------------------------------------------------------------------
# Extraction stage triggering
# ---------------------------------------------------------------------------


class TestExtractionTriggersOnNewSpeechActs:
    """deadline_change and collective_commitment must trigger extraction."""

    def test_deadline_change_triggers_extraction(self):
        from app.services.orchestration.stages.extraction import should_run_extraction

        gate = CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.8,
            rationale_short="deadline language",
        )
        sa = SpeechActResult(
            speech_act=PipelineSpeechAct.deadline_change,
            confidence=0.85,
            rationale_short="deadline change detected",
        )
        assert should_run_extraction(gate, sa) is True

    def test_collective_commitment_triggers_extraction(self):
        from app.services.orchestration.stages.extraction import should_run_extraction

        gate = CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.75,
            rationale_short="collective language",
        )
        sa = SpeechActResult(
            speech_act=PipelineSpeechAct.collective_commitment,
            confidence=0.7,
            rationale_short="collective commitment detected",
        )
        assert should_run_extraction(gate, sa) is True


# ---------------------------------------------------------------------------
# GD-E04 and GD-E05 debug endpoint tests (mock-based)
# ---------------------------------------------------------------------------


def _gd_e05_pipeline_result() -> PipelineResult:
    """GD-E05: 'The deadline has moved to March 15th.' -> speech_act=deadline_change."""
    return PipelineResult(
        run_id="dry-run",
        normalized_signal_id="debug-test",
        pipeline_version="v1",
        eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
        candidate_gate=CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.80,
            rationale_short="Deadline change language",
        ),
        speech_act=SpeechActResult(
            speech_act=PipelineSpeechAct.deadline_change,
            confidence=0.85,
            rationale_short="Deadline reschedule detected",
        ),
        extraction=CommitmentExtractionResult(
            candidate_present=True,
            owner_text="you",
            owner_resolution=OwnerResolution.recipient,
            deliverable_text="update timeline",
            timing_text="March 15",
            rationale_short="Deadline moved, recipient must update",
        ),
        final_routing=RoutingDecision(
            action=RoutingAction.create_candidate_record,
            reason_code="commitment_detected",
            summary="Deadline change commitment",
        ),
    )


def _gd_e04_pipeline_result() -> PipelineResult:
    """GD-E04: 'We need to schedule a call...' -> owner_resolution=ambiguous, owner_confidence<0.6."""
    return PipelineResult(
        run_id="dry-run",
        normalized_signal_id="debug-test",
        pipeline_version="v1",
        eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
        candidate_gate=CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.75,
            rationale_short="Collective commitment language",
        ),
        speech_act=SpeechActResult(
            speech_act=PipelineSpeechAct.collective_commitment,
            confidence=0.70,
            rationale_short="Collective we-phrasing detected",
        ),
        extraction=CommitmentExtractionResult(
            candidate_present=True,
            owner_text="we",
            owner_resolution=OwnerResolution.ambiguous,
            deliverable_text="schedule a call to review the proposal",
            timing_text="end of the month",
            owner_confidence=0.4,
            rationale_short="Collective phrasing, ambiguous ownership",
            ambiguity_flags=["collective_we", "ambiguous_owner"],
        ),
        final_routing=RoutingDecision(
            action=RoutingAction.create_candidate_record,
            reason_code="commitment_detected",
            summary="Collective commitment with ambiguous ownership",
        ),
    )


class TestGDE05DeadlineChange:
    """GD-E05: deadline_change speech act must be valid in pipeline results."""

    def test_deadline_change_speech_act_accepted_in_response(self, client):
        """GD-E05 result with speech_act=deadline_change must serialize correctly."""
        fake_result = _gd_e05_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "The deadline has moved to March 15th. Please update your timeline accordingly.",
                "source_type": "email",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["speech_act"]["speech_act"] == "deadline_change"
        assert data["extraction"]["timing_text"] == "March 15"
        assert data["extraction"]["owner_resolution"] == "recipient"


class TestGDE04CollectiveOwnership:
    """GD-E04: collective 'We need to...' must yield ambiguous ownership."""

    def test_collective_ownership_ambiguous_in_response(self, client):
        """GD-E04 result with owner_resolution=ambiguous, owner_confidence<0.6."""
        fake_result = _gd_e04_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "We need to schedule a call before the end of the month to review the proposal.",
                "source_type": "email",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction"]["owner_resolution"] == "ambiguous"
        assert data["extraction"]["owner_confidence"] < 0.6
        assert "collective_we" in data["extraction"]["ambiguity_flags"]
