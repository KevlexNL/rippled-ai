"""Tests for candidate-to-commitment promotion — WO-RIPPLED-CANDIDATE-PROMOTION-BROKEN.

Tests the three bugs identified:
1. Silent exception swallowing in run_clarification_task (no error logging)
2. NULL observe_until candidates never picked up by clarification sweep
3. End-to-end promotion: candidate with confidence 0.7 → commitment created
4. Backfill script promotes eligible candidates
"""
from __future__ import annotations

import logging
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from app.models.enums import AmbiguityType
from app.services.clarification.analyzer import AnalysisResult, analyze_candidate
from app.services.clarification.promoter import promote_candidate


# ---------------------------------------------------------------------------
# Candidate factory (matches test_clarification.py style)
# ---------------------------------------------------------------------------

def _make_candidate(**kwargs) -> types.SimpleNamespace:
    """Create a minimal CommitmentCandidate-like namespace for testing."""
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
# Bug 1: Silent exception swallowing — task must log errors
# ---------------------------------------------------------------------------

class TestTaskErrorLogging:
    """run_clarification_task must log the actual exception on generic failures."""

    def test_generic_exception_is_logged_before_retry(self):
        """When run_clarification raises a non-ValueError exception,
        the task handler must log it at ERROR level before retrying."""
        db_error = RuntimeError("connection refused: could not connect to server")

        with patch("app.tasks.get_sync_session") as mock_session_ctx, \
             patch("app.tasks.run_clarification", side_effect=db_error), \
             patch("app.tasks.logger") as mock_logger, \
             patch("app.tasks.run_clarification_task.retry", side_effect=Exception("retry")) as mock_retry:

            mock_session = MagicMock()
            mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(Exception, match="retry"):
                from app.tasks import run_clarification_task
                run_clarification_task("candidate-123")

            # The key assertion: the error must be logged with the actual exception
            mock_logger.error.assert_called_once()
            log_args = mock_logger.error.call_args
            assert "candidate-123" in str(log_args)
            assert "connection refused" in str(log_args)


# ---------------------------------------------------------------------------
# Bug 2: NULL observe_until — sweep must treat NULL as expired
# ---------------------------------------------------------------------------

class TestSweepNullObserveUntil:
    """Candidates with observe_until=NULL and confidence < 0.75 must be
    picked up by the clarification sweep (treated as observation expired)."""

    def test_sweep_query_includes_null_observe_until(self):
        """run_clarification_batch must include candidates where
        observe_until IS NULL in addition to observe_until <= now."""
        from sqlalchemy import select, and_, or_
        from app.models.orm import CommitmentCandidate

        # We test that the sweep query is constructed to handle NULL.
        # The actual query in run_clarification_batch should include:
        #   OR observe_until IS NULL
        # We verify by checking the generated SQL from the task.

        # Import the batch function and inspect its behavior
        from app.tasks import run_clarification_batch

        # Mock the session to capture the query
        mock_session = MagicMock()
        mock_session.execute = MagicMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        with patch("app.tasks.get_sync_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            run_clarification_batch()

        # Inspect the SQL statement that was executed
        executed_stmt = mock_session.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))

        # The compiled SQL must contain IS NULL check for observe_until
        assert "IS NULL" in compiled.upper(), (
            f"Sweep query does not handle NULL observe_until. SQL: {compiled}"
        )


# ---------------------------------------------------------------------------
# Bug 3: End-to-end promotion (confidence 0.7)
# ---------------------------------------------------------------------------

class TestEndToEndPromotion:
    """A candidate with confidence 0.7 must be promoted to a commitment
    after its observation window expires."""

    def test_candidate_confidence_070_promoted_after_window_expires(self):
        """Create a candidate with confidence=0.7, expired observe_until.
        Verify promotion creates a Commitment and sets was_promoted=True."""
        candidate = _make_candidate(
            confidence_score=Decimal("0.70"),
            observe_until=datetime.now(timezone.utc) - timedelta(hours=1),
            linked_entities={"people": ["Alice"], "dates": []},
            context_window={},
        )

        db = MagicMock()
        db.add = MagicMock()

        # Analyze + promote
        analysis = analyze_candidate(candidate)
        commitment = promote_candidate(candidate, db, analysis)

        # Commitment was created
        assert commitment is not None
        assert commitment.title  # non-empty title
        assert commitment.user_id == "user-001"
        assert commitment.confidence_commitment == Decimal("0.70")
        assert commitment.lifecycle_state in ("proposed", "needs_clarification")

        # Candidate marked as promoted
        assert candidate.was_promoted is True

        # DB objects were added (commitment + join record + ambiguity rows)
        assert db.add.call_count >= 2  # at least commitment + join record

    def test_full_clarification_flow_with_confidence_070(self):
        """Full clarification flow: candidate with 0.7 confidence and expired
        window → returns 'clarified' with a commitment_id."""
        from app.services.clarification.clarifier import run_clarification
        from app.models.orm import Commitment

        candidate = _make_candidate(
            confidence_score=Decimal("0.70"),
            observe_until=datetime.now(timezone.utc) - timedelta(hours=1),
            linked_entities={"people": ["Alice"], "dates": []},
            context_window={},
        )

        db = MagicMock()
        db.get = MagicMock(return_value=candidate)
        db.add = MagicMock()
        db.flush = MagicMock()

        # Patch out CounterpartyExtractor and resolve_party_sync to avoid
        # needing real DB for identity resolution
        with patch("app.services.clarification.clarifier.resolve_party_sync", return_value=None), \
             patch("app.services.clarification.clarifier.CounterpartyExtractor"):
            result = run_clarification(str(candidate.id), db)

        assert result["status"] == "clarified"
        assert "commitment_id" in result
        assert candidate.was_promoted is True

    def test_promotion_is_idempotent(self):
        """Promoting an already-promoted candidate raises ValueError."""
        candidate = _make_candidate(was_promoted=True)
        db = MagicMock()
        analysis = AnalysisResult()

        with pytest.raises(ValueError, match="already promoted"):
            promote_candidate(candidate, db, analysis)


# ---------------------------------------------------------------------------
# Bug 4: Batch sweep logging
# ---------------------------------------------------------------------------

class TestBatchSweepLogging:
    """The clarification batch sweep must log how many candidates were found
    and enqueued, so promotion activity is visible in Railway logs."""

    def test_batch_logs_enqueued_count(self):
        """run_clarification_batch must log the count of enqueued tasks."""
        from app.tasks import run_clarification_batch

        mock_session = MagicMock()
        # Simulate finding 3 candidates
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = ["id-1", "id-2", "id-3"]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("app.tasks.get_sync_session") as mock_ctx, \
             patch("app.tasks.run_clarification_task") as mock_task, \
             patch("app.tasks.logger") as mock_logger:

            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = run_clarification_batch()

        assert result["enqueued"] == 3

        # Must log the count at INFO level
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        found_log = any("3" in c and ("enqueue" in c.lower() or "candidate" in c.lower()) for c in info_calls)
        assert found_log, (
            f"Batch sweep must log enqueued count. Actual log calls: {info_calls}"
        )
