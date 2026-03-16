"""Tests for run_clarification_task FK race condition retry — WO-RIPPLED-PIPELINE-RACE-FIX.

Verifies that:
1. ValueError (candidate not found) triggers a Celery retry with 5s delay
2. Other exceptions still use the default retry delay (30s)
3. Normal operation (no error) returns the clarification result
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@patch("app.tasks.get_sync_session")
@patch("app.tasks.run_clarification")
class TestClarificationTaskRetry:
    """Test run_clarification_task handles FK race condition."""

    def test_retries_with_short_delay_on_value_error(
        self, mock_run_clarification, mock_session
    ):
        """FK race: candidate not found yet should retry after 5s, not 30s."""
        from app.tasks import run_clarification_task

        mock_run_clarification.side_effect = ValueError(
            "CommitmentCandidate 'abc-123' not found"
        )

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        # Patch retry on the bound task object
        mock_retry = MagicMock(side_effect=Exception("retry-called"))
        with patch.object(run_clarification_task, "retry", mock_retry):
            with pytest.raises(Exception, match="retry-called"):
                run_clarification_task("abc-123")

        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        assert call_kwargs["countdown"] == 5
        assert isinstance(call_kwargs["exc"], ValueError)

    def test_retries_with_default_delay_on_other_errors(
        self, mock_run_clarification, mock_session
    ):
        """Non-FK errors should use default retry (no countdown override)."""
        from app.tasks import run_clarification_task

        mock_run_clarification.side_effect = RuntimeError("DB connection lost")

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_retry = MagicMock(side_effect=Exception("retry-called"))
        with patch.object(run_clarification_task, "retry", mock_retry):
            with pytest.raises(Exception, match="retry-called"):
                run_clarification_task("abc-123")

        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        # Should NOT have a countdown override — uses default_retry_delay
        assert "countdown" not in call_kwargs

    def test_returns_result_on_success(
        self, mock_run_clarification, mock_session
    ):
        """Happy path: returns clarification result without retrying."""
        from app.tasks import run_clarification_task

        mock_run_clarification.return_value = {
            "status": "clarified",
            "commitment_id": "commit-1",
        }

        mock_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        result = run_clarification_task("cand-1")

        assert result["status"] == "clarified"
        assert result["commitment_id"] == "commit-1"
