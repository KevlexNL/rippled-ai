"""Tests for Phase C1 — Model-Assisted Detection.

Test strategy:
- ModelDetectionService: unit tests with mocked OpenAI responses
- HybridDetectionService: integration tests covering all confidence zones
- Edge cases: OpenAI failure fallback, rate limits, malformed responses
- Config: environment variable handling

Tests run without a real database or real OpenAI calls.
"""
from __future__ import annotations

import types
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.services.model_detection import ModelDetectionService, ModelDetectionResult
from app.services.hybrid_detection import (
    HybridDetectionService,
    AMBIGUOUS_LOWER,
    AMBIGUOUS_UPPER,
    MODEL_PROMOTE_THRESHOLD,
    MODEL_DEMOTE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_candidate(**kwargs) -> Any:
    """Create a minimal CommitmentCandidate-like namespace for testing."""
    defaults: dict[str, Any] = {
        "id": "cand-001",
        "user_id": "user-001",
        "source_type": "email",
        "raw_text": "I'll have the report done by Friday",
        "confidence_score": Decimal("0.55"),
        "trigger_class": "implicit_next_step",
        "is_explicit": False,
        "context_window": {
            "trigger_text": "I'll have the report done by Friday",
            "pre_context": "We discussed the Q1 analysis yesterday.",
            "post_context": "Let me know if you need anything earlier.",
            "source_type": "email",
        },
        "was_discarded": False,
        "discard_reason": None,
        "model_confidence": None,
        "model_classification": None,
        "model_explanation": None,
        "model_called_at": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _mock_openai_response(is_commitment: bool, confidence: float, explanation: str = "test", suggested_owner: str | None = None, suggested_deadline: str | None = None) -> Any:
    """Build a mock OpenAI chat completion response."""
    import json
    content = json.dumps({
        "is_commitment": is_commitment,
        "confidence": confidence,
        "explanation": explanation,
        "suggested_owner": suggested_owner,
        "suggested_deadline": suggested_deadline,
    })
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    return response


# ---------------------------------------------------------------------------
# ModelDetectionService — result dataclass
# ---------------------------------------------------------------------------

class TestModelDetectionResult:
    def test_result_fields_exist(self):
        result = ModelDetectionResult(
            is_commitment=True,
            confidence=0.85,
            explanation="Clear commitment detected",
            suggested_owner="Alice",
            suggested_deadline="2026-03-20",
        )
        assert result.is_commitment is True
        assert result.confidence == 0.85
        assert result.explanation == "Clear commitment detected"
        assert result.suggested_owner == "Alice"
        assert result.suggested_deadline == "2026-03-20"

    def test_result_nullable_fields(self):
        result = ModelDetectionResult(
            is_commitment=False,
            confidence=0.2,
            explanation="Not a commitment",
            suggested_owner=None,
            suggested_deadline=None,
        )
        assert result.suggested_owner is None
        assert result.suggested_deadline is None


# ---------------------------------------------------------------------------
# ModelDetectionService — classify method
# ---------------------------------------------------------------------------

class TestModelDetectionServiceClassify:
    """ModelDetectionService.classify() with mocked OpenAI responses."""

    def test_classify_returns_commitment_result(self):
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(
            is_commitment=True, confidence=0.9,
            explanation="Explicit self-commitment",
            suggested_owner="Alice", suggested_deadline="2026-03-20",
        )
        with patch.object(service._client.chat.completions, "create", return_value=mock_response):
            candidate = _make_candidate()
            result = service.classify(candidate)
        assert isinstance(result, ModelDetectionResult)
        assert result.is_commitment is True
        assert result.confidence == 0.9

    def test_classify_returns_not_commitment_result(self):
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(
            is_commitment=False, confidence=0.85,
            explanation="Casual statement, not a commitment",
        )
        with patch.object(service._client.chat.completions, "create", return_value=mock_response):
            result = service.classify(_make_candidate(raw_text="sounds good"))
        assert result.is_commitment is False
        assert result.confidence == 0.85

    def test_classify_passes_context_window_to_openai(self):
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.8)
        ctx = {
            "trigger_text": "I'll do it",
            "pre_context": "We need this done.",
            "post_context": "ASAP.",
            "source_type": "slack",
        }
        with patch.object(service._client.chat.completions, "create", return_value=mock_response) as mock_create:
            service.classify(_make_candidate(context_window=ctx))
        call_args = mock_create.call_args
        prompt_text = str(call_args)
        assert "I'll do it" in prompt_text

    def test_classify_includes_suggested_owner(self):
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(
            is_commitment=True, confidence=0.88,
            suggested_owner="Bob", suggested_deadline="next Friday",
        )
        with patch.object(service._client.chat.completions, "create", return_value=mock_response):
            result = service.classify(_make_candidate())
        assert result.suggested_owner == "Bob"
        assert result.suggested_deadline == "next Friday"

    def test_classify_uses_json_response_format(self):
        """OpenAI must be called with json_object response format."""
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.7)
        with patch.object(service._client.chat.completions, "create", return_value=mock_response) as mock_create:
            service.classify(_make_candidate())
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    def test_classify_uses_configured_model(self):
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.7)
        with patch.object(service._client.chat.completions, "create", return_value=mock_response) as mock_create:
            service.classify(_make_candidate())
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("model") == "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# ModelDetectionService — error handling
# ---------------------------------------------------------------------------

class TestModelDetectionServiceErrorHandling:
    def test_classify_returns_none_on_openai_error(self):
        """API errors must return None, never raise."""
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        with patch.object(service._client.chat.completions, "create", side_effect=Exception("API error")):
            result = service.classify(_make_candidate())
        assert result is None

    def test_classify_returns_none_on_malformed_json(self):
        """Malformed JSON in response must return None, never raise."""
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        bad_msg = MagicMock()
        bad_msg.content = "not valid json at all"
        bad_choice = MagicMock()
        bad_choice.message = bad_msg
        bad_response = MagicMock()
        bad_response.choices = [bad_choice]
        with patch.object(service._client.chat.completions, "create", return_value=bad_response):
            result = service.classify(_make_candidate())
        assert result is None

    def test_classify_returns_none_on_missing_fields(self):
        """JSON with missing required fields must return None."""
        import json
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        incomplete_msg = MagicMock()
        incomplete_msg.content = json.dumps({"is_commitment": True})  # missing confidence, explanation
        choice = MagicMock()
        choice.message = incomplete_msg
        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock()
        response.usage.prompt_tokens = 50
        response.usage.completion_tokens = 10
        with patch.object(service._client.chat.completions, "create", return_value=response):
            result = service.classify(_make_candidate())
        assert result is None

    def test_classify_returns_none_on_empty_context_window(self):
        """Candidate with no context_window should not raise."""
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.7)
        with patch.object(service._client.chat.completions, "create", return_value=mock_response):
            result = service.classify(_make_candidate(context_window=None))
        # Should still work or return None gracefully
        assert result is None or isinstance(result, ModelDetectionResult)

    def test_classify_returns_none_when_no_api_key(self):
        """Service initialized with empty api_key must return None without calling API."""
        service = ModelDetectionService(api_key="", model="gpt-4.1-mini")
        result = service.classify(_make_candidate())
        assert result is None

    def test_rate_limit_triggers_retry(self):
        """429 RateLimitError triggers retry logic."""
        from openai import RateLimitError
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429, headers={}),
            body={},
        )
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.8)
        # First call raises 429, second call succeeds
        with patch.object(
            service._client.chat.completions,
            "create",
            side_effect=[rate_limit_error, mock_response],
        ):
            result = service.classify(_make_candidate())
        # After retry, should succeed
        assert result is not None
        assert result.is_commitment is True


# ---------------------------------------------------------------------------
# HybridDetectionService — confidence zone routing
# ---------------------------------------------------------------------------

class TestHybridDetectionServiceZones:
    """Pre-filter routing to the right confidence zone."""

    def test_high_confidence_skips_model(self):
        """confidence >= 0.75: skip model, keep deterministic result."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.85"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is False

    def test_high_confidence_boundary_skips_model(self):
        """confidence exactly 0.75: skip model."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.75"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is False

    def test_low_confidence_skips_model(self):
        """confidence < 0.35: skip model, keep deterministic result."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.20"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is False

    def test_low_confidence_boundary_skips_model(self):
        """confidence exactly 0.34: skip model."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.34"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is False

    def test_ambiguous_zone_calls_model(self):
        """0.35 <= confidence < 0.75: model is called."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.82,
            explanation="Ambiguous but looks like a commitment",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["model_called"] is True
        mock_model.classify.assert_called_once_with(candidate)

    def test_ambiguous_lower_boundary_calls_model(self):
        """confidence exactly 0.35: model IS called."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.75,
            explanation="Commitment", suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.35"))
        result = service.process(candidate)
        assert result["model_called"] is True

    def test_ambiguous_upper_boundary_calls_model(self):
        """confidence exactly 0.74: model IS called."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.75,
            explanation="Commitment", suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.74"))
        result = service.process(candidate)
        assert result["model_called"] is True


# ---------------------------------------------------------------------------
# HybridDetectionService — decision rules
# ---------------------------------------------------------------------------

class TestHybridDetectionDecisionRules:
    """Decision rules when model result is available."""

    def test_model_promotes_ambiguous_candidate(self):
        """Model says commitment with confidence > 0.6: detection_method = model-assisted."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.85,
            explanation="This is clearly a commitment",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.50"))
        result = service.process(candidate)
        assert result["detection_method"] == "model-assisted"
        assert result["was_discarded"] is False

    def test_model_demotes_false_positive(self):
        """Model says not-commitment with confidence > 0.7: detection_method = model-overridden, was_discarded = True."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=False, confidence=0.80,
            explanation="This is casual speech, not a commitment",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.45"))
        result = service.process(candidate)
        assert result["detection_method"] == "model-overridden"
        assert result["was_discarded"] is True
        assert result["discard_reason"] == "model-overridden"

    def test_model_uncertain_keeps_deterministic(self):
        """Model not confident (< threshold): keep deterministic result."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.5,  # Below MODEL_PROMOTE_THRESHOLD
            explanation="Unclear",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.50"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["was_discarded"] is False

    def test_model_says_not_commitment_but_low_confidence_keeps_deterministic(self):
        """Model says not-commitment but confidence <= 0.7: keep deterministic."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=False, confidence=0.55,  # Below MODEL_DEMOTE_THRESHOLD
            explanation="Maybe not a commitment",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.50"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["was_discarded"] is False

    def test_model_confidence_recorded_in_result(self):
        """Model confidence is returned in result for DB update."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.88,
            explanation="Strong commitment signal",
            suggested_owner="Bob", suggested_deadline="Friday",
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["model_confidence"] == 0.88
        assert result["model_classification"] == "commitment"
        assert result["model_explanation"] == "Strong commitment signal"

    def test_model_not_commitment_classification_recorded(self):
        """Model not-commitment result is recorded."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=False, confidence=0.80,
            explanation="Not a commitment",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.50"))
        result = service.process(candidate)
        assert result["model_classification"] == "not-commitment"

    def test_model_uncertain_classification_when_low_confidence(self):
        """When model confidence too low for action, classification is 'uncertain'."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.45,
            explanation="Hard to say",
            suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.50"))
        result = service.process(candidate)
        assert result["model_classification"] == "uncertain"


# ---------------------------------------------------------------------------
# HybridDetectionService — model failure fallback
# ---------------------------------------------------------------------------

class TestHybridDetectionFallback:
    def test_model_returns_none_falls_back_to_deterministic(self):
        """If ModelDetectionService returns None (failure), keep deterministic result."""
        mock_model = MagicMock()
        mock_model.classify.return_value = None
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is True  # was attempted
        assert result["was_discarded"] is False

    def test_model_raises_exception_falls_back_to_deterministic(self):
        """If model_service.classify raises, catch and fall back."""
        mock_model = MagicMock()
        mock_model.classify.side_effect = Exception("Unexpected error")
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["was_discarded"] is False

    def test_model_service_none_falls_back_gracefully(self):
        """If model_service is None (not configured), ambiguous zone acts as deterministic."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["detection_method"] == "deterministic"
        assert result["model_called"] is False

    def test_model_called_at_timestamp_set_on_success(self):
        """model_called_at is set when model is actually called."""
        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True, confidence=0.8,
            explanation="Commitment", suggested_owner=None, suggested_deadline=None,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate)
        assert result["model_called_at"] is not None
        assert isinstance(result["model_called_at"], datetime)

    def test_model_called_at_none_when_skipped(self):
        """model_called_at is None when model is skipped."""
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.85"))
        result = service.process(candidate)
        assert result["model_called_at"] is None


# ---------------------------------------------------------------------------
# HybridDetectionService — result structure
# ---------------------------------------------------------------------------

class TestHybridDetectionResultStructure:
    def test_result_always_has_required_keys(self):
        """Result dict always has the required keys regardless of path."""
        service = HybridDetectionService(model_service=None)
        for score in [Decimal("0.20"), Decimal("0.55"), Decimal("0.85")]:
            result = service.process(_make_candidate(confidence_score=score))
            assert "detection_method" in result
            assert "model_called" in result
            assert "was_discarded" in result
            assert "discard_reason" in result
            assert "model_confidence" in result
            assert "model_classification" in result
            assert "model_explanation" in result
            assert "model_called_at" in result

    def test_none_fields_when_model_not_called(self):
        service = HybridDetectionService(model_service=None)
        result = service.process(_make_candidate(confidence_score=Decimal("0.85")))
        assert result["model_confidence"] is None
        assert result["model_classification"] is None
        assert result["model_explanation"] is None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_ambiguous_lower_is_decimal(self):
        assert AMBIGUOUS_LOWER == Decimal("0.35")

    def test_ambiguous_upper_is_decimal(self):
        assert AMBIGUOUS_UPPER == Decimal("0.75")

    def test_promote_threshold(self):
        assert MODEL_PROMOTE_THRESHOLD == 0.6

    def test_demote_threshold(self):
        assert MODEL_DEMOTE_THRESHOLD == 0.7


# ---------------------------------------------------------------------------
# ModelDetectionService — token logging
# ---------------------------------------------------------------------------

class TestModelDetectionTokenLogging:
    def test_token_usage_logged_at_debug(self, caplog):
        import logging
        service = ModelDetectionService(api_key="test-key", model="gpt-4.1-mini")
        mock_response = _mock_openai_response(is_commitment=True, confidence=0.8)
        mock_response.usage.prompt_tokens = 120
        mock_response.usage.completion_tokens = 45
        with patch.object(service._client.chat.completions, "create", return_value=mock_response):
            with caplog.at_level(logging.DEBUG):
                service.classify(_make_candidate())
        # Token usage should appear in logs
        log_text = " ".join(caplog.messages)
        assert "120" in log_text or "tokens" in log_text.lower()
