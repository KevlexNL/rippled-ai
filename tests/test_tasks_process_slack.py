"""Tests for process_slack_event Celery task — signal persistence path.

Verifies that the task:
1. Persists RawSignalIngest + NormalizedSignalModel via NormalizationRepository
2. Deduplicates by payload hash
3. Logs errors before retrying (lesson 2026-03-25)
"""
from unittest.mock import MagicMock, patch

import pytest


def _make_payload(**event_overrides) -> dict:
    event = {
        "type": "message",
        "ts": "1704067200.000001",
        "user": "U12345",
        "text": "I'll send the report by Friday.",
        "channel": "C12345",
        "team": "T12345",
    }
    event.update(event_overrides)
    return {
        "token": "test-token",
        "team_id": "T12345",
        "type": "event_callback",
        "event": event,
    }


class _FakeSource:
    def __init__(self, source_id="src-001", user_id="user-001"):
        self.id = source_id
        self.user_id = user_id
        self.source_type = "slack"
        self.provider_account_id = "T12345"
        self.is_active = True
        self.credentials = None  # will be overridden by mock


class TestProcessSlackEventPersistence:
    """Test that process_slack_event persists RawSignalIngest + NormalizedSignal."""

    @patch("app.tasks.get_sync_session")
    @patch("app.connectors.shared.ingestor.ingest_item")
    @patch("app.connectors.shared.ingestor.get_or_create_source_sync")
    def test_persists_raw_ingest_and_normalized_signal(
        self, mock_get_or_create, mock_ingest, mock_session_ctx
    ):
        """Valid message event → RawSignalIngest + NormalizedSignal persisted."""
        from app.tasks import process_slack_event

        source = _FakeSource()
        mock_get_or_create.return_value = source

        # Mock ingest_item to return (item, True) indicating new item
        mock_source_item = MagicMock()
        mock_source_item.id = "si-001"
        mock_ingest.return_value = (mock_source_item, True)

        # Mock the DB session context manager
        mock_db = MagicMock()
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # Mock Source lookup to return None (fallback path)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Mock NormalizationRepository
        mock_repo = MagicMock()
        mock_repo.find_raw_ingest_by_hash.return_value = None
        mock_raw_ingest = MagicMock()
        mock_raw_ingest.id = "ri-001"
        mock_repo.save_raw_ingest.return_value = mock_raw_ingest

        with patch("app.tasks.settings") as mock_settings:
            mock_settings.slack_team_id = "T12345"
            mock_settings.slack_user_id = "user-001"
            with patch(
                "app.services.normalization.normalization_repository.NormalizationRepository",
                return_value=mock_repo,
            ):
                result = process_slack_event(_make_payload())

        assert result["status"] == "ingested"
        mock_repo.save_raw_ingest.assert_called_once()
        mock_repo.save_normalized_signal.assert_called_once()

        # Verify the raw ingest was created with correct fields
        raw_create = mock_repo.save_raw_ingest.call_args[0][0]
        assert raw_create.provider == "slack"
        assert raw_create.provider_message_id == "1704067200.000001"
        assert str(raw_create.source_type) == "slack" or raw_create.source_type == "slack"

    @patch("app.tasks.get_sync_session")
    @patch("app.connectors.shared.ingestor.ingest_item")
    @patch("app.connectors.shared.ingestor.get_or_create_source_sync")
    def test_duplicate_payload_skips_signal_persistence(
        self, mock_get_or_create, mock_ingest, mock_session_ctx
    ):
        """Duplicate SourceItem (created=False) → no signal persistence."""
        from app.tasks import process_slack_event

        source = _FakeSource()
        mock_get_or_create.return_value = source
        mock_ingest.return_value = (None, False)  # duplicate

        mock_db = MagicMock()
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        mock_repo = MagicMock()

        with patch("app.tasks.settings") as mock_settings:
            mock_settings.slack_team_id = "T12345"
            mock_settings.slack_user_id = "user-001"
            with patch(
                "app.services.normalization.normalization_repository.NormalizationRepository",
                return_value=mock_repo,
            ):
                result = process_slack_event(_make_payload())

        assert result["status"] == "duplicate"
        mock_repo.save_raw_ingest.assert_not_called()
        mock_repo.save_normalized_signal.assert_not_called()

    @patch("app.tasks.get_sync_session")
    @patch("app.connectors.shared.ingestor.ingest_item")
    @patch("app.connectors.shared.ingestor.get_or_create_source_sync")
    def test_filtered_event_returns_filtered(
        self, mock_get_or_create, mock_ingest, mock_session_ctx
    ):
        """Bot message → filtered, no persistence."""
        from app.tasks import process_slack_event

        source = _FakeSource()
        mock_get_or_create.return_value = source

        mock_db = MagicMock()
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.tasks.settings") as mock_settings:
            mock_settings.slack_team_id = "T12345"
            mock_settings.slack_user_id = "user-001"
            result = process_slack_event(_make_payload(bot_id="B999"))

        assert result["status"] == "filtered"
        mock_ingest.assert_not_called()

    def test_error_logging_before_retry(self):
        """Exceptions are logged at ERROR before retry (lesson 2026-03-25)."""
        from app.tasks import process_slack_event

        task = process_slack_event
        # Bind a fake request to the task
        task.request.retries = 0

        with patch("app.tasks.get_sync_session") as mock_session_ctx:
            mock_session_ctx.return_value.__enter__ = MagicMock(
                side_effect=RuntimeError("db connection failed")
            )
            mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

            with patch("app.tasks.settings") as mock_settings:
                mock_settings.slack_team_id = "T12345"
                with patch("app.tasks.logger") as mock_logger:
                    with pytest.raises(Exception):
                        process_slack_event(_make_payload())

                    mock_logger.error.assert_called_once()
                    call_args = mock_logger.error.call_args
                    assert "process_slack_event failed" in call_args[0][0]
