"""Tests for fragment gate — WO-RIPPLED-FRAGMENT-GATE.

Short text fragments under 10 characters must be rejected before promotion.
Known regression: `done`, `done.`, `done. 🔥`, `We'll`, `well.`, `well!`,
`well?`, `actually`, `instead?`, `Will you?` were all promoted.
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.enums import AmbiguityType
from app.services.clarification.analyzer import AnalysisResult, analyze_candidate
from app.services.clarification.promoter import (
    MIN_CANDIDATE_TEXT_LENGTH,
    promote_candidate,
)


# ---------------------------------------------------------------------------
# Candidate factory
# ---------------------------------------------------------------------------

def _make_candidate(**kwargs) -> types.SimpleNamespace:
    _future = datetime.now(timezone.utc) + timedelta(hours=24)
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "originating_item_id": "item-001",
        "source_type": "email",
        "raw_text": "I'll send the revised proposal by Friday",
        "trigger_class": "explicit_commitment",
        "is_explicit": True,
        "flag_reanalysis": False,
        "confidence_score": Decimal("0.70"),
        "linked_entities": {"people": ["Alice"], "dates": ["2026-03-15"]},
        "context_window": {},
        "observe_until": _future,
        "priority_hint": None,
        "was_promoted": False,
        "was_discarded": False,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Threshold constant
# ---------------------------------------------------------------------------

class TestMinLengthConstant:
    """MIN_CANDIDATE_TEXT_LENGTH must be 10."""

    def test_threshold_is_10(self):
        assert MIN_CANDIDATE_TEXT_LENGTH == 10


# ---------------------------------------------------------------------------
# promote_candidate rejects short fragments
# ---------------------------------------------------------------------------

class TestPromoteCandidateRejectsFragments:
    """promote_candidate must raise ValueError and discard candidates
    whose raw_text is shorter than MIN_CANDIDATE_TEXT_LENGTH."""

    @pytest.mark.parametrize("fragment", [
        "done",
        "done.",
        "done. 🔥",
        "We'll",
        "well.",
        "well!",
        "well?",
        "actually",
        "instead?",
        "Will you?",
        "",
        "   ",
        "ok",
        "yes",
        "no",
    ])
    def test_short_fragment_rejected(self, fragment: str):
        candidate = _make_candidate(raw_text=fragment)
        db = MagicMock()
        analysis = AnalysisResult()

        with pytest.raises(ValueError, match="too short"):
            promote_candidate(candidate, db, analysis)

        # Candidate must be marked as discarded
        assert candidate.was_discarded is True
        # DB must NOT have been called (no commitment created)
        db.add.assert_not_called()

    def test_valid_text_still_promotes(self):
        """Text at or above the threshold must still promote normally."""
        candidate = _make_candidate(raw_text="I'll send the report by Friday")
        db = MagicMock()
        analysis = AnalysisResult()

        commitment = promote_candidate(candidate, db, analysis)
        assert commitment is not None
        assert candidate.was_promoted is True

    def test_exactly_at_threshold_promotes(self):
        """Text with exactly MIN_CANDIDATE_TEXT_LENGTH chars promotes."""
        text = "a" * MIN_CANDIDATE_TEXT_LENGTH
        candidate = _make_candidate(raw_text=text)
        db = MagicMock()
        analysis = AnalysisResult()

        commitment = promote_candidate(candidate, db, analysis)
        assert commitment is not None

    def test_one_below_threshold_rejected(self):
        """Text one char below threshold is rejected."""
        text = "a" * (MIN_CANDIDATE_TEXT_LENGTH - 1)
        candidate = _make_candidate(raw_text=text)
        db = MagicMock()
        analysis = AnalysisResult()

        with pytest.raises(ValueError, match="too short"):
            promote_candidate(candidate, db, analysis)

    def test_whitespace_only_stripped_then_rejected(self):
        """Whitespace-padded short text is stripped before length check."""
        candidate = _make_candidate(raw_text="   done   ")
        db = MagicMock()
        analysis = AnalysisResult()

        with pytest.raises(ValueError, match="too short"):
            promote_candidate(candidate, db, analysis)
        assert candidate.was_discarded is True


# ---------------------------------------------------------------------------
# Clarification sweep filters short fragments
# ---------------------------------------------------------------------------

class TestSweepFiltersFragments:
    """run_clarification_batch must exclude candidates with short raw_text."""

    def test_sweep_query_filters_short_text(self):
        from app.tasks import run_clarification_batch

        mock_session = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("app.tasks.get_sync_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            run_clarification_batch()

        # Inspect generated SQL — must include a length filter
        executed_stmt = mock_session.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "length" in compiled.lower() or "char_length" in compiled.lower() or "len" in compiled.lower(), (
            f"Sweep query must filter on text length. SQL: {compiled}"
        )
