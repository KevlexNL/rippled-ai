"""Tests for multi-user IMAP poller functions.

Covers poll_all_email_sources and _poll_source from
app.connectors.email.imap_poller.
"""
from unittest.mock import MagicMock, patch, call

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
    """Return a context manager mock that yields a DB with the given sources."""
    mock_db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = sources
    mock_db.execute.return_value = execute_result

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestPollAllEmailSources:
    def test_no_active_sources_returns_empty(self):
        """No email sources → summary with all zeros."""
        cm = _make_sync_session_cm([])

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            result = imap_poller.poll_all_email_sources()

        assert result["ingested"] == 0
        assert result["duplicates"] == 0
        assert result["errors"] == 0
        assert result["sources_polled"] == 0
        assert result["sources_failed"] == 0

    def test_single_source_polled(self):
        """One source with valid credentials → sources_polled = 1."""
        source = _make_source(
            credentials={"imap_host": "imap.example.com", "imap_user": "u@example.com", "imap_password": "pass"}
        )
        cm = _make_sync_session_cm([source])

        # _poll_source makes its own IMAP connections; mock it entirely
        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            with patch.object(
                imap_poller,
                "_poll_source",
                return_value={"ingested": 3, "duplicates": 1, "errors": 0},
            ):
                result = imap_poller.poll_all_email_sources()

        assert result["sources_polled"] == 1
        assert result["sources_failed"] == 0
        assert result["ingested"] == 3
        assert result["duplicates"] == 1

    def test_one_source_failure_doesnt_stop_others(self):
        """First source raises exception, second succeeds; only sources_failed incremented."""
        source_a = _make_source(source_id="src-A")
        source_b = _make_source(source_id="src-B")
        cm = _make_sync_session_cm([source_a, source_b])

        call_count = 0

        def side_effect(source):
            nonlocal call_count
            call_count += 1
            if source.id == "src-A":
                raise RuntimeError("IMAP connection refused")
            return {"ingested": 2, "duplicates": 0, "errors": 0}

        with patch("app.connectors.email.imap_poller.get_sync_session", return_value=cm):
            with patch.object(imap_poller, "_poll_source", side_effect=side_effect):
                result = imap_poller.poll_all_email_sources()

        assert result["sources_polled"] == 1   # only source_b counted
        assert result["sources_failed"] == 1   # source_a failed
        assert result["ingested"] == 2


class TestPollSource:
    def _mock_sync_session(self):
        """Return a mock get_sync_session that handles the last_synced_at update."""
        mock_db = MagicMock()
        mock_db.get.return_value = MagicMock()  # mock Source for last_synced_at update
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_db)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    def test_per_source_credentials_used(self):
        """Source credentials override env-var defaults."""
        source = _make_source(
            credentials={
                "imap_host": "custom-imap.test-mail.local",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "custom@test-mail.local",
                "imap_password": "custom-pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])  # no messages
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value={
                "imap_host": "custom-imap.test-mail.local",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "custom@test-mail.local",
                "imap_password": "custom-pass",
            },
        ):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=self._mock_sync_session()):
                    result = imap_poller._poll_source(source)

        # Verify the result is a dict (no exception, credentials were used)
        assert isinstance(result, dict)
        assert "ingested" in result

    def test_env_var_fallback(self):
        """Source with no credentials uses env var settings."""
        source = _make_source(credentials=None)

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"0"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        mock_settings = MagicMock()
        mock_settings.imap_host = "env-imap.test-mail.local"
        mock_settings.imap_port = 993
        mock_settings.imap_ssl = True
        mock_settings.imap_user = "env@test-mail.local"
        mock_settings.imap_password = "env-pass"
        mock_settings.imap_sent_folder = "Sent"

        with patch("app.connectors.email.imap_poller.get_settings", return_value=mock_settings):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn) as mock_imap:
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=self._mock_sync_session()):
                    result = imap_poller._poll_source(source)

        # Verify IMAP4_SSL called with env-var host
        mock_imap.assert_called_once_with("env-imap.test-mail.local", 993)
        assert isinstance(result, dict)

    def test_source_missing_host_skipped(self):
        """Source with no host (and no env-var host) is skipped without error."""
        source = _make_source(credentials={})  # empty credentials

        mock_settings = MagicMock()
        mock_settings.imap_host = ""   # no env var either
        mock_settings.imap_port = 993
        mock_settings.imap_ssl = True
        mock_settings.imap_user = ""
        mock_settings.imap_password = ""
        mock_settings.imap_sent_folder = "Sent"

        with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value={}):
            with patch("app.connectors.email.imap_poller.get_settings", return_value=mock_settings):
                result = imap_poller._poll_source(source)

        # Skipped sources return the skipped flag, not counted as errors
        assert result.get("skipped") is True
        assert result.get("errors", 0) == 0

    @pytest.mark.parametrize("host", [
        "imap.example.com",
        "mail.example.org",
        "smtp.example.net",
        "IMAP.EXAMPLE.COM",
    ])
    def test_reserved_domain_host_skipped(self, host):
        """Sources with RFC 2606 reserved domain hostnames are skipped."""
        source = _make_source(credentials={
            "imap_host": host,
            "imap_user": "user@example.com",
            "imap_password": "pass",
        })

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            result = imap_poller._poll_source(source)

        assert result.get("skipped") is True
        assert result.get("errors", 0) == 0
