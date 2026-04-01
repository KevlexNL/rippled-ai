"""Tests for WO-RIPPLED-ENTITY-EXTRACTION — always-on entity extraction.

Verifies:
1. HybridDetectionService calls model for entity extraction regardless of
   confidence zone (high, ambiguous, low).
2. Classification overrides (promote/demote) only apply in the ambiguous zone.
3. Clarifier sets resolved_owner = requester_name as fallback when no identity match.
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.model_detection import ModelDetectionResult
from app.services.hybrid_detection import HybridDetectionService


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _make_candidate(**kwargs):
    defaults = {
        "id": "cand-entity-001",
        "user_id": "user-001",
        "source_type": "email",
        "raw_text": "I'll send the report to Bob by Friday",
        "confidence_score": Decimal("0.85"),
        "trigger_class": "explicit_commitment",
        "is_explicit": True,
        "context_window": {
            "trigger_text": "I'll send the report to Bob by Friday",
            "pre_context": "",
            "post_context": "",
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


def _model_result_with_entities(**kwargs):
    """Model result that includes entity extraction fields."""
    defaults = dict(
        is_commitment=True,
        confidence=0.9,
        explanation="Clear commitment",
        suggested_owner="Alice",
        suggested_deadline="Friday",
        speech_act="self_commitment",
        deliverable="the report",
        counterparty="Bob",
        user_relationship="mine",
        structure_complete=True,
        requester="Alice",
        beneficiary="Bob",
    )
    defaults.update(kwargs)
    return ModelDetectionResult(**defaults)


# ---------------------------------------------------------------------------
# HybridDetectionService — always-on entity extraction
# ---------------------------------------------------------------------------

class TestHighConfidenceEntityExtraction:
    """High-confidence candidates (>= 0.75) must still get entity extraction."""

    def test_high_confidence_calls_model_for_entities(self):
        """Model must be called even when confidence >= 0.75."""
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities()
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.85"))

        result = service.process(candidate)

        mock_model.classify.assert_called_once()
        assert result["requester"] == "Alice"
        assert result["beneficiary"] == "Bob"

    def test_high_confidence_preserves_deterministic_classification(self):
        """High-confidence candidates keep 'deterministic' method — model does NOT
        override classification even if it disagrees."""
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities(
            is_commitment=False, confidence=0.9,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.85"))

        result = service.process(candidate)

        # Classification unchanged — still deterministic, NOT discarded
        assert result["detection_method"] == "deterministic"
        assert result["was_discarded"] is False
        # But entities ARE extracted
        assert result["requester"] == "Alice"
        assert result["beneficiary"] == "Bob"

    def test_high_confidence_boundary_calls_model(self):
        """Confidence exactly 0.75 must still call model for entities."""
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities()
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.75"))

        result = service.process(candidate)

        mock_model.classify.assert_called_once()
        assert result["requester"] == "Alice"


class TestLowConfidenceEntityExtraction:
    """Low-confidence candidates (< 0.35) must still get entity extraction."""

    def test_low_confidence_calls_model_for_entities(self):
        """Model must be called even when confidence < 0.35."""
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities(
            is_commitment=False, confidence=0.2,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.20"))

        result = service.process(candidate)

        mock_model.classify.assert_called_once()
        assert result["requester"] == "Alice"
        assert result["beneficiary"] == "Bob"

    def test_low_confidence_preserves_deterministic_classification(self):
        """Low-confidence candidates keep 'deterministic' method."""
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities(
            is_commitment=True, confidence=0.8,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.20"))

        result = service.process(candidate)

        assert result["detection_method"] == "deterministic"
        assert result["was_discarded"] is False


class TestAmbiguousZoneUnchanged:
    """Ambiguous zone (0.35-0.75) keeps existing classification behaviour."""

    def test_ambiguous_still_promotes(self):
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities(
            is_commitment=True, confidence=0.85,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))

        result = service.process(candidate)

        assert result["detection_method"] == "model-assisted"
        assert result["requester"] == "Alice"

    def test_ambiguous_still_demotes(self):
        mock_model = MagicMock()
        mock_model.classify.return_value = _model_result_with_entities(
            is_commitment=False, confidence=0.80,
        )
        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))

        result = service.process(candidate)

        assert result["detection_method"] == "model-overridden"
        assert result["was_discarded"] is True


class TestNoModelServiceGraceful:
    """When no model service is configured, return empty entities gracefully."""

    def test_no_model_service_returns_empty_entities(self):
        service = HybridDetectionService(model_service=None)
        candidate = _make_candidate(confidence_score=Decimal("0.85"))
        result = service.process(candidate)
        assert result["model_called"] is False
        # Entity fields should not be present when model is unavailable
        assert result.get("requester") is None
        assert result.get("beneficiary") is None


# ---------------------------------------------------------------------------
# Clarifier — resolved_owner fallback
# ---------------------------------------------------------------------------

class TestClarifierResolvedOwnerFallback:
    """Clarifier must set resolved_owner = requester_name when no identity match."""

    def test_resolved_owner_set_from_requester_name(self):
        """When requester extracted but no identity resolution, resolved_owner = requester_name."""
        from app.services.clarification.clarifier import run_clarification

        candidate_id = str(uuid.uuid4())
        candidate = types.SimpleNamespace(
            id=candidate_id,
            user_id="user-001",
            source_type="email",
            raw_text="I'll send the report to Bob by Friday",
            trigger_class="explicit_commitment",
            is_explicit=True,
            confidence_score=Decimal("0.85"),
            linked_entities={
                "requester": "Alice",
                "beneficiary": "Bob",
                "speech_act": "self_commitment",
                "deliverable": "the report",
                "structure_complete": True,
            },
            context_window={},
            observe_until=datetime.now(timezone.utc) - timedelta(hours=1),
            priority_hint=None,
            was_promoted=False,
            was_discarded=False,
            originating_item_id="item-001",
            flag_reanalysis=False,
        )

        mock_db = MagicMock()
        mock_db.get.return_value = candidate

        # Patch resolve_party_sync to return None (no identity match)
        with patch("app.services.clarification.clarifier.resolve_party_sync", return_value=None), \
             patch("app.services.clarification.clarifier.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                counterparty_extraction_enabled=False,
            )
            result = run_clarification(candidate_id, mock_db)

        assert result["status"] == "clarified"

        # Find the Commitment object that was added to the DB
        added_objects = [
            call_args[0][0]
            for call_args in mock_db.add.call_args_list
        ]

        from app.models.orm import Commitment
        commitments = [o for o in added_objects if isinstance(o, Commitment)]
        assert len(commitments) >= 1

        commitment = commitments[0]
        assert commitment.requester_name == "Alice"
        assert commitment.resolved_owner == "Alice"
