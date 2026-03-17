"""Tests for detection audit service — write_audit_entry and create_audit_entry."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from app.services.detection.audit import create_audit_entry, write_audit_entry


class TestCreateAuditEntry:
    """Test create_audit_entry returns a complete dict."""

    def test_basic_fields(self):
        entry = create_audit_entry(
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_3",
            commitment_created=True,
        )
        assert entry["source_item_id"] == "item-1"
        assert entry["user_id"] == "user-1"
        assert entry["tier_used"] == "tier_3"
        assert entry["commitment_created"] is True

    def test_llm_fields(self):
        entry = create_audit_entry(
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_3",
            prompt_version="seed-v1",
            raw_prompt="test prompt",
            raw_response="test response",
            parsed_result=[{"trigger_phrase": "I will"}],
            tokens_in=100,
            tokens_out=50,
            cost_estimate=Decimal("0.01"),
            model="claude-sonnet-4-6",
            duration_ms=250,
        )
        assert entry["prompt_version"] == "seed-v1"
        assert entry["raw_prompt"] == "test prompt"
        assert entry["raw_response"] == "test response"
        assert entry["parsed_result"] == [{"trigger_phrase": "I will"}]
        assert entry["tokens_in"] == 100
        assert entry["tokens_out"] == 50
        assert entry["cost_estimate"] == Decimal("0.01")
        assert entry["model"] == "claude-sonnet-4-6"
        assert entry["duration_ms"] == 250

    def test_error_detail(self):
        entry = create_audit_entry(
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_3",
            error_detail="Parse error: JSONDecodeError",
        )
        assert entry["error_detail"] == "Parse error: JSONDecodeError"

    def test_defaults_to_none_for_llm_fields(self):
        entry = create_audit_entry(
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_1",
        )
        assert entry["prompt_version"] is None
        assert entry["raw_prompt"] is None
        assert entry["raw_response"] is None
        assert entry["parsed_result"] is None
        assert entry["tokens_in"] is None
        assert entry["tokens_out"] is None
        assert entry["cost_estimate"] is None
        assert entry["model"] is None
        assert entry["duration_ms"] is None
        assert entry["error_detail"] is None


class TestWriteAuditEntry:
    """Test write_audit_entry creates a DetectionAudit and flushes."""

    def test_writes_to_db_with_all_fields(self):
        db = MagicMock()
        entry = write_audit_entry(
            db,
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_3",
            commitment_created=True,
            prompt_version="seed-v1",
            raw_prompt="test prompt",
            raw_response="test response",
            parsed_result=[{"trigger_phrase": "I will"}],
            tokens_in=100,
            tokens_out=50,
            cost_estimate=Decimal("0.01"),
            model="claude-sonnet-4-6",
            duration_ms=250,
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert entry.source_item_id == "item-1"
        assert entry.prompt_version == "seed-v1"
        assert entry.raw_prompt == "test prompt"
        assert entry.raw_response == "test response"
        assert entry.tokens_in == 100
        assert entry.tokens_out == 50
        assert entry.model == "claude-sonnet-4-6"

    def test_backward_compatible_with_existing_callers(self):
        """Existing callers that don't pass LLM fields should still work."""
        db = MagicMock()
        entry = write_audit_entry(
            db,
            source_item_id="item-1",
            user_id="user-1",
            tier_used="tier_1",
            matched_phrase="I will send",
            confidence=Decimal("0.85"),
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert entry.tier_used == "tier_1"
        assert entry.matched_phrase == "I will send"
        assert entry.prompt_version is None
        assert entry.raw_prompt is None
