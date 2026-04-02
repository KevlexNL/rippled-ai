"""Tests for run_reanalysis_sweep — C2 re-analysis workflow.

Verifies that flag_reanalysis=true candidates are picked up by a periodic
Celery task, enqueued for model detection, and have their flag cleared.
"""
from __future__ import annotations

import types
from decimal import Decimal
from unittest.mock import MagicMock, patch, call


def _make_candidate(**kwargs):
    """Create a minimal candidate namespace for testing."""
    defaults = {
        "id": "cand-reanalysis-001",
        "flag_reanalysis": True,
        "was_promoted": False,
        "was_discarded": False,
        "confidence_score": Decimal("0.50"),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestReanalysisSweep:
    """Tests for the run_reanalysis_sweep Celery task."""

    @patch("app.tasks.run_model_detection_pass")
    @patch("app.tasks.get_sync_session")
    def test_enqueues_flagged_candidates(self, mock_session_ctx, mock_detect):
        """Candidates with flag_reanalysis=true should be enqueued."""
        from app.tasks import run_reanalysis_sweep

        # Simulate two flagged candidate IDs returned by the query
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            "cand-001",
            "cand-002",
        ]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        result = run_reanalysis_sweep()

        assert result["enqueued"] == 2
        mock_detect.delay.assert_any_call("cand-001")
        mock_detect.delay.assert_any_call("cand-002")

    @patch("app.tasks.run_model_detection_pass")
    @patch("app.tasks.get_sync_session")
    def test_clears_flag_after_enqueue(self, mock_session_ctx, mock_detect):
        """flag_reanalysis should be set to false after processing."""
        from app.tasks import run_reanalysis_sweep

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            "cand-001",
        ]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        result = run_reanalysis_sweep()

        assert result["enqueued"] == 1
        # Verify the update statement was executed (second call to db.execute)
        assert mock_db.execute.call_count >= 2  # SELECT + UPDATE
        mock_db.commit.assert_called_once()

    @patch("app.tasks.run_model_detection_pass")
    @patch("app.tasks.get_sync_session")
    def test_no_flagged_candidates_is_noop(self, mock_session_ctx, mock_detect):
        """When no candidates are flagged, nothing should be enqueued."""
        from app.tasks import run_reanalysis_sweep

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        result = run_reanalysis_sweep()

        assert result["enqueued"] == 0
        mock_detect.delay.assert_not_called()
        # No UPDATE should be issued for empty list
        mock_db.commit.assert_not_called()

    @patch("app.tasks.get_settings")
    def test_disabled_when_model_detection_off(self, mock_settings):
        """Should skip when model_detection_enabled is false."""
        from app.tasks import run_reanalysis_sweep

        mock_settings.return_value.model_detection_enabled = False

        with patch("app.tasks.settings", mock_settings.return_value):
            result = run_reanalysis_sweep()

        assert result["enqueued"] == 0
        assert "model_detection_enabled" in result.get("reason", "")

    @patch("app.tasks.run_model_detection_pass")
    @patch("app.tasks.get_sync_session")
    def test_respects_limit(self, mock_session_ctx, mock_detect):
        """Should respect the limit parameter."""
        from app.tasks import run_reanalysis_sweep

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            "cand-001",
        ]
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        result = run_reanalysis_sweep(limit=10)

        assert result["enqueued"] == 1


class TestReanalysisBeatSchedule:
    """Verify the beat schedule includes the reanalysis sweep."""

    def test_reanalysis_in_beat_schedule(self):
        from app.tasks import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "reanalysis-sweep" in schedule
        assert schedule["reanalysis-sweep"]["task"] == "app.tasks.run_reanalysis_sweep"
