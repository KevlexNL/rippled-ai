"""Tests for email backfill logic — WO-RIPPLED-EMAIL-BACKFILL.

Covers:
- _build_search_criteria: first-sync vs incremental
- _poll_source: uses SINCE criteria and updates last_synced_at
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from app.connectors.email import imap_poller
from app.connectors.email.imap_poller import _build_search_criteria, BACKFILL_DAYS


class TestBuildSearchCriteria:
    def test_first_sync_uses_30_day_lookback(self):
        """When last_synced_at is None, criteria should be SINCE <30 days ago>."""
        criteria = _build_search_criteria(None)
        expected_date = (datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)).strftime("%d-%b-%Y")
        assert criteria == f"SINCE {expected_date}"

    def test_incremental_sync_uses_last_synced_at(self):
        """When last_synced_at is set, criteria should be SINCE that date."""
        last_synced = datetime(2026, 3, 10, 14, 30, 0, tzinfo=timezone.utc)
        criteria = _build_search_criteria(last_synced)
        assert criteria == "SINCE 10-Mar-2026"

    def test_criteria_format_is_valid_imap(self):
        """Criteria string should start with 'SINCE ' followed by dd-Mon-yyyy."""
        criteria = _build_search_criteria(None)
        assert criteria.startswith("SINCE ")
        date_part = criteria.split(" ", 1)[1]
        # Should parse back to a valid date
        datetime.strptime(date_part, "%d-%b-%Y")


class TestPollSourceBackfill:
    def _make_source(self, last_synced_at=None):
        s = MagicMock()
        s.id = "src-backfill"
        s.user_id = "user-001"
        s.is_active = True
        s.last_synced_at = last_synced_at
        s.credentials = {
            "imap_host": "imap.test-mail.local",
            "imap_port": 993,
            "imap_ssl": True,
            "imap_user": "u@test-mail.local",
            "imap_password": "pass",
        }
        return s

    def _mock_conn(self):
        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        return mock_conn

    def test_first_sync_uses_since_not_unseen(self):
        """First sync (last_synced_at=None) should use SINCE criteria, not UNSEEN."""
        source = self._make_source(last_synced_at=None)
        mock_conn = self._mock_conn()

        mock_db_source = MagicMock()
        mock_db = MagicMock()
        mock_db.get.return_value = mock_db_source

        session_calls = []
        def fake_session():
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=mock_db)
            cm.__exit__ = MagicMock(return_value=False)
            session_calls.append(cm)
            return cm

        with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value=source.credentials):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", side_effect=fake_session):
                    imap_poller._poll_source(source)

        # Verify search was called with SINCE, not UNSEEN
        search_calls = mock_conn.search.call_args_list
        for c in search_calls:
            args = c[0]
            assert "UNSEEN" not in str(args), "First sync should not use UNSEEN"
            assert "SINCE" in str(args[1]), f"Expected SINCE in search criteria, got {args}"

    def test_incremental_sync_uses_last_synced_date(self):
        """Subsequent sync uses SINCE <last_synced_at date>."""
        last_synced = datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone.utc)
        source = self._make_source(last_synced_at=last_synced)
        mock_conn = self._mock_conn()

        mock_db = MagicMock()
        mock_db.get.return_value = MagicMock()

        def fake_session():
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=mock_db)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value=source.credentials):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", side_effect=fake_session):
                    imap_poller._poll_source(source)

        search_calls = mock_conn.search.call_args_list
        for c in search_calls:
            args = c[0]
            assert "SINCE 14-Mar-2026" in str(args[1])

    def test_last_synced_at_updated_after_sync(self):
        """After successful sync, source.last_synced_at should be updated."""
        source = self._make_source(last_synced_at=None)
        mock_conn = self._mock_conn()

        mock_db_source = MagicMock()
        mock_db_source.last_synced_at = None
        mock_db = MagicMock()
        mock_db.get.return_value = mock_db_source

        def fake_session():
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=mock_db)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value=source.credentials):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", side_effect=fake_session):
                    imap_poller._poll_source(source)

        # Verify last_synced_at was set
        assert mock_db_source.last_synced_at is not None
        assert isinstance(mock_db_source.last_synced_at, datetime)

    def test_backfill_cap_is_30_days(self):
        """The backfill lookback should be exactly 30 days."""
        assert BACKFILL_DAYS == 30
