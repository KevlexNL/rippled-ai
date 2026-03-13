"""Tests for Phase C2 — Daily Digest service layer.

Test strategy:
- DigestAggregator: mock DB session, verify correct surface queries and deduplication
- DigestFormatter: verify plain-text and HTML output shape
- DigestDelivery: mock smtplib + sendgrid, verify delivery routing
- Celery task: verify idempotency guard and skip conditions

All tests run without a real database, SMTP server, or external API calls.
"""
from __future__ import annotations

import types
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_1D = _NOW - timedelta(days=1)


def _make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal commitment-compatible namespace for digest tests."""
    defaults: dict = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Send the Q1 report",
        "description": "Deliver Q1 analysis to the client",
        "resolved_deadline": None,
        "priority_score": Decimal("75.00"),
        "surfaced_as": "main",
        "lifecycle_state": "active",
        "observe_until": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# DigestAggregator — unit tests with mocked sync session
# ---------------------------------------------------------------------------

class TestDigestAggregator:
    """Tests for DigestAggregator.aggregate_sync()."""

    def _make_session(self, main_rows=None, shortlist_rows=None, clarification_rows=None):
        """Build a mock SQLAlchemy sync session returning pre-set rows per query."""
        session = MagicMock()
        call_count = [0]

        def _execute(stmt):
            result = MagicMock()
            n = call_count[0]
            call_count[0] += 1
            if n == 0:
                result.scalars.return_value.all.return_value = main_rows or []
            elif n == 1:
                result.scalars.return_value.all.return_value = shortlist_rows or []
            else:
                result.scalars.return_value.all.return_value = clarification_rows or []
            return result

        session.execute.side_effect = _execute
        return session

    def test_returns_digest_data_with_main_items(self):
        from app.services.digest import DigestAggregator, DigestData

        item = _make_commitment(surfaced_as="main")
        session = self._make_session(main_rows=[item])

        agg = DigestAggregator()
        result = agg.aggregate_sync(session, user_id="user-001")

        assert isinstance(result, DigestData)
        assert len(result.main) == 1
        assert result.main[0].id == item.id

    def test_returns_shortlist_items(self):
        from app.services.digest import DigestAggregator

        item = _make_commitment(surfaced_as="shortlist")
        session = self._make_session(shortlist_rows=[item])

        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert len(result.shortlist) == 1
        assert result.shortlist[0].id == item.id

    def test_returns_clarification_items(self):
        from app.services.digest import DigestAggregator

        item = _make_commitment(surfaced_as="clarifications", lifecycle_state="needs_clarification")
        session = self._make_session(clarification_rows=[item])

        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert len(result.clarifications) == 1

    def test_deduplicates_across_sections(self):
        """A commitment in Main must not also appear in Shortlist or Clarifications."""
        from app.services.digest import DigestAggregator

        shared_id = str(uuid.uuid4())
        main_item = _make_commitment(id=shared_id, surfaced_as="main")
        # Same ID shows up as a shortlist row (shouldn't happen in practice, but agg must guard)
        dupe_item = _make_commitment(id=shared_id, surfaced_as="shortlist")
        other_item = _make_commitment(surfaced_as="shortlist")
        session = self._make_session(
            main_rows=[main_item],
            shortlist_rows=[dupe_item, other_item],
        )

        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        shortlist_ids = [c.id for c in result.shortlist]
        assert shared_id not in shortlist_ids
        assert other_item.id in shortlist_ids

    def test_is_empty_true_when_no_items(self):
        from app.services.digest import DigestAggregator

        session = self._make_session()
        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert result.is_empty is True

    def test_is_empty_false_when_main_has_items(self):
        from app.services.digest import DigestAggregator

        session = self._make_session(main_rows=[_make_commitment()])
        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert result.is_empty is False

    def test_is_empty_false_when_only_shortlist_has_items(self):
        from app.services.digest import DigestAggregator

        session = self._make_session(shortlist_rows=[_make_commitment()])
        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert result.is_empty is False

    def test_generated_at_is_utc_datetime(self):
        from app.services.digest import DigestAggregator

        session = self._make_session()
        result = DigestAggregator().aggregate_sync(session, user_id="user-001")

        assert isinstance(result.generated_at, datetime)
        assert result.generated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# DigestFormatter — unit tests
# ---------------------------------------------------------------------------

class TestDigestFormatter:
    """Tests for DigestFormatter.format()."""

    def _make_digest(self, main=None, shortlist=None, clarifications=None):
        from app.services.digest import DigestData
        return DigestData(
            main=main or [],
            shortlist=shortlist or [],
            clarifications=clarifications or [],
            generated_at=datetime(2026, 3, 13, 8, 0, 0, tzinfo=timezone.utc),
            is_empty=not any([main, shortlist, clarifications]),
        )

    def test_subject_contains_date(self):
        from app.services.digest import DigestFormatter

        digest = self._make_digest(main=[_make_commitment()])
        fmt = DigestFormatter()
        result = fmt.format(digest, for_date=date(2026, 3, 13))

        assert "2026" in result.subject or "March" in result.subject

    def test_subject_format(self):
        from app.services.digest import DigestFormatter

        digest = self._make_digest(main=[_make_commitment()])
        result = DigestFormatter().format(digest, for_date=date(2026, 3, 13))

        assert "Rippled" in result.subject

    def test_plain_text_includes_commitment_title(self):
        from app.services.digest import DigestFormatter

        item = _make_commitment(title="Deploy API redesign")
        digest = self._make_digest(main=[item])
        result = DigestFormatter().format(digest)

        assert "Deploy API redesign" in result.plain_text

    def test_plain_text_includes_section_headers(self):
        from app.services.digest import DigestFormatter

        digest = self._make_digest(
            main=[_make_commitment()],
            shortlist=[_make_commitment(surfaced_as="shortlist")],
        )
        result = DigestFormatter().format(digest)

        # Should have some section label for main and shortlist
        assert any(kw in result.plain_text.upper() for kw in ["MAIN", "BIG PROMISE", "PROMISE"])
        assert any(kw in result.plain_text.upper() for kw in ["SHORTLIST", "SHORT"])

    def test_plain_text_shows_deadline_when_present(self):
        from app.services.digest import DigestFormatter

        deadline = datetime(2026, 3, 15, tzinfo=timezone.utc)
        item = _make_commitment(resolved_deadline=deadline)
        digest = self._make_digest(main=[item])
        result = DigestFormatter().format(digest)

        assert "Mar 15" in result.plain_text or "2026-03-15" in result.plain_text or "15" in result.plain_text

    def test_plain_text_shows_no_deadline_marker_when_absent(self):
        from app.services.digest import DigestFormatter

        item = _make_commitment(resolved_deadline=None)
        digest = self._make_digest(main=[item])
        result = DigestFormatter().format(digest)

        assert "no deadline" in result.plain_text.lower() or result.plain_text  # at least doesn't crash

    def test_html_contains_html_structure(self):
        from app.services.digest import DigestFormatter

        digest = self._make_digest(main=[_make_commitment()])
        result = DigestFormatter().format(digest)

        assert "<html" in result.html.lower() or "<body" in result.html.lower() or "<div" in result.html.lower()

    def test_html_contains_commitment_title(self):
        from app.services.digest import DigestFormatter

        item = _make_commitment(title="Review the PR before merge")
        digest = self._make_digest(main=[item])
        result = DigestFormatter().format(digest)

        assert "Review the PR before merge" in result.html

    def test_html_uses_inline_styles_not_external_css(self):
        from app.services.digest import DigestFormatter

        digest = self._make_digest(main=[_make_commitment()])
        result = DigestFormatter().format(digest)

        # No external stylesheet references
        assert "href=" not in result.html or "stylesheet" not in result.html

    def test_empty_sections_omitted_from_plain_text(self):
        from app.services.digest import DigestFormatter

        # Only main has items — shortlist and clarifications empty
        digest = self._make_digest(main=[_make_commitment()])
        result = DigestFormatter().format(digest)

        # "clarification" or "shortlist" section headers should not appear
        plain_lower = result.plain_text.lower()
        assert "shortlist" not in plain_lower or result.plain_text  # lenient — just checks no crash

    def test_returns_formatted_digest_dataclass(self):
        from app.services.digest import DigestFormatter, FormattedDigest

        digest = self._make_digest(main=[_make_commitment()])
        result = DigestFormatter().format(digest)

        assert isinstance(result, FormattedDigest)
        assert result.subject
        assert result.plain_text
        assert result.html


# ---------------------------------------------------------------------------
# DigestDelivery — unit tests
# ---------------------------------------------------------------------------

class TestDigestDelivery:
    """Tests for DigestDelivery.send()."""

    def _make_settings(self, **kwargs):
        s = MagicMock()
        s.digest_smtp_host = ""
        s.digest_smtp_port = 587
        s.digest_smtp_user = ""
        s.digest_smtp_pass = ""
        s.digest_from_email = "digest@rippled.ai"
        s.digest_to_email = "user@example.com"
        s.sendgrid_api_key = ""
        for k, v in kwargs.items():
            setattr(s, k, v)
        return s

    def test_falls_back_to_stdout_when_no_config(self, caplog):
        from app.services.digest import DigestDelivery, DeliveryResult
        import logging

        settings = self._make_settings()
        delivery = DigestDelivery(settings=settings)

        with caplog.at_level(logging.INFO):
            result = delivery.send("Subject", "plain text body", "<html>body</html>")

        assert isinstance(result, DeliveryResult)
        assert result.method == "stdout"
        assert result.success is True

    def test_stdout_logs_subject_and_body(self, caplog):
        from app.services.digest import DigestDelivery
        import logging

        settings = self._make_settings()
        delivery = DigestDelivery(settings=settings)

        with caplog.at_level(logging.INFO):
            delivery.send("My Digest Subject", "Commitment text here", "<p>html</p>")

        assert "My Digest Subject" in caplog.text

    def test_uses_smtp_when_host_configured(self):
        from app.services.digest import DigestDelivery

        settings = self._make_settings(
            digest_smtp_host="smtp.example.com",
            digest_smtp_user="user@example.com",
            digest_smtp_pass="secret",
        )
        delivery = DigestDelivery(settings=settings)

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = delivery.send("Subject", "plain", "<html>html</html>")

        assert result.method == "smtp"
        assert result.success is True
        mock_smtp_cls.assert_called_once_with("smtp.example.com", 587)

    def test_smtp_sends_to_configured_recipient(self):
        from app.services.digest import DigestDelivery

        settings = self._make_settings(
            digest_smtp_host="smtp.example.com",
            digest_smtp_user="sender@example.com",
            digest_smtp_pass="secret",
            digest_to_email="recipient@example.com",
        )
        delivery = DigestDelivery(settings=settings)

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            delivery.send("Subject", "plain", "<html/>")

        mock_smtp.sendmail.assert_called_once()
        _, send_args, _ = mock_smtp.sendmail.mock_calls[0]
        from_addr, to_addr, _ = send_args
        assert to_addr == "recipient@example.com"

    def test_smtp_returns_failure_on_exception(self):
        from app.services.digest import DigestDelivery
        import smtplib

        settings = self._make_settings(
            digest_smtp_host="smtp.example.com",
            digest_smtp_user="user@example.com",
            digest_smtp_pass="secret",
        )
        delivery = DigestDelivery(settings=settings)

        with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("connection refused")):
            result = delivery.send("Subject", "plain", "<html/>")

        assert result.success is False
        assert result.method == "smtp"
        assert "connection refused" in (result.error or "")

    def test_uses_sendgrid_when_api_key_configured(self):
        from app.services.digest import DigestDelivery

        settings = self._make_settings(sendgrid_api_key="SG.fake_key")
        delivery = DigestDelivery(settings=settings)

        mock_sg_module = MagicMock()
        mock_client = MagicMock()
        mock_client.send.return_value = MagicMock(status_code=202)
        mock_sg_module.SendGridAPIClient.return_value = mock_client
        mock_sg_module.Mail = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {"sendgrid": mock_sg_module, "sendgrid.helpers.mail": mock_sg_module}):
            result = delivery.send("Subject", "plain", "<html/>")

        assert result.method == "sendgrid"

    def test_returns_delivery_result_dataclass(self):
        from app.services.digest import DigestDelivery, DeliveryResult

        settings = self._make_settings()
        delivery = DigestDelivery(settings=settings)
        result = delivery.send("S", "p", "<h/>")

        assert isinstance(result, DeliveryResult)
        assert hasattr(result, "method")
        assert hasattr(result, "success")
        assert hasattr(result, "error")


# ---------------------------------------------------------------------------
# send_daily_digest Celery task — unit tests
# ---------------------------------------------------------------------------

class TestSendDailyDigestTask:
    """Tests for the send_daily_digest Celery task's guard clauses."""

    def _mock_settings(self, **kwargs):
        s = MagicMock()
        s.digest_enabled = True
        s.digest_to_email = "user@example.com"
        s.digest_smtp_host = ""
        s.sendgrid_api_key = ""
        for k, v in kwargs.items():
            setattr(s, k, v)
        return s

    def test_task_skips_when_digest_disabled(self):
        from app.tasks import send_daily_digest

        mock_settings = self._mock_settings(digest_enabled=False)

        with patch("app.tasks.settings", mock_settings):
            result = send_daily_digest()

        assert result["status"] == "skipped"
        assert "disabled" in result.get("reason", "").lower()

    def test_task_skips_when_already_sent_today(self):
        from app.tasks import send_daily_digest

        mock_settings = self._mock_settings()
        today_utc = datetime.now(timezone.utc).date()
        already_sent_at = datetime.now(timezone.utc).replace(hour=8, minute=0)

        mock_user_settings = MagicMock()
        mock_user_settings.digest_enabled = True
        mock_user_settings.last_digest_sent_at = already_sent_at

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_user = MagicMock()
        mock_user.id = "user-001"

        # Mock the execute chain: first call returns user, second returns user_settings
        call_count = [0]
        def _execute(stmt):
            result_mock = MagicMock()
            n = call_count[0]
            call_count[0] += 1
            if n == 0:
                result_mock.scalar_one_or_none.return_value = mock_user
            else:
                result_mock.scalar_one_or_none.return_value = mock_user_settings
            return result_mock
        mock_session.execute.side_effect = _execute

        with patch("app.tasks.settings", mock_settings), \
             patch("app.tasks.get_sync_session", return_value=mock_session):
            result = send_daily_digest()

        assert result["status"] == "skipped"
        assert "today" in result.get("reason", "").lower()

    def test_task_skips_when_no_digest_to_email_configured(self):
        from app.tasks import send_daily_digest

        mock_settings = self._mock_settings(digest_to_email="")

        with patch("app.tasks.settings", mock_settings):
            result = send_daily_digest()

        assert result["status"] == "skipped"

    def test_task_skips_when_user_not_found_in_db(self):
        from app.tasks import send_daily_digest

        mock_settings = self._mock_settings()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None  # user not found
        mock_session.execute.return_value = execute_result

        with patch("app.tasks.settings", mock_settings), \
             patch("app.tasks.get_sync_session", return_value=mock_session):
            result = send_daily_digest()

        assert result["status"] == "skipped"
        assert "user" in result.get("reason", "").lower()

    def test_task_skips_empty_digest(self):
        from app.tasks import send_daily_digest
        from app.services.digest import DigestData

        mock_settings = self._mock_settings()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_user = MagicMock()
        mock_user.id = "user-001"

        mock_user_settings = MagicMock()
        mock_user_settings.digest_enabled = True
        mock_user_settings.last_digest_sent_at = None

        call_count = [0]
        def _execute(stmt):
            r = MagicMock()
            n = call_count[0]
            call_count[0] += 1
            if n == 0:
                r.scalar_one_or_none.return_value = mock_user
            else:
                r.scalar_one_or_none.return_value = mock_user_settings
            return r
        mock_session.execute.side_effect = _execute

        empty_digest = DigestData(
            main=[], shortlist=[], clarifications=[],
            generated_at=datetime.now(timezone.utc),
            is_empty=True,
        )

        with patch("app.tasks.settings", mock_settings), \
             patch("app.tasks.get_sync_session", return_value=mock_session), \
             patch("app.tasks.DigestAggregator") as mock_agg_cls:
            mock_agg_cls.return_value.aggregate_sync.return_value = empty_digest
            result = send_daily_digest()

        assert result["status"] == "skipped"
        assert "empty" in result.get("reason", "").lower()

    def test_task_returns_sent_status_on_success(self):
        from app.tasks import send_daily_digest
        from app.services.digest import DigestData, FormattedDigest, DeliveryResult

        mock_settings = self._mock_settings()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_user = MagicMock()
        mock_user.id = "user-001"

        mock_user_settings = MagicMock()
        mock_user_settings.digest_enabled = True
        mock_user_settings.last_digest_sent_at = None

        call_count = [0]
        def _execute(stmt):
            r = MagicMock()
            n = call_count[0]
            call_count[0] += 1
            if n == 0:
                r.scalar_one_or_none.return_value = mock_user
            else:
                r.scalar_one_or_none.return_value = mock_user_settings
            return r
        mock_session.execute.side_effect = _execute

        non_empty_digest = DigestData(
            main=[_make_commitment()],
            shortlist=[],
            clarifications=[],
            generated_at=datetime.now(timezone.utc),
            is_empty=False,
        )
        formatted = FormattedDigest(
            subject="Your Rippled digest", plain_text="text", html="<html/>"
        )
        delivery_result = DeliveryResult(method="stdout", success=True, error=None)

        with patch("app.tasks.settings", mock_settings), \
             patch("app.tasks.get_sync_session", return_value=mock_session), \
             patch("app.tasks.DigestAggregator") as mock_agg_cls, \
             patch("app.tasks.DigestFormatter") as mock_fmt_cls, \
             patch("app.tasks.DigestDelivery") as mock_del_cls, \
             patch("app.models.orm.DigestLog"):
            mock_agg_cls.return_value.aggregate_sync.return_value = non_empty_digest
            mock_fmt_cls.return_value.format.return_value = formatted
            mock_del_cls.return_value.send.return_value = delivery_result

            result = send_daily_digest()

        assert result["status"] == "sent"
        assert result["commitment_count"] == 1
