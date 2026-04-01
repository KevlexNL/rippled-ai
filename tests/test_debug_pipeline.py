"""Tests for POST /api/v1/debug/pipeline — dry-run pipeline endpoint."""

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


def _fake_pipeline_result(**overrides) -> PipelineResult:
    """Build a realistic PipelineResult for mocking."""
    defaults = dict(
        run_id="dry-run",
        normalized_signal_id="debug-test",
        pipeline_version="v1",
        eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
        candidate_gate=CandidateGateResult(
            candidate_type=CandidateType.commitment_candidate,
            confidence=0.85,
            rationale_short="Clear commitment language",
        ),
        speech_act=SpeechActResult(
            speech_act=PipelineSpeechAct.self_commitment,
            confidence=0.9,
            rationale_short="Speaker commits to action",
        ),
        extraction=CommitmentExtractionResult(
            candidate_present=True,
            owner_text="I",
            deliverable_text="quarterly report",
            timing_text="by Friday",
            rationale_short="Clear self-commitment",
        ),
        final_routing=RoutingDecision(
            action=RoutingAction.create_candidate_record,
            reason_code="commitment_detected",
            summary="Commitment detected",
        ),
    )
    defaults.update(overrides)
    return PipelineResult(**defaults)


class TestDebugPipelineEndpoint:
    """POST /api/v1/debug/pipeline accepts text and returns per-stage output."""

    def test_returns_200_with_stage_output(self, client):
        """Endpoint accepts a text payload and returns pipeline stage results."""
        fake_result = _fake_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I'll send you the quarterly report by Friday.",
                "source_type": "email",
            })

        assert resp.status_code == 200
        data = resp.json()

        assert "pipeline_version" in data
        assert "eligibility" in data
        assert data["eligibility"]["eligible"] is True
        assert "candidate_gate" in data
        assert data["candidate_gate"]["candidate_type"] == "commitment_candidate"
        assert "speech_act" in data
        assert "final_routing" in data

    def test_rejects_empty_text(self, client):
        """Endpoint rejects empty text with 422."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "",
            "source_type": "email",
        })
        assert resp.status_code == 422

    def test_rejects_missing_text(self, client):
        """Endpoint rejects missing text field."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "source_type": "email",
        })
        assert resp.status_code == 422

    def test_defaults_source_type_to_email(self, client):
        """source_type defaults to 'email' if not provided."""
        fake_result = _fake_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I will do the thing.",
            })

        assert resp.status_code == 200

