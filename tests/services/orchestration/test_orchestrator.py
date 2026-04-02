"""Tests for the SignalOrchestrator — end-to-end pipeline with mocked LLM calls."""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.contracts import (
    CandidateType,
    EligibilityReason,
    PipelineSpeechAct,
    RoutingAction,
)
from app.services.orchestration.orchestrator import SignalOrchestrator


def _make_signal(**kwargs) -> NormalizedSignal:
    defaults = {
        "signal_id": "sig-001",
        "source_type": "email",
        "occurred_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "authored_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "latest_authored_text": "I'll send you the quarterly report by Friday.",
        "subject": "Re: Quarterly Report",
    }
    defaults.update(kwargs)
    return NormalizedSignal(**defaults)


def _mock_llm_response(content: dict):
    """Create a mock OpenAI response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(content)
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return mock_response


class TestOrchestratorIneligible:
    def test_ineligible_signal_stops_early(self):
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        orchestrator = SignalOrchestrator(db)
        signal = _make_signal(latest_authored_text="", prior_context_text=None)

        result = orchestrator.process(signal)

        assert result.eligibility.eligible is False
        assert result.eligibility.reason == EligibilityReason.missing_text
        assert result.final_routing.action == RoutingAction.discard
        assert result.candidate_gate is None

    def test_unsupported_source_stops_early(self):
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        orchestrator = SignalOrchestrator(db)
        signal = _make_signal(source_type="sms")

        result = orchestrator.process(signal)

        assert result.eligibility.eligible is False
        assert result.final_routing.action == RoutingAction.discard


class TestOrchestratorFullPipeline:
    @patch("app.services.orchestration.stages.llm_caller.OpenAI")
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_commitment_flow_creates_record(self, mock_settings, mock_openai_cls):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        # Mock the client instance
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Stage 1: Gate says commitment candidate
        gate_response = _mock_llm_response({
            "candidate_type": "commitment_candidate",
            "confidence": 0.85,
            "rationale_short": "Sender says I'll send",
            "escalate_recommended": False,
        })

        # Stage 2: Speech act says self_commitment
        speech_response = _mock_llm_response({
            "speech_act": "self_commitment",
            "confidence": 0.90,
            "actor_hint": "sender",
            "target_hint": "recipient",
            "rationale_short": "Self-commitment to send report",
            "ambiguity_flags": [],
        })

        # Stage 3: Extraction
        extraction_response = _mock_llm_response({
            "candidate_present": True,
            "owner_text": "sender (Alice)",
            "owner_resolution": "sender",
            "deliverable_text": "quarterly report",
            "timing_text": "by Friday",
            "target_text": "recipient",
            "evidence_span": "I'll send you the quarterly report by Friday",
            "evidence_source": "latest_authored_text",
            "owner_confidence": 0.95,
            "deliverable_confidence": 0.90,
            "timing_confidence": 0.85,
            "target_confidence": 0.80,
            "ambiguity_flags": [],
            "rationale_short": "Clear self-commitment",
        })

        mock_client.chat.completions.create.side_effect = [
            gate_response, speech_response, extraction_response,
        ]

        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        orchestrator = SignalOrchestrator(db)
        result = orchestrator.process(_make_signal())

        assert result.eligibility.eligible is True
        assert result.candidate_gate is not None
        assert result.candidate_gate.candidate_type == CandidateType.commitment_candidate
        assert result.speech_act is not None
        assert result.speech_act.speech_act == PipelineSpeechAct.self_commitment
        assert result.extraction is not None
        assert result.extraction.candidate_present is True
        assert result.final_routing.action == RoutingAction.create_candidate_record
        assert result.error is None

    @patch("app.services.orchestration.stages.llm_caller.OpenAI")
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_greeting_discarded(self, mock_settings, mock_openai_cls):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        gate_response = _mock_llm_response({
            "candidate_type": "none",
            "confidence": 0.10,
            "rationale_short": "Just a greeting",
            "escalate_recommended": False,
        })

        mock_client.chat.completions.create.side_effect = [gate_response]

        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        orchestrator = SignalOrchestrator(db)
        signal = _make_signal(latest_authored_text="Hi Bob, hope you're doing well!")

        result = orchestrator.process(signal)

        assert result.eligibility.eligible is True
        assert result.final_routing.action == RoutingAction.discard


class TestOrchestratorErrorHandling:
    @patch("app.services.orchestration.stages.llm_caller.OpenAI")
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_gate_failure_records_error(self, mock_settings, mock_openai_cls):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        orchestrator = SignalOrchestrator(db)
        result = orchestrator.process(_make_signal())

        assert result.eligibility.eligible is True
        assert result.candidate_gate is None
        assert "Candidate gate stage failed" in result.error

    @patch("app.services.orchestration.stages.llm_caller.OpenAI")
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_gate_failure_populates_stage_errors(self, mock_settings, mock_openai_cls):
        """stage_errors dict must contain the actual LLM error for diagnostics (AC4)."""
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")

        db = MagicMock()
        orchestrator = SignalOrchestrator(db)
        result = orchestrator.process(_make_signal())

        assert result.stage_errors is not None
        assert "candidate_gate" in result.stage_errors
        assert "Connection timeout" in result.stage_errors["candidate_gate"]

    @patch("app.services.orchestration.stages.llm_caller.OpenAI")
    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_gate_failure_error_includes_detail(self, mock_settings, mock_openai_cls):
        """result.error must include the actual LLM error, not just generic message."""
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_model="gpt-test")

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")

        db = MagicMock()
        orchestrator = SignalOrchestrator(db)
        result = orchestrator.process(_make_signal())

        assert "Candidate gate stage failed" in result.error
        assert "Connection timeout" in result.error

    @patch("app.services.orchestration.stages.llm_caller.get_settings")
    def test_missing_api_key_surfaces_in_stage_errors(self, mock_settings):
        """Missing API key error must be visible in stage_errors."""
        mock_settings.return_value = MagicMock(openai_api_key="", openai_model="gpt-test")

        orchestrator = SignalOrchestrator(db=None, dry_run=True)
        result = orchestrator.process(_make_signal())

        assert result.stage_errors is not None
        assert "candidate_gate" in result.stage_errors
        assert "API key" in result.stage_errors["candidate_gate"]
