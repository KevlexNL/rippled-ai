"""Tests for requester + beneficiary fields across the detection pipeline.

Covers:
- ModelDetectionResult parsing (requester/beneficiary extraction)
- HybridDetectionService passthrough
- Owner resolver for requester/beneficiary
- Surfacing router: requester → mine, beneficiary-only → contributing/watching
- Schema serialization
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. ModelDetectionResult: requester + beneficiary fields
# ---------------------------------------------------------------------------

class TestModelDetectionResultFields:
    """requester and beneficiary should be captured from LLM response."""

    def test_parse_response_extracts_requester_and_beneficiary(self):
        from app.services.model_detection import ModelDetectionService

        svc = ModelDetectionService(api_key="test-key")

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps({
            "is_commitment": True,
            "confidence": 0.9,
            "explanation": "Matt asked Kevin to prepare the portal demo for Nadine",
            "suggested_owner": "Kevin",
            "suggested_deadline": None,
            "speech_act": "request",
            "deliverable": "prepare portal demo",
            "counterparty": "Matt",
            "user_relationship": "mine",
            "structure_complete": True,
            "requester": "Matt",
            "beneficiary": "Nadine",
        })

        result = svc._parse_response(response)
        assert result is not None
        assert result.requester == "Matt"
        assert result.beneficiary == "Nadine"

    def test_parse_response_handles_null_requester_beneficiary(self):
        from app.services.model_detection import ModelDetectionService

        svc = ModelDetectionService(api_key="test-key")

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps({
            "is_commitment": True,
            "confidence": 0.85,
            "explanation": "Self-commitment",
            "suggested_owner": "Kevin",
            "suggested_deadline": None,
            "speech_act": "self_commitment",
            "deliverable": "send the report",
            "counterparty": None,
            "user_relationship": "mine",
            "structure_complete": True,
            "requester": None,
            "beneficiary": None,
        })

        result = svc._parse_response(response)
        assert result is not None
        assert result.requester is None
        assert result.beneficiary is None

    def test_parse_response_handles_missing_requester_beneficiary_keys(self):
        """Backward compat: older LLM responses without requester/beneficiary should default to None."""
        from app.services.model_detection import ModelDetectionService

        svc = ModelDetectionService(api_key="test-key")

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps({
            "is_commitment": True,
            "confidence": 0.85,
            "explanation": "test",
            "suggested_owner": "Kevin",
            "suggested_deadline": None,
            "speech_act": "self_commitment",
            "deliverable": "send report",
            "counterparty": None,
            "user_relationship": "mine",
            "structure_complete": True,
            # No requester/beneficiary keys
        })

        result = svc._parse_response(response)
        assert result is not None
        assert result.requester is None
        assert result.beneficiary is None


# ---------------------------------------------------------------------------
# 2. HybridDetectionService: passthrough of requester/beneficiary
# ---------------------------------------------------------------------------

class TestHybridDetectionPassthrough:
    """requester and beneficiary should flow through hybrid detection result dict."""

    def test_hybrid_passes_through_requester_beneficiary(self):
        from app.services.hybrid_detection import HybridDetectionService
        from app.services.model_detection import ModelDetectionResult

        mock_model = MagicMock()
        mock_model.classify.return_value = ModelDetectionResult(
            is_commitment=True,
            confidence=0.85,
            explanation="test",
            suggested_owner="Kevin",
            suggested_deadline=None,
            speech_act="request",
            deliverable="prepare demo",
            counterparty="Matt",
            user_relationship="mine",
            structure_complete=True,
            requester="Matt",
            beneficiary="Nadine",
        )

        svc = HybridDetectionService(model_service=mock_model)

        candidate = SimpleNamespace(
            id="cand-1",
            confidence_score=Decimal("0.50"),
            context_window={"trigger_text": "test"},
            raw_text="test",
        )

        result = svc.process(candidate)
        assert result["requester"] == "Matt"
        assert result["beneficiary"] == "Nadine"

    def test_hybrid_skips_model_returns_none_requester_beneficiary(self):
        """When model is skipped (high confidence), requester/beneficiary not in result."""
        from app.services.hybrid_detection import HybridDetectionService

        svc = HybridDetectionService(model_service=None)

        candidate = SimpleNamespace(
            id="cand-2",
            confidence_score=Decimal("0.90"),
            context_window={"trigger_text": "test"},
            raw_text="test",
        )

        result = svc.process(candidate)
        # When model is not called, these keys shouldn't be present
        assert "requester" not in result
        assert "beneficiary" not in result


# ---------------------------------------------------------------------------
# 3. Owner resolver: resolve requester/beneficiary against identity profiles
# ---------------------------------------------------------------------------

class TestResolveParty:
    """resolve_party_sync should match names/emails against identity profiles."""

    def test_resolve_party_matches_name(self):
        from app.services.identity.owner_resolver import resolve_party_sync

        mock_profile = SimpleNamespace(
            identity_value="Matt Johnson",
            identity_type="name",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_profile]

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        result = resolve_party_sync("Matt", "user-123", mock_db)
        assert result == "user-123"

    def test_resolve_party_returns_none_for_no_match(self):
        from app.services.identity.owner_resolver import resolve_party_sync

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        result = resolve_party_sync("Unknown Person", "user-123", mock_db)
        assert result is None

    def test_resolve_party_returns_none_for_empty_input(self):
        from app.services.identity.owner_resolver import resolve_party_sync

        mock_db = MagicMock()
        result = resolve_party_sync("", "user-123", mock_db)
        assert result is None

        result = resolve_party_sync(None, "user-123", mock_db)
        assert result is None


# ---------------------------------------------------------------------------
# 4. Surfacing router: requester → mine treatment
# ---------------------------------------------------------------------------

class TestSurfacingRouterRequesterLogic:
    """When user is requester, commitment should be treated as 'mine'."""

    def _make_commitment(self, **overrides):
        defaults = {
            "confidence_commitment": Decimal("0.85"),
            "confidence_owner": Decimal("0.80"),
            "confidence_deadline": Decimal("0.70"),
            "confidence_delivery": Decimal("0.60"),
            "confidence_closure": Decimal("0.50"),
            "confidence_actionability": Decimal("0.80"),
            "ownership_ambiguity": None,
            "timing_ambiguity": None,
            "deliverable_ambiguity": None,
            "observe_until": None,
            "counterparty_type": "internal",
            "context_type": "internal",
            "structure_complete": True,
            "speech_act": "request",
            "user_relationship": "watching",
            "requester_resolved": None,
            "beneficiary_resolved": None,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_requester_is_user_overrides_watching_to_mine(self):
        """If requester_resolved matches user_id, user_relationship should be treated as 'mine'
        and the commitment should NOT be gated by the watching relationship filter."""
        from app.services.surfacing_router import route

        commitment = self._make_commitment(
            user_relationship="watching",
            requester_resolved="user-123",
        )
        # The surfacing router should check requester_resolved and NOT gate on watching
        result = route(commitment)
        # Should NOT be gated by watching relationship (may still be held for score reasons)
        assert "watching" not in result.reason

    def test_beneficiary_only_remains_watching(self):
        """If user is only the beneficiary (not requester/owner), stays watching."""
        from app.services.surfacing_router import route

        commitment = self._make_commitment(
            user_relationship="watching",
            requester_resolved=None,
            beneficiary_resolved="user-123",
        )
        result = route(commitment)
        assert result.surface is None
        assert "watching" in result.reason


# ---------------------------------------------------------------------------
# 5. Schema: requester/beneficiary serialization
# ---------------------------------------------------------------------------

class TestSchemaFields:
    """Pydantic schemas should include requester/beneficiary fields."""

    def test_commitment_read_has_requester_beneficiary(self):
        from app.models.schemas import CommitmentRead
        fields = CommitmentRead.model_fields
        assert "requester_name" in fields
        assert "requester_email" in fields
        assert "beneficiary_name" in fields
        assert "beneficiary_email" in fields

    def test_commitment_create_has_requester_beneficiary(self):
        from app.models.schemas import CommitmentCreate
        fields = CommitmentCreate.model_fields
        assert "requester_name" in fields
        assert "requester_email" in fields
        assert "beneficiary_name" in fields
        assert "beneficiary_email" in fields


# ---------------------------------------------------------------------------
# 6. ORM: requester/beneficiary columns
# ---------------------------------------------------------------------------

class TestORMFields:
    """ORM Commitment model should have requester/beneficiary columns."""

    def test_orm_commitment_has_requester_fields(self):
        from app.models.orm import Commitment
        mapper = Commitment.__table__.columns
        assert "requester_name" in mapper
        assert "requester_email" in mapper

    def test_orm_commitment_has_beneficiary_fields(self):
        from app.models.orm import Commitment
        mapper = Commitment.__table__.columns
        assert "beneficiary_name" in mapper
        assert "beneficiary_email" in mapper

    def test_orm_commitment_has_resolved_fields(self):
        from app.models.orm import Commitment
        mapper = Commitment.__table__.columns
        assert "requester_resolved" in mapper
        assert "beneficiary_resolved" in mapper


# ---------------------------------------------------------------------------
# 7. Deprecation: counterparty fields still exist
# ---------------------------------------------------------------------------

class TestDeprecatedCounterpartyFieldsStillExist:
    """Old counterparty_* fields must still exist (deprecation, not removal)."""

    def test_counterparty_fields_still_on_orm(self):
        from app.models.orm import Commitment
        mapper = Commitment.__table__.columns
        assert "counterparty_name" in mapper
        assert "counterparty_email" in mapper
        assert "counterparty_type" in mapper
        assert "counterparty_resolved" in mapper

    def test_counterparty_fields_still_on_schema(self):
        from app.models.schemas import CommitmentRead
        fields = CommitmentRead.model_fields
        assert "counterparty_name" in fields
        assert "counterparty_email" in fields
        assert "counterparty_type" in fields
