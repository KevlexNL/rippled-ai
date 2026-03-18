"""Tests for commitment structure enforcement (WO-RIPPLED-COMMITMENT-STRUCTURE-DETECTION).

Covers:
- Model detection v3: new fields in prompt response (deliverable, counterparty, user_relationship, structure_complete)
- Surfacing router: structure_complete gate, watching relationship gate
- Surface API filtering: mine-only for main, mine+contributing for shortlist
- Ownership filter: server-side user_relationship used when present
"""
from __future__ import annotations

import json
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.model_detection import ModelDetectionService, ModelDetectionResult
from app.services.hybrid_detection import HybridDetectionService
from app.services.surfacing_router import route, RoutingResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _make_candidate(**kwargs) -> Any:
    """Create a minimal CommitmentCandidate-like namespace for testing."""
    defaults: dict[str, Any] = {
        "id": "cand-001",
        "user_id": "user-001",
        "source_type": "email",
        "raw_text": "I'll send the report to Sarah by Friday",
        "confidence_score": Decimal("0.55"),
        "trigger_class": "explicit_self_commitment",
        "is_explicit": True,
        "context_window": {
            "trigger_text": "I'll send the report to Sarah by Friday",
            "pre_context": "We discussed the Q1 analysis.",
            "post_context": "Let me know if you need anything.",
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


def _make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal commitment-compatible namespace for surfacing tests."""
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Send the report",
        "description": None,
        "commitment_text": "I'll send the report to Sarah",
        "context_type": "internal",
        "resolved_deadline": None,
        "vague_time_phrase": None,
        "deadline_candidates": None,
        "timing_ambiguity": None,
        "deliverable": "report",
        "target_entity": None,
        "confidence_commitment": Decimal("0.7"),
        "confidence_owner": Decimal("0.6"),
        "confidence_actionability": Decimal("0.65"),
        "ownership_ambiguity": None,
        "deliverable_ambiguity": None,
        "resolved_owner": "Alice",
        "suggested_owner": None,
        "observe_until": None,
        "lifecycle_state": "active",
        "candidate_commitments": [],
        "surfaced_as": None,
        "priority_score": None,
        "timing_strength": None,
        "business_consequence": None,
        "cognitive_burden": None,
        "confidence_for_surfacing": None,
        "surfacing_reason": None,
        "is_surfaced": False,
        "surfaced_at": None,
        # New structure enforcement fields
        "counterparty_resolved": "Sarah",
        "user_relationship": "mine",
        "structure_complete": True,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Model Detection v3 — response parsing
# ---------------------------------------------------------------------------

class TestModelDetectionV3:
    """Test that ModelDetectionService parses v3 response fields."""

    def _mock_openai_response(self, data: dict) -> MagicMock:
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps(data)
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        return response

    def test_v3_fields_parsed(self):
        """v3 response includes deliverable, counterparty, user_relationship, structure_complete."""
        service = ModelDetectionService(api_key="test-key")
        mock_client = MagicMock()
        service._client = mock_client

        v3_response = {
            "is_commitment": True,
            "confidence": 0.9,
            "explanation": "Explicit self-commitment to send report.",
            "suggested_owner": "Kevin",
            "suggested_deadline": "Friday",
            "deliverable": "Q1 analysis report",
            "counterparty": "Sarah",
            "user_relationship": "mine",
            "structure_complete": True,
        }
        mock_client.chat.completions.create.return_value = self._mock_openai_response(v3_response)

        candidate = _make_candidate()
        result = service.classify(candidate, user_name="Kevin", user_email="kevin@test.com")

        assert result is not None
        assert result.is_commitment is True
        assert result.deliverable == "Q1 analysis report"
        assert result.counterparty == "Sarah"
        assert result.user_relationship == "mine"
        assert result.structure_complete is True

    def test_v3_structure_incomplete(self):
        """When counterparty is missing, structure_complete should be False."""
        service = ModelDetectionService(api_key="test-key")
        mock_client = MagicMock()
        service._client = mock_client

        v3_response = {
            "is_commitment": True,
            "confidence": 0.7,
            "explanation": "Commitment but counterparty unknown.",
            "suggested_owner": "Kevin",
            "suggested_deadline": None,
            "deliverable": "the report",
            "counterparty": None,
            "user_relationship": "mine",
            "structure_complete": False,
        }
        mock_client.chat.completions.create.return_value = self._mock_openai_response(v3_response)

        result = service.classify(_make_candidate())
        assert result is not None
        assert result.structure_complete is False
        assert result.counterparty is None

    def test_v3_invalid_relationship_normalized(self):
        """Invalid user_relationship value should be normalized to None."""
        service = ModelDetectionService(api_key="test-key")
        mock_client = MagicMock()
        service._client = mock_client

        v3_response = {
            "is_commitment": True,
            "confidence": 0.8,
            "explanation": "Test.",
            "suggested_owner": "Kevin",
            "suggested_deadline": None,
            "deliverable": "report",
            "counterparty": "Sarah",
            "user_relationship": "invalid_value",
            "structure_complete": True,
        }
        mock_client.chat.completions.create.return_value = self._mock_openai_response(v3_response)

        result = service.classify(_make_candidate())
        assert result is not None
        assert result.user_relationship is None

    def test_user_identity_injected_in_prompt(self):
        """User identity should appear in the user message when provided."""
        service = ModelDetectionService(api_key="test-key")
        context = {
            "trigger_text": "I'll do it",
            "pre_context": "",
            "post_context": "",
            "source_type": "slack",
        }
        msg = service._build_user_message(context, user_name="Kevin B", user_email="kevin@test.com")
        assert "Kevin B" in msg
        assert "kevin@test.com" in msg
        assert "[Current user]" in msg


# ---------------------------------------------------------------------------
# Hybrid Detection v3 — structure fields passed through
# ---------------------------------------------------------------------------

class TestHybridDetectionV3:
    """Test that HybridDetectionService passes through v3 structure fields."""

    def test_structure_fields_in_result(self):
        """Model result structure fields should be in hybrid result dict."""
        model_result = ModelDetectionResult(
            is_commitment=True,
            confidence=0.8,
            explanation="Commitment detected.",
            suggested_owner="Kevin",
            suggested_deadline="Friday",
            deliverable="Q1 report",
            counterparty="Sarah",
            user_relationship="mine",
            structure_complete=True,
        )
        mock_model = MagicMock(spec=ModelDetectionService)
        mock_model.classify.return_value = model_result

        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        result = service.process(candidate, user_name="Kevin", user_email="kevin@test.com")

        assert result["deliverable"] == "Q1 report"
        assert result["counterparty"] == "Sarah"
        assert result["user_relationship"] == "mine"
        assert result["structure_complete"] is True

    def test_user_identity_passed_to_model(self):
        """process() should pass user_name and user_email to model.classify()."""
        mock_model = MagicMock(spec=ModelDetectionService)
        mock_model.classify.return_value = None  # model returns None

        service = HybridDetectionService(model_service=mock_model)
        candidate = _make_candidate(confidence_score=Decimal("0.55"))
        service.process(candidate, user_name="Kevin B", user_email="kevin@test.com")

        mock_model.classify.assert_called_once_with(
            candidate, user_name="Kevin B", user_email="kevin@test.com"
        )


# ---------------------------------------------------------------------------
# Surfacing Router — structure_complete gate
# ---------------------------------------------------------------------------

class TestSurfacingStructureGate:
    """Test that surfacing router respects structure_complete and user_relationship."""

    def test_structure_incomplete_never_surfaced(self):
        """Commitments with structure_complete=False should never be surfaced."""
        c = _make_commitment(structure_complete=False)
        result = route(c)
        assert result.surface is None
        assert "structure incomplete" in result.reason

    def test_structure_complete_can_be_surfaced(self):
        """Commitments with structure_complete=True should pass the gate."""
        c = _make_commitment(
            structure_complete=True,
            user_relationship="mine",
            confidence_commitment=Decimal("0.9"),
            confidence_actionability=Decimal("0.8"),
        )
        result = route(c)
        # Should get routed somewhere (not held by structure gate)
        assert "structure incomplete" not in (result.reason or "")

    def test_watching_never_surfaced(self):
        """Commitments with user_relationship='watching' should not be surfaced."""
        c = _make_commitment(user_relationship="watching")
        result = route(c)
        assert result.surface is None
        assert "watching" in result.reason

    def test_mine_can_be_surfaced(self):
        """Commitments with user_relationship='mine' should pass the relationship gate."""
        c = _make_commitment(
            user_relationship="mine",
            confidence_commitment=Decimal("0.9"),
            confidence_actionability=Decimal("0.8"),
        )
        result = route(c)
        assert "watching" not in (result.reason or "")

    def test_contributing_can_be_surfaced(self):
        """Commitments with user_relationship='contributing' should pass the relationship gate."""
        c = _make_commitment(
            user_relationship="contributing",
            confidence_commitment=Decimal("0.9"),
            confidence_actionability=Decimal("0.8"),
        )
        result = route(c)
        assert "watching" not in (result.reason or "")

    def test_null_relationship_passes_gate(self):
        """Pre-backfill commitments (user_relationship=None) should pass the relationship gate."""
        c = _make_commitment(user_relationship=None)
        result = route(c)
        assert "watching" not in (result.reason or "")


# ---------------------------------------------------------------------------
# UserRelationship enum
# ---------------------------------------------------------------------------

class TestUserRelationshipEnum:
    """Test that the UserRelationship enum has the correct values."""

    def test_enum_values(self):
        from app.models.enums import UserRelationship
        assert UserRelationship.mine.value == "mine"
        assert UserRelationship.contributing.value == "contributing"
        assert UserRelationship.watching.value == "watching"
        assert len(UserRelationship) == 3
