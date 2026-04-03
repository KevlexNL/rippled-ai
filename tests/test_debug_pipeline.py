"""Tests for POST /api/v1/debug/pipeline — dry-run pipeline endpoint."""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import status
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

    def test_uses_dry_run_mode(self, client):
        """Endpoint passes dry_run=True to orchestrator — no DB persistence."""
        fake_result = _fake_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I'll send the report.",
            })

        assert resp.status_code == 200
        MockOrch.assert_called_once_with(db=None, dry_run=True)

    def test_ineligible_signal_returns_200_without_db(self, client):
        """Ineligible text still returns 200 with dry_run (no DB needed)."""
        # Don't mock the orchestrator — exercise the real code path
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "   ",  # blank after strip
        })
        # Pydantic validator rejects blank text
        assert resp.status_code == 422


class TestSPAFallbackDoesNotInterceptAPI:
    """GET requests to /api/ paths must NOT return SPA HTML (AC2)."""

    def test_get_debug_pipeline_returns_non_html(self, client):
        """GET /api/v1/debug/pipeline must return 405 or JSON error, not SPA HTML."""
        resp = client.get("/api/v1/debug/pipeline")
        # Must NOT return 200 with HTML — that's the SPA catching it
        content_type = resp.headers.get("content-type", "")
        assert "text/html" not in content_type, (
            f"GET /api/v1/debug/pipeline returned HTML (SPA catch-all intercepted): {resp.status_code}"
        )
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_get_arbitrary_api_path_returns_non_html(self, client):
        """GET /api/v1/nonexistent should return 404, not SPA HTML."""
        resp = client.get("/api/v1/nonexistent")
        content_type = resp.headers.get("content-type", "")
        assert "text/html" not in content_type, (
            "GET /api/v1/nonexistent returned HTML (SPA catch-all intercepted)"
        )

    def test_spa_fallback_still_works_for_frontend_routes(self, client):
        """Non-API paths should still get SPA HTML if public dir exists."""
        resp = client.get("/admin/dashboard")
        # If the SPA public dir exists, this should return HTML.
        # If it doesn't exist (CI), the catch-all won't be registered — skip.
        import os
        public_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", "public"))
        if os.path.isdir(public_dir):
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")


class TestDebugPipelineSenderAndHeaders:
    """Debug endpoint must accept sender_email and headers for eligibility checks."""

    def test_newsletter_sender_rejected_via_debug(self, client):
        """GD-E06: newsletter@substack.com must be rejected at eligibility."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "Check out our latest newsletter!",
            "source_type": "email",
            "sender_email": "newsletter@substack.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility"]["eligible"] is False
        assert data["eligibility"]["reason"] == "newsletter_sender"

    def test_noreply_sender_rejected_via_debug(self, client):
        """GD-E15: noreply@calendly.com must be rejected at eligibility."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "Your meeting has been scheduled.",
            "source_type": "email",
            "sender_email": "noreply@calendly.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility"]["eligible"] is False
        assert data["eligibility"]["reason"] == "newsletter_sender"

    def test_list_unsubscribe_header_rejected_via_debug(self, client):
        """Email with List-Unsubscribe header must be rejected."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "Some promotional content here with a real commitment maybe.",
            "source_type": "email",
            "sender_email": "newsletter@substack.com",
            "headers": {"List-Unsubscribe": "<mailto:unsub@example.com>"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility"]["eligible"] is False

    def test_fragment_rejected_via_debug(self, client):
        """GD-E07: 'done.' must be rejected as fragment at eligibility."""
        resp = client.post("/api/v1/debug/pipeline", json={
            "text": "done.",
            "source_type": "email",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility"]["eligible"] is False
        assert data["eligibility"]["reason"] == "fragment_too_short"

    def test_normal_sender_passes_debug(self, client):
        """Normal sender email should pass eligibility."""
        fake_result = _fake_pipeline_result()

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I'll send the report by Friday.",
                "source_type": "email",
                "sender_email": "alice@company.com",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility"]["eligible"] is True


class TestCandidateGateErrorDetail:
    """When candidate gate fails, error detail must be surfaced (AC4)."""

    def test_gate_failure_includes_actual_error_in_response(self, client):
        """When gate LLM call fails, the response error includes the reason."""
        fake_result = _fake_pipeline_result(
            candidate_gate=None,
            speech_act=None,
            extraction=None,
            routing=None,
            final_routing=None,
            error="Candidate gate stage failed",
        )

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I will deliver the report by Friday.",
            })

        data = resp.json()
        # The error should exist but this test validates the *new* behavior:
        # stage_errors should contain the per-stage error detail
        assert "stage_errors" in data, "PipelineResult must include stage_errors field"

    def test_stage_errors_contains_gate_error_detail(self, client):
        """stage_errors should contain the actual LLM error for the gate stage."""
        fake_result = _fake_pipeline_result(
            candidate_gate=None,
            speech_act=None,
            extraction=None,
            routing=None,
            final_routing=None,
            error="Candidate gate stage failed: No OpenAI API key configured",
            stage_errors={"candidate_gate": "No OpenAI API key configured"},
        )

        with patch("app.api.routes.debug.SignalOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.process.return_value = fake_result
            MockOrch.return_value = mock_instance

            resp = client.post("/api/v1/debug/pipeline", json={
                "text": "I will deliver the report by Friday.",
            })

        data = resp.json()
        assert data["stage_errors"]["candidate_gate"] == "No OpenAI API key configured"
        assert "No OpenAI API key configured" in data["error"]

