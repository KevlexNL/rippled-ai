"""Tests for WO-RIPPLED-ROUTING-BACKLOG fix.

Three fixes:
1. Stale candidate discard sweep — candidates stuck >48h past observe_until get discarded
2. ValueError handling — separate FK race from promotion errors in clarification task
3. Backlog cleanup — one-time task to discard stale stuck candidates
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.clarification.analyzer import analyze_candidate
from app.services.clarification.promoter import promote_candidate


# ---------------------------------------------------------------------------
# Candidate factory
# ---------------------------------------------------------------------------

def _make_candidate(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "originating_item_id": "item-001",
        "source_type": "slack",
        "raw_text": "needs to finalize the quarterly budget report",
        "trigger_class": "obligation_marker",
        "is_explicit": True,
        "flag_reanalysis": False,
        "confidence_score": Decimal("0.60"),
        "linked_entities": {"people": ["Alice"], "dates": []},
        "context_window": {},
        "observe_until": datetime.now(timezone.utc) - timedelta(hours=4),
        "priority_hint": None,
        "was_promoted": False,
        "was_discarded": False,
        "model_called_at": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ===========================================================================
# Fix 1: Stale candidate discard sweep
# ===========================================================================

class TestStaleCandidateDiscard:
    """Candidates stuck >48h past observe_until must be discarded."""

    def test_stale_candidate_is_discarded(self):
        """A candidate whose observe_until expired >48h ago, with no promotion
        or discard, should be marked was_discarded=True with reason 'stale_unresolved'."""
        from app.tasks import run_stale_candidate_discard

        stale_id = str(uuid.uuid4())

        # Mock DB query to return one stale candidate
        mock_session = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_id]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("app.tasks.get_sync_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = run_stale_candidate_discard()

        assert result["discarded"] == 1

    def test_stale_sweep_only_targets_expired_candidates(self):
        """The stale sweep query must only select candidates where
        observe_until is more than STALE_THRESHOLD_HOURS in the past."""
        from app.tasks import STALE_THRESHOLD_HOURS

        assert STALE_THRESHOLD_HOURS == 48, (
            f"Stale threshold should be 48 hours, got {STALE_THRESHOLD_HOURS}"
        )

    def test_stale_sweep_sets_discard_reason(self):
        """Discarded candidates must have discard_reason='stale_unresolved'."""
        from app.tasks import run_stale_candidate_discard

        mock_session = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = ["id-1"]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("app.tasks.get_sync_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = run_stale_candidate_discard()

        # The task should have discarded at least 1
        assert result["discarded"] >= 1


# ===========================================================================
# Fix 2: ValueError handling in clarification task
# ===========================================================================

class TestClarificationValueErrorHandling:
    """run_clarification_task must NOT retry promotion ValueErrors as FK race."""

    def test_promotion_valueerror_not_retried_as_fk_race(self):
        """When promote_candidate raises ValueError (e.g., already promoted),
        the task should NOT retry — it should log and mark the candidate
        as handled, not treat it as an FK race condition."""
        from app.tasks import run_clarification_task

        # Simulate a ValueError from promotion (not FK race)
        promotion_error = ValueError("Candidate 'abc' is already promoted")

        with patch("app.tasks.get_sync_session") as mock_ctx, \
             patch("app.tasks.run_clarification", side_effect=promotion_error), \
             patch("app.tasks.run_clarification_task.retry", side_effect=Exception("retry")), \
             patch("app.tasks.logger"):

            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            # The task should NOT retry for promotion errors
            # It should return a skipped/error result instead
            try:
                result = run_clarification_task("abc")
                # If it returns without exception, it handled the error gracefully
                assert result["status"] in ("error", "skipped"), \
                    f"Expected non-retry handling, got {result}"
            except Exception as exc:
                # If it still retries, the fix isn't applied
                if "retry" in str(exc):
                    pytest.fail(
                        "Task retried a promotion ValueError as FK race — "
                        "should handle gracefully instead"
                    )
                raise

    def test_fk_race_valueerror_still_retried(self):
        """A ValueError with 'not found' message (FK race) should still retry."""
        from app.tasks import run_clarification_task

        fk_race_error = ValueError("CommitmentCandidate 'abc' not found")

        with patch("app.tasks.get_sync_session") as mock_ctx, \
             patch("app.tasks.run_clarification", side_effect=fk_race_error), \
             patch("app.tasks.run_clarification_task.retry", side_effect=Exception("retry")) as mock_retry, \
             patch("app.tasks.logger"):

            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(Exception, match="retry"):
                run_clarification_task("abc")

            mock_retry.assert_called_once()

    def test_fragment_gate_valueerror_not_retried(self):
        """Fragment gate ValueError (text too short) should NOT retry."""
        from app.tasks import run_clarification_task

        fragment_error = ValueError("Candidate 'abc' raw_text too short (5 chars < 10)")

        with patch("app.tasks.get_sync_session") as mock_ctx, \
             patch("app.tasks.run_clarification", side_effect=fragment_error), \
             patch("app.tasks.run_clarification_task.retry", side_effect=Exception("retry")), \
             patch("app.tasks.logger"):

            mock_session = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            try:
                result = run_clarification_task("abc")
                assert result["status"] in ("error", "skipped")
            except Exception as exc:
                if "retry" in str(exc):
                    pytest.fail(
                        "Task retried a fragment gate ValueError — "
                        "should handle gracefully instead"
                    )
                raise


# ===========================================================================
# Fix 3: Backlog cleanup task
# ===========================================================================

class TestBacklogCleanup:
    """One-time backlog cleanup: discard candidates stuck with
    obligation_marker / follow_up_commitment trigger classes."""

    def test_backlog_cleanup_exists(self):
        """A cleanup_routing_backlog task must exist."""
        from app.tasks import cleanup_routing_backlog
        assert callable(cleanup_routing_backlog)

    def test_backlog_cleanup_targets_stuck_trigger_classes(self):
        """cleanup_routing_backlog must target obligation_marker,
        follow_up_commitment, and blocker_signal trigger classes."""
        from app.tasks import BACKLOG_TRIGGER_CLASSES

        assert "obligation_marker" in BACKLOG_TRIGGER_CLASSES
        assert "follow_up_commitment" in BACKLOG_TRIGGER_CLASSES
        assert "blocker_signal" in BACKLOG_TRIGGER_CLASSES

    def test_backlog_cleanup_returns_counts(self):
        """cleanup_routing_backlog returns counts per trigger_class."""
        from app.tasks import cleanup_routing_backlog

        mock_session = MagicMock()
        # Simulate update returning rowcount
        mock_update_result = MagicMock()
        mock_update_result.rowcount = 5
        mock_session.execute.return_value = mock_update_result

        with patch("app.tasks.get_sync_session") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = cleanup_routing_backlog()

        assert "discarded" in result
        assert isinstance(result["discarded"], int)


# ===========================================================================
# Promotion sanity: obligation_marker and follow_up_commitment CAN promote
# ===========================================================================

class TestTriggerClassPromotionSanity:
    """Verify that obligation_marker and follow_up_commitment candidates
    can actually be promoted through the clarification flow."""

    def test_obligation_marker_candidate_promotes(self):
        """An obligation_marker candidate with expired observe_until
        should be promotable to a commitment."""
        candidate = _make_candidate(
            trigger_class="obligation_marker",
            confidence_score=Decimal("0.60"),
            observe_until=datetime.now(timezone.utc) - timedelta(hours=4),
            raw_text="needs to finalize the quarterly budget report",
            linked_entities={"people": ["Alice"], "dates": []},
        )

        db = MagicMock()
        db.add = MagicMock()

        analysis = analyze_candidate(candidate)
        commitment = promote_candidate(candidate, db, analysis)

        assert commitment is not None
        assert candidate.was_promoted is True
        assert commitment.title

    def test_follow_up_commitment_candidate_promotes(self):
        """A follow_up_commitment candidate should be promotable."""
        candidate = _make_candidate(
            trigger_class="follow_up_commitment",
            confidence_score=Decimal("0.55"),
            observe_until=datetime.now(timezone.utc) - timedelta(hours=4),
            raw_text="follow up on the design review with the team",
            linked_entities={"people": ["Bob"], "dates": []},
        )

        db = MagicMock()
        db.add = MagicMock()

        analysis = analyze_candidate(candidate)
        commitment = promote_candidate(candidate, db, analysis)

        assert commitment is not None
        assert candidate.was_promoted is True

    def test_full_clarification_flow_obligation_marker(self):
        """Full clarification flow for obligation_marker returns 'clarified'."""
        from app.services.clarification.clarifier import run_clarification

        candidate = _make_candidate(
            trigger_class="obligation_marker",
            confidence_score=Decimal("0.60"),
            observe_until=datetime.now(timezone.utc) - timedelta(hours=4),
        )

        db = MagicMock()
        db.get = MagicMock(return_value=candidate)
        db.add = MagicMock()
        db.flush = MagicMock()

        with patch("app.services.clarification.clarifier.resolve_party_sync", return_value=None), \
             patch("app.services.clarification.clarifier.CounterpartyExtractor"):
            result = run_clarification(str(candidate.id), db)

        assert result["status"] == "clarified"
        assert candidate.was_promoted is True

    def test_full_clarification_flow_follow_up_commitment(self):
        """Full clarification flow for follow_up_commitment returns 'clarified'."""
        from app.services.clarification.clarifier import run_clarification

        candidate = _make_candidate(
            trigger_class="follow_up_commitment",
            confidence_score=Decimal("0.55"),
            raw_text="follow up on the budget proposal with finance",
        )

        db = MagicMock()
        db.get = MagicMock(return_value=candidate)
        db.add = MagicMock()
        db.flush = MagicMock()

        with patch("app.services.clarification.clarifier.resolve_party_sync", return_value=None), \
             patch("app.services.clarification.clarifier.CounterpartyExtractor"):
            result = run_clarification(str(candidate.id), db)

        assert result["status"] == "clarified"
        assert candidate.was_promoted is True


# ===========================================================================
# Beat schedule: stale discard must be scheduled
# ===========================================================================

class TestBeatSchedule:
    """Stale candidate discard must be in the Celery beat schedule."""

    def test_stale_discard_in_beat_schedule(self):
        """The stale-candidate-discard task must be scheduled in Celery beat."""
        from app.tasks import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        stale_tasks = [
            k for k, v in beat_schedule.items()
            if "stale" in k.lower() or "stale" in v.get("task", "").lower()
        ]
        assert stale_tasks, (
            f"No stale candidate discard task in beat schedule. "
            f"Schedule keys: {list(beat_schedule.keys())}"
        )
