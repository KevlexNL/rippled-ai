"""Tests for seed_detector classification + extraction — WO-RIPPLED-CLASSIFICATION-EXTRACTION.

Verifies that _create_commitment_and_signal:
1. Defaults speech_act to "self_commitment" when LLM returns None/invalid
2. Sets structure_complete based on extraction completeness
3. Populates requester_name and beneficiary_name from LLM data
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.orm import Commitment, CommitmentSignal, SourceItem


def _make_source_item() -> MagicMock:
    item = MagicMock(spec=SourceItem)
    item.id = "test-item-id"
    item.source_type = "email"
    return item


def _make_db():
    """Create a mock DB session that captures added objects."""
    db = MagicMock()
    added = []

    def capture_add(obj):
        added.append(obj)

    db.add.side_effect = capture_add
    db.flush.return_value = None
    db._added = added
    return db


def _get_commitment(db) -> Commitment:
    """Return the first Commitment object added to the session."""
    for obj in db._added:
        if isinstance(obj, Commitment):
            return obj
    raise AssertionError("No Commitment was added to the session")  # noqa: TRY003


class TestSeedDetectorSpeechActDefault:
    """speech_act must default to 'self_commitment' when LLM omits or returns invalid value."""

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_speech_act_defaults_when_missing(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "I will send the report by Friday",
            "who_committed": "Alice",
            "title": "Send report",
            "confidence": 0.85,
            # No speech_act key at all
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.speech_act == "self_commitment"

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_speech_act_defaults_when_invalid(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "I will send the report",
            "who_committed": "Alice",
            "title": "Send report",
            "confidence": 0.85,
            "speech_act": "banana",  # invalid value
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.speech_act == "self_commitment"

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_speech_act_preserved_when_valid(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "Can you send the report?",
            "who_committed": "Alice",
            "title": "Send report",
            "confidence": 0.85,
            "speech_act": "request",
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.speech_act == "request"


class TestSeedDetectorStructureComplete:
    """structure_complete must be set based on extraction completeness."""

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_structure_complete_true_when_all_fields_present(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "I will send the report by Friday",
            "who_committed": "Alice",
            "directed_at": "Bob",
            "title": "Send report",
            "confidence": 0.85,
            "speech_act": "self_commitment",
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.structure_complete is True

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_structure_complete_false_when_fields_missing(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "Something needs to happen",
            "title": "Something",
            "confidence": 0.5,
            # No who_committed, no directed_at
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.structure_complete is False


class TestSeedDetectorEntityExtraction:
    """requester_name and beneficiary_name must be populated from LLM extraction."""

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_requester_and_beneficiary_set(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "I will send Alice the report",
            "who_committed": "Bob",
            "directed_at": "Alice",
            "title": "Send report",
            "confidence": 0.85,
            "speech_act": "self_commitment",
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.requester_name == "Bob"
        assert commitment.beneficiary_name == "Alice"

    @patch("app.services.detection.seed_detector.resolve_owner_sync", return_value=None)
    def test_beneficiary_none_when_not_directed(self, _mock_resolve):
        from app.services.detection.seed_detector import _create_commitment_and_signal

        c_data = {
            "trigger_phrase": "I will review the code",
            "who_committed": "Bob",
            # No directed_at
            "title": "Review code",
            "confidence": 0.85,
        }
        db = _make_db()
        _create_commitment_and_signal(db, "user-1", _make_source_item(), c_data)

        commitment = _get_commitment(db)
        assert commitment.requester_name == "Bob"
        assert commitment.beneficiary_name is None
