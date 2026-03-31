"""Tests for [R5] context_tags on commitments.

Covers:
1. _derive_context_tags returns correct tag for each source type
2. promote_candidate populates context_tags on the commitment
3. Unknown / None source type returns None
4. CommitmentRead schema exposes context_tags field
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.clarification.promoter import _derive_context_tags, promote_candidate
from app.services.clarification.analyzer import AnalysisResult


# ---------------------------------------------------------------------------
# Candidate factory
# ---------------------------------------------------------------------------

def _make_candidate(source_type: str = "email", **kwargs) -> types.SimpleNamespace:
    _future = datetime.now(timezone.utc) + timedelta(hours=24)
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "originating_item_id": "item-001",
        "source_type": source_type,
        "raw_text": "I'll send the report tomorrow",
        "trigger_class": "explicit_commitment",
        "is_explicit": True,
        "flag_reanalysis": False,
        "confidence_score": Decimal("0.75"),
        "linked_entities": {},
        "context_window": {},
        "observe_until": _future,
        "priority_hint": None,
        "was_promoted": False,
        "was_discarded": False,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Unit: _derive_context_tags
# ---------------------------------------------------------------------------

class TestDeriveContextTags:
    def test_slack_source(self):
        candidate = _make_candidate(source_type="slack")
        assert _derive_context_tags(candidate) == ["slack"]

    def test_email_source(self):
        candidate = _make_candidate(source_type="email")
        assert _derive_context_tags(candidate) == ["email"]

    def test_meeting_source(self):
        candidate = _make_candidate(source_type="meeting")
        assert _derive_context_tags(candidate) == ["meeting"]

    def test_unknown_source_type_returns_none(self):
        candidate = _make_candidate(source_type="telegram")
        assert _derive_context_tags(candidate) is None

    def test_none_source_type_returns_none(self):
        candidate = _make_candidate(source_type=None)
        assert _derive_context_tags(candidate) is None

    def test_case_insensitive(self):
        candidate = _make_candidate(source_type="SLACK")
        assert _derive_context_tags(candidate) == ["slack"]

    def test_case_insensitive_meeting(self):
        candidate = _make_candidate(source_type="Meeting")
        assert _derive_context_tags(candidate) == ["meeting"]


# ---------------------------------------------------------------------------
# Integration: promote_candidate sets context_tags
# ---------------------------------------------------------------------------

class TestPromoteContextTags:
    """promote_candidate must set context_tags on the resulting Commitment."""

    def _make_db(self):
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()
        return db

    def _make_analysis(self) -> AnalysisResult:
        return AnalysisResult(
            issue_types=[],
            issue_severity="none",
            why_this_matters="",
            observation_window_status="open",
            surface_recommendation="do_nothing",
        )

    def test_slack_commitment_has_slack_tag(self):
        candidate = _make_candidate(source_type="slack")
        db = self._make_db()
        commitment = promote_candidate(candidate, db, self._make_analysis())
        assert commitment.context_tags == ["slack"]

    def test_email_commitment_has_email_tag(self):
        candidate = _make_candidate(source_type="email")
        db = self._make_db()
        commitment = promote_candidate(candidate, db, self._make_analysis())
        assert commitment.context_tags == ["email"]

    def test_meeting_commitment_has_meeting_tag(self):
        candidate = _make_candidate(source_type="meeting")
        db = self._make_db()
        commitment = promote_candidate(candidate, db, self._make_analysis())
        assert commitment.context_tags == ["meeting"]

    def test_unknown_source_commitment_has_none_tags(self):
        candidate = _make_candidate(source_type="other")
        db = self._make_db()
        commitment = promote_candidate(candidate, db, self._make_analysis())
        assert commitment.context_tags is None


# ---------------------------------------------------------------------------
# Schema: CommitmentRead has context_tags field
# ---------------------------------------------------------------------------

class TestCommitmentReadSchema:
    def test_context_tags_field_exists(self):
        from app.models.schemas import CommitmentRead
        assert "context_tags" in CommitmentRead.model_fields

    def test_context_tags_defaults_to_none(self):
        from app.models.schemas import CommitmentRead
        field = CommitmentRead.model_fields["context_tags"]
        assert field.default is None

    def test_context_tags_in_commitment_create(self):
        from app.models.schemas import CommitmentCreate
        assert "context_tags" in CommitmentCreate.model_fields

    def test_context_tags_in_commitment_update(self):
        from app.models.schemas import CommitmentUpdate
        assert "context_tags" in CommitmentUpdate.model_fields
