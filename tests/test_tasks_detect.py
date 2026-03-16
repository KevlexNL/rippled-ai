"""Tests for detect_commitments Celery task — WO-RIPPLED-PIPELINE-BUG-001.

Verifies that the task correctly handles the return value from run_detection(),
which returns a list[CommitmentCandidate], not a dict.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


@patch("app.tasks.get_sync_session")
@patch("app.tasks.run_detection")
class TestDetectCommitmentsTask:
    """Test detect_commitments task handles run_detection return types."""

    def test_handles_list_return_from_run_detection(
        self, mock_run_detection, mock_session
    ):
        """BUG REPRO: run_detection returns list, task must not call .get() on it."""
        from app.tasks import detect_commitments

        # run_detection returns a list of candidates (ORM objects)
        candidate1 = MagicMock()
        candidate1.id = "cand-1"
        candidate2 = MagicMock()
        candidate2.id = "cand-2"
        mock_run_detection.return_value = [candidate1, candidate2]

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        result = detect_commitments("item-123")

        assert result["status"] == "complete"
        assert result["source_item_id"] == "item-123"
        assert result["candidates_created"] == 2

    def test_handles_empty_list_return(self, mock_run_detection, mock_session):
        """No candidates detected — should return 0 candidates_created."""
        from app.tasks import detect_commitments

        mock_run_detection.return_value = []

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        result = detect_commitments("item-456")

        assert result["status"] == "complete"
        assert result["candidates_created"] == 0

    def test_logs_result_type_for_debugging(
        self, mock_run_detection, mock_session, caplog
    ):
        """WO acceptance: debugging logs show result type before processing."""
        import logging
        from app.tasks import detect_commitments

        mock_run_detection.return_value = []

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        with caplog.at_level(logging.DEBUG, logger="app.tasks"):
            detect_commitments("item-789")

        assert any("detection complete" in msg for msg in caplog.messages)
