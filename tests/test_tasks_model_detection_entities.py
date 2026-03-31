"""Tests for model detection task — linked_entities enrichment.

Verifies that run_model_detection_pass stores speech_act, structure_complete,
user_relationship, and deliverable in candidate.linked_entities alongside
requester and beneficiary.
"""
from __future__ import annotations

import types
from decimal import Decimal
from unittest.mock import MagicMock, patch


def _make_candidate(**kwargs):
    defaults = {
        "id": "cand-ent-001",
        "user_id": "user-001",
        "source_type": "email",
        "raw_text": "I'll send the report by Friday",
        "confidence_score": Decimal("0.55"),
        "originating_item_id": "item-001",
        "context_window": {},
        "was_promoted": False,
        "was_discarded": False,
        "discard_reason": None,
        "model_confidence": None,
        "model_classification": None,
        "model_explanation": None,
        "model_called_at": None,
        "detection_method": None,
        "linked_entities": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_hybrid_result(**kwargs):
    defaults = {
        "detection_method": "model-assisted",
        "model_called": True,
        "was_discarded": False,
        "discard_reason": None,
        "model_confidence": 0.85,
        "model_classification": "commitment",
        "model_explanation": "Clear commitment",
        "model_called_at": None,
        "requester": "Alice",
        "beneficiary": "Bob",
        "speech_act": "request",
        "structure_complete": True,
        "user_relationship": "mine",
        "deliverable": "Q2 report",
        "audit_raw_prompt": None,
        "audit_raw_response": None,
        "audit_parsed_result": None,
        "audit_tokens_in": None,
        "audit_tokens_out": None,
        "audit_model": None,
        "audit_duration_ms": None,
        "audit_prompt_version": None,
        "audit_error_detail": None,
    }
    defaults.update(kwargs)
    return defaults


def _run_with_result(hybrid_result):
    """Helper: run model detection task with given hybrid result, return candidate."""
    from app.tasks import run_model_detection_pass

    candidate = _make_candidate()

    mock_hybrid = MagicMock()
    mock_hybrid.process.return_value = hybrid_result

    mock_db = MagicMock()
    mock_db.get.return_value = candidate

    with patch("app.services.model_detection.ModelDetectionService"), \
         patch("app.services.hybrid_detection.HybridDetectionService", return_value=mock_hybrid), \
         patch("app.tasks.get_sync_session") as mock_session, \
         patch("app.tasks.settings") as mock_settings:
        mock_settings.model_detection_enabled = True
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4.1-mini"
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        run_model_detection_pass("cand-ent-001")

    return candidate


class TestModelDetectionLinkedEntities:
    """Verify model detection stores classification fields in linked_entities."""

    def test_stores_speech_act_in_linked_entities(self):
        candidate = _run_with_result(_make_hybrid_result(speech_act="request"))
        entities = candidate.linked_entities or {}
        assert entities.get("speech_act") == "request"

    def test_stores_structure_complete_in_linked_entities(self):
        candidate = _run_with_result(_make_hybrid_result(structure_complete=True))
        entities = candidate.linked_entities or {}
        assert entities.get("structure_complete") is True

    def test_stores_user_relationship_in_linked_entities(self):
        candidate = _run_with_result(_make_hybrid_result(user_relationship="mine"))
        entities = candidate.linked_entities or {}
        assert entities.get("user_relationship") == "mine"

    def test_stores_deliverable_in_linked_entities(self):
        candidate = _run_with_result(_make_hybrid_result(deliverable="Q2 report"))
        entities = candidate.linked_entities or {}
        assert entities.get("deliverable") == "Q2 report"
