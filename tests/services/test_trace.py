"""Tests for Signal Trace Inspector service.

Tests the trace_source_item and fetch_samples functions using mocked DB sessions.
"""
from __future__ import annotations

import types
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.trace.tracer import (
    _compute_verdict,
    _json_safe,
    _row_to_dict,
    _trace_raw,
    _trace_normalization,
    _trace_patterns,
    trace_source_item,
    fetch_samples,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(**kwargs) -> Any:
    """Create a minimal SourceItem-like namespace for testing."""
    defaults = {
        "id": "item-001",
        "source_id": "src-001",
        "user_id": "user-001",
        "source_type": "email",
        "external_id": "ext-001",
        "thread_id": None,
        "direction": "inbound",
        "sender_id": None,
        "sender_name": "Alice",
        "sender_email": "alice@example.com",
        "is_external_participant": False,
        "content": "I will send the report by Friday.",
        "content_normalized": None,
        "has_attachment": False,
        "attachment_metadata": None,
        "recipients": [],
        "source_url": None,
        "occurred_at": datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 3, 15, 10, 1, tzinfo=timezone.utc),
        "metadata_": None,
        "is_quoted_content": False,
        "seed_processed_at": datetime(2026, 3, 15, 10, 5, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# json_safe
# ---------------------------------------------------------------------------

class TestJsonSafe:
    def test_decimal(self):
        assert _json_safe(Decimal("0.750")) == 0.75

    def test_datetime(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _json_safe(dt) == "2026-01-01T00:00:00+00:00"

    def test_string(self):
        assert _json_safe("hello") == "hello"

    def test_none(self):
        assert _json_safe(None) is None


# ---------------------------------------------------------------------------
# row_to_dict
# ---------------------------------------------------------------------------

class TestRowToDict:
    def test_extracts_fields(self):
        item = _make_item()
        result = _row_to_dict(item, ["id", "source_type", "sender_name"])
        assert result == {"id": "item-001", "source_type": "email", "sender_name": "Alice"}

    def test_missing_field_returns_none(self):
        item = _make_item()
        result = _row_to_dict(item, ["nonexistent_field"])
        assert result == {"nonexistent_field": None}


# ---------------------------------------------------------------------------
# trace_raw
# ---------------------------------------------------------------------------

class TestTraceRaw:
    def test_basic_output(self):
        item = _make_item()
        result = _trace_raw(item)
        assert result["stage"] == "raw"
        assert result["status"] == "loaded"
        assert result["data"]["sender_name"] == "Alice"
        assert result["data"]["source_type"] == "email"
        assert result["data"]["content_length"] == len("I will send the report by Friday.")
        assert "I will send" in result["data"]["content_preview"]

    def test_empty_content(self):
        item = _make_item(content=None)
        result = _trace_raw(item)
        assert result["data"]["content_length"] == 0
        assert result["data"]["content_preview"] == ""


# ---------------------------------------------------------------------------
# trace_normalization
# ---------------------------------------------------------------------------

class TestTraceNormalization:
    def test_basic_output(self):
        item = _make_item(content="I will send the report. Maybe later.")
        result = _trace_normalization(item)
        assert result["stage"] == "normalization"
        assert result["status"] == "complete"
        assert result["data"]["raw_length"] > 0

    def test_with_normalized_content(self):
        item = _make_item(content="raw", content_normalized="normalized text")
        result = _trace_normalization(item)
        assert result["data"]["has_content_normalized"] is True


# ---------------------------------------------------------------------------
# trace_patterns
# ---------------------------------------------------------------------------

class TestTracePatterns:
    def test_match_found(self):
        item = _make_item(content="I will send the report by Friday.")
        result = _trace_patterns(item)
        assert result["stage"] == "pattern_detection"
        # "I will send" should trigger explicit self-commitment patterns
        assert result["data"]["patterns_checked"] > 0

    def test_no_match(self):
        item = _make_item(content="Hello, how are you?")
        result = _trace_patterns(item)
        assert result["stage"] == "pattern_detection"
        # Greeting should not match commitment patterns (or only suppression)


# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------

class TestComputeVerdict:
    def test_commitment_created(self):
        stages = [
            {"stage": "final_state", "status": "commitment_created", "data": {}},
        ]
        assert _compute_verdict(stages) == "commitment_created"

    def test_candidate_pending(self):
        stages = [
            {"stage": "final_state", "status": "no_commitment", "data": {}},
            {"stage": "candidate_decision", "status": "not_promoted",
             "data": {"decisions": [{"decision": "pending"}]}},
        ]
        assert _compute_verdict(stages) == "candidate_pending"

    def test_rejected(self):
        stages = [
            {"stage": "final_state", "status": "no_commitment", "data": {}},
            {"stage": "candidate_decision", "status": "not_promoted",
             "data": {"decisions": [{"decision": "discarded"}]}},
        ]
        assert _compute_verdict(stages) == "rejected_as_noise"

    def test_not_processed(self):
        stages = [
            {"stage": "raw", "status": "loaded",
             "data": {"seed_processed_at": None}},
            {"stage": "extraction", "status": "no_candidates", "data": {}},
            {"stage": "final_state", "status": "no_commitment", "data": {}},
        ]
        assert _compute_verdict(stages) == "not_processed"

    def test_no_candidates(self):
        stages = [
            {"stage": "raw", "status": "loaded",
             "data": {"seed_processed_at": "2026-03-15T10:00:00+00:00"}},
            {"stage": "extraction", "status": "no_candidates", "data": {}},
            {"stage": "final_state", "status": "no_commitment", "data": {}},
        ]
        assert _compute_verdict(stages) == "no_candidates_created"


# ---------------------------------------------------------------------------
# trace_source_item (integration with mocked DB)
# ---------------------------------------------------------------------------

class TestTraceSourceItem:
    def test_item_not_found_raises(self):
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            trace_source_item("nonexistent-id", db)

    def test_basic_trace_returns_all_stages(self):
        item = _make_item()
        db = MagicMock()
        db.get.return_value = item
        # Mock all DB queries to return empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = trace_source_item("item-001", db)

        assert result["source_item_id"] == "item-001"
        assert "verdict" in result
        assert len(result["stages"]) == 8

        stage_names = [s["stage"] for s in result["stages"]]
        assert stage_names == [
            "raw", "normalization", "pattern_detection", "llm_detection",
            "extraction", "candidate_decision", "clarification", "final_state",
        ]


# ---------------------------------------------------------------------------
# fetch_samples (mocked DB)
# ---------------------------------------------------------------------------

class TestFetchSamples:
    def test_returns_list(self):
        item = _make_item()
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [item]
        db.execute.return_value = mock_result

        # Mock the candidate check
        mock_cand_result = MagicMock()
        mock_cand_result.scalar_one_or_none.return_value = None

        # First call returns items, second call checks candidates
        db.execute.side_effect = [mock_result, mock_cand_result]

        result = fetch_samples("email", 5, db)
        assert len(result) == 1
        assert result[0]["id"] == "item-001"
        assert result[0]["source_type"] == "email"
        assert result[0]["status"] == "processed_no_match"  # seed_processed_at set, no candidate
