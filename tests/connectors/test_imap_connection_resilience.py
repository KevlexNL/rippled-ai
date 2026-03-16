"""Tests for IMAP connection resilience: hostname sanitization, DNS retry, logging.

Covers the fixes for WO-RIPPLED-EMAIL-HOST-FIX-002:
- Hostname whitespace stripping
- Retry on transient DNS/socket errors
- Diagnostic logging of hostname attempted
"""
import socket
from unittest.mock import MagicMock, patch

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


def _mock_sync_session():
    mock_db = MagicMock()
    mock_db.get.return_value = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestHostnameSanitization:
    """Hostname values are stripped and validated before IMAP connection."""

    def test_whitespace_stripped_from_hostname(self):
        """Leading/trailing whitespace in imap_host is stripped."""
        source = _make_source(
            credentials={
                "imap_host": "  imap.gmail.com  ",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn) as mock_imap:
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=_mock_sync_session()):
                    imap_poller._poll_source(source)

        # Should connect with stripped hostname, not the whitespace version
        mock_imap.assert_called_once_with("imap.gmail.com", 993)

    def test_whitespace_only_hostname_treated_as_empty(self):
        """A hostname that is only whitespace should be treated as missing."""
        source = _make_source(
            credentials={
                "imap_host": "   ",
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        mock_settings = MagicMock()
        mock_settings.imap_host = ""
        mock_settings.imap_port = 993
        mock_settings.imap_ssl = True
        mock_settings.imap_user = ""
        mock_settings.imap_password = ""
        mock_settings.imap_sent_folder = "Sent"

        with patch("app.connectors.email.imap_poller.decrypt_credentials", return_value=source.credentials):
            with patch("app.connectors.email.imap_poller.get_settings", return_value=mock_settings):
                result = imap_poller._poll_source(source)

        assert result.get("skipped") is True

    def test_whitespace_stripped_from_username(self):
        """Leading/trailing whitespace in imap_user is stripped."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "  test@gmail.com  ",
                "imap_password": "pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=_mock_sync_session()):
                    imap_poller._poll_source(source)

        # login should use stripped username
        mock_conn.login.assert_called_once_with("test@gmail.com", "pass")


class TestDnsRetry:
    """Transient DNS failures are retried before giving up."""

    def test_retries_on_transient_dns_error(self):
        """IMAP connection retried on socket.gaierror, succeeds on retry."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        # First call raises DNS error, second succeeds
        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch(
                "app.connectors.email.imap_poller.imaplib.IMAP4_SSL",
                side_effect=[
                    socket.gaierror(-5, "No address associated with hostname"),
                    mock_conn,
                ],
            ) as mock_imap:
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=_mock_sync_session()):
                    with patch("app.connectors.email.imap_poller.time.sleep"):  # don't actually sleep
                        result = imap_poller._poll_source(source)

        # Should have been called twice (initial + 1 retry)
        assert mock_imap.call_count == 2
        assert "ingested" in result  # success, not an exception

    def test_gives_up_after_max_retries(self):
        """After exhausting retries, the DNS error propagates."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        dns_error = socket.gaierror(-5, "No address associated with hostname")

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch(
                "app.connectors.email.imap_poller.imaplib.IMAP4_SSL",
                side_effect=dns_error,
            ) as mock_imap:
                with patch("app.connectors.email.imap_poller.time.sleep"):
                    with pytest.raises(socket.gaierror):
                        imap_poller._poll_source(source)

        # Should have attempted 3 times total (1 initial + 2 retries)
        assert mock_imap.call_count == 3

    def test_no_retry_on_auth_error(self):
        """IMAP auth errors are NOT retried — only DNS/connection errors."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "wrong-pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.login.side_effect = Exception("AUTHENTICATIONFAILED")

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch(
                "app.connectors.email.imap_poller.imaplib.IMAP4_SSL",
                return_value=mock_conn,
            ) as mock_imap:
                with patch("app.connectors.email.imap_poller.time.sleep"):
                    with pytest.raises(Exception, match="AUTHENTICATIONFAILED"):
                        imap_poller._poll_source(source)

        # IMAP4_SSL called only once — no retry for auth errors
        assert mock_imap.call_count == 1

    def test_retries_on_connection_refused(self):
        """ConnectionRefusedError is also retried (transient network issue)."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch(
                "app.connectors.email.imap_poller.imaplib.IMAP4_SSL",
                side_effect=[
                    ConnectionRefusedError("Connection refused"),
                    mock_conn,
                ],
            ) as mock_imap:
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=_mock_sync_session()):
                    with patch("app.connectors.email.imap_poller.time.sleep"):
                        result = imap_poller._poll_source(source)

        assert mock_imap.call_count == 2
        assert "ingested" in result


class TestDiagnosticLogging:
    """Connection attempts log the hostname for debugging."""

    def test_logs_hostname_on_connection_attempt(self):
        """The hostname being connected to is logged at info level."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.login.return_value = ("OK", [b"Logged in"])

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", return_value=mock_conn):
                with patch("app.connectors.email.imap_poller.get_sync_session", return_value=_mock_sync_session()):
                    with patch.object(imap_poller.logger, "info") as mock_log:
                        imap_poller._poll_source(source)

        # At least one info log should mention the hostname
        log_messages = [str(c) for c in mock_log.call_args_list]
        assert any("imap.gmail.com" in msg for msg in log_messages)

    def test_logs_hostname_on_dns_failure(self):
        """DNS failure logs the hostname that failed to resolve."""
        source = _make_source(
            credentials={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_ssl": True,
                "imap_user": "test@gmail.com",
                "imap_password": "pass",
            }
        )

        dns_error = socket.gaierror(-5, "No address associated with hostname")

        with patch(
            "app.connectors.email.imap_poller.decrypt_credentials",
            return_value=source.credentials,
        ):
            with patch("app.connectors.email.imap_poller.imaplib.IMAP4_SSL", side_effect=dns_error):
                with patch("app.connectors.email.imap_poller.time.sleep"):
                    with patch.object(imap_poller.logger, "warning") as mock_warn:
                        with pytest.raises(socket.gaierror):
                            imap_poller._poll_source(source)

        # Warning logs should mention the hostname
        warn_messages = [str(c) for c in mock_warn.call_args_list]
        assert any("imap.gmail.com" in msg for msg in warn_messages)
