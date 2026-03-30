"""Tests for email source error isolation.

Verifies that a bad source (e.g. connection failure) is isolated and
does not crash the entire ingestion worker. Other sources continue.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.connectors.email import imap_poller


def _make_source(
    source_id: str = "src-001",
    user_id: str = "user-001",
    credentials: dict | None = None,
    is_active: bool = True,
    last_synced_at=None,
):
    s = MagicMock()
    s.id = source_id
    s.user_id = user_id
    s.is_active = is_active
    s.credentials = credentials
    s.last_synced_at = last_synced_at
    return s


def _make_sync_session_cm(sources: list):
    mock_db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = sources
    mock_db.execute.return_value = execute_result

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestErrorIsolation:
    def test_bad_source_does_not_crash_worker(self):
        """First source raises, second succeeds — worker continues."""
        source_bad = _make_source(source_id="src-BAD", credentials={"imap_host": "bad.host.invalid"})
        source_good = _make_source(source_id="src-GOOD")
        cm = _make_sync_session_cm([source_bad, source_good])

        call_count = {"n": 0}

        def _mock_poll(source):
            call_count["n"] += 1
            if source.id == "src-BAD":
                raise ConnectionRefusedError("Connection refused")
            return {"ingested": 2, "duplicates": 0, "errors": 0}

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            with patch.object(imap_poller, "_poll_source", side_effect=_mock_poll):
                with patch.object(imap_poller, "_record_source_error") as mock_record:
                    result = imap_poller.poll_all_email_sources()

        # Both sources were attempted
        assert call_count["n"] == 2
        # Good source counted
        assert result["sources_polled"] == 1
        assert result["ingested"] == 2
        # Bad source counted as failed, not crashed
        assert result["sources_failed"] == 1
        # Error was recorded
        mock_record.assert_called_once_with("src-BAD", "Connection refused")

    def test_all_sources_fail_returns_summary(self):
        """All sources fail — worker returns summary, doesn't raise."""
        source_a = _make_source(source_id="src-A")
        source_b = _make_source(source_id="src-B")
        cm = _make_sync_session_cm([source_a, source_b])

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            with patch.object(imap_poller, "_poll_source", side_effect=OSError("Network unreachable")):
                with patch.object(imap_poller, "_record_source_error"):
                    result = imap_poller.poll_all_email_sources()

        assert result["sources_polled"] == 0
        assert result["sources_failed"] == 2
        assert result["ingested"] == 0


class TestRecordSourceError:
    def test_records_error_on_source(self):
        """_record_source_error writes last_error and last_error_at to the source row."""
        mock_source = MagicMock()
        mock_db = MagicMock()
        mock_db.get.return_value = mock_source

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_db)
        cm.__exit__ = MagicMock(return_value=False)

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            imap_poller._record_source_error("src-001", "Connection refused")

        assert mock_source.last_error == "Connection refused"
        assert mock_source.last_error_at is not None

    def test_truncates_long_errors(self):
        """Error messages longer than 2000 chars are truncated."""
        mock_source = MagicMock()
        mock_db = MagicMock()
        mock_db.get.return_value = mock_source

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_db)
        cm.__exit__ = MagicMock(return_value=False)

        long_error = "x" * 5000
        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            imap_poller._record_source_error("src-001", long_error)

        assert len(mock_source.last_error) == 2000

    def test_does_not_raise_on_db_failure(self):
        """If recording the error itself fails, it should not propagate."""
        cm = MagicMock()
        cm.__enter__ = MagicMock(side_effect=RuntimeError("DB down"))
        cm.__exit__ = MagicMock(return_value=False)

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            # Should not raise
            imap_poller._record_source_error("src-001", "original error")


class TestSuccessfulSyncClearsError:
    def test_successful_poll_clears_last_error(self):
        """After successful sync, last_error and last_error_at are cleared."""
        source = _make_source(
            credentials={"imap_host": "imap.gmail.com", "imap_user": "u@gmail.com", "imap_password": "pass"}
        )

        mock_db_source = MagicMock()
        mock_db_source.last_error = "previous error"
        mock_db_source.last_error_at = "2026-01-01"

        mock_db = MagicMock()
        mock_db.get.return_value = mock_db_source

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_db)
        cm.__exit__ = MagicMock(return_value=False)

        # Mock IMAP connection to succeed with no messages
        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = (None, [b""])

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value=source.credentials):
                with patch("app.connectors.email.imap_poller.get_settings") as mock_settings:
                    mock_settings.return_value.imap_host = ""
                    mock_settings.return_value.imap_port = 993
                    mock_settings.return_value.imap_ssl = True
                    mock_settings.return_value.imap_user = ""
                    mock_settings.return_value.imap_password = ""
                    mock_settings.return_value.imap_sent_folder = "Sent"
                    with patch("imaplib.IMAP4_SSL", return_value=mock_conn):
                        result = imap_poller._poll_source(source)

        assert mock_db_source.last_error is None
        assert mock_db_source.last_error_at is None
