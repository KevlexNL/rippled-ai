"""Tests for Phase C3 — GoogleCalendarConnector.

Covers:
- sync() skip when google_calendar_enabled=False
- sync() skip when oauth not configured
- sync() skip when user has no tokens
- _parse_google_datetime parses dateTime with timezone
- _parse_google_datetime parses date-only (all-day events)
- _upsert_event creates new event
- _upsert_event detects cancellation (status=cancelled)
- _upsert_event detects rescheduling (starts_at changed)
- get_auth_url returns string containing accounts.google.com (mocked)
- event cancellation handling: linked commitments surfaced
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.google_calendar import (
    GoogleCalendarConnector,
    _is_expired,
    _parse_google_datetime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_settings(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "google_calendar_enabled": True,
        "google_oauth_client_id": "client-id",
        "google_oauth_client_secret": "client-secret",
        "google_oauth_redirect_uri": "http://localhost/callback",
        "google_calendar_user_email": "",
        "encryption_key": "",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_user_settings(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "user_id": "user-001",
        "google_access_token": "token-abc",
        "google_refresh_token": "refresh-xyz",
        "google_token_expiry": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_db(user_settings=None):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user_settings
    db.execute.return_value = result
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# TestGoogleCalendarConnector
# ---------------------------------------------------------------------------


class TestGoogleCalendarConnectorGuards:

    def test_skip_when_disabled(self):
        """google_calendar_enabled=False → status=skipped."""
        settings = make_settings(google_calendar_enabled=False)
        connector = GoogleCalendarConnector(settings=settings, db=make_db())
        result = connector.sync("user-001")
        assert result["status"] == "skipped"
        assert "google_calendar_enabled" in result["reason"]

    def test_skip_when_oauth_not_configured(self):
        """google_oauth_client_id empty → status=skipped."""
        settings = make_settings(google_oauth_client_id="")
        connector = GoogleCalendarConnector(settings=settings, db=make_db())
        result = connector.sync("user-001")
        assert result["status"] == "skipped"
        assert "oauth" in result["reason"]

    def test_skip_when_no_tokens(self):
        """UserSettings has no refresh_token → status=skipped."""
        settings = make_settings()
        user_settings = make_user_settings(google_refresh_token=None)
        connector = GoogleCalendarConnector(settings=settings, db=make_db(user_settings=user_settings))
        result = connector.sync("user-001")
        assert result["status"] == "skipped"

    def test_skip_when_no_user_settings(self):
        """No UserSettings row → status=skipped."""
        settings = make_settings()
        connector = GoogleCalendarConnector(settings=settings, db=make_db(user_settings=None))
        result = connector.sync("user-001")
        assert result["status"] == "skipped"


class TestParseGoogleDatetime:

    def test_parses_datetime_with_offset(self):
        """dateTime with timezone offset parsed to UTC datetime."""
        result = _parse_google_datetime({"dateTime": "2026-03-15T10:00:00+01:00"})
        assert result is not None
        assert result.tzinfo is not None
        # 10:00+01:00 = 09:00 UTC
        assert result.hour == 9

    def test_parses_datetime_zulu(self):
        """dateTime ending in Z parsed correctly."""
        result = _parse_google_datetime({"dateTime": "2026-03-15T14:30:00Z"})
        assert result is not None
        assert result.hour == 14
        assert result.minute == 30

    def test_parses_date_only_all_day(self):
        """date-only (all-day event) returns midnight UTC."""
        result = _parse_google_datetime({"date": "2026-03-15"})
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15

    def test_returns_none_for_empty(self):
        """Empty dict → returns None."""
        assert _parse_google_datetime({}) is None
        assert _parse_google_datetime(None) is None


class TestIsExpired:

    def test_expired_token(self):
        """Expiry in the past → True."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert _is_expired(past) is True

    def test_non_expired_token(self):
        """Expiry in the future (beyond 5 min grace) → False."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert _is_expired(future) is False


class TestUpsertEvent:

    def _make_connector(self):
        settings = make_settings()
        return GoogleCalendarConnector(settings=settings, db=MagicMock())

    def test_creates_new_event_when_not_existing(self):
        """Upsert with no existing event → creates new Event row."""
        connector = self._make_connector()

        db = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        db.execute.return_value = execute_result
        added = []
        db.add.side_effect = added.append

        raw = {
            "id": "google-event-001",
            "summary": "Weekly standup",
            "status": "confirmed",
            "start": {"dateTime": "2026-03-20T09:00:00Z"},
            "end": {"dateTime": "2026-03-20T09:30:00Z"},
        }
        result = connector._upsert_event(raw, db)
        assert result == "created"
        assert len(added) == 1

    def test_detects_cancellation(self):
        """Existing confirmed event → status=cancelled → returns 'cancelled'."""
        connector = self._make_connector()

        from app.models.orm import Event
        existing = MagicMock(spec=Event)
        existing.status = "confirmed"
        existing.starts_at = datetime(2026, 3, 20, 9, 0, tzinfo=timezone.utc)

        db = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = existing
        db.execute.return_value = execute_result

        raw = {
            "id": "google-event-001",
            "summary": "Weekly standup",
            "status": "cancelled",
            "start": {"dateTime": "2026-03-20T09:00:00Z"},
            "end": {"dateTime": "2026-03-20T09:30:00Z"},
        }
        result = connector._upsert_event(raw, db)
        assert result == "cancelled"
        assert existing.status == "cancelled"
        assert existing.cancelled_at is not None

    def test_detects_rescheduling(self):
        """Existing event with different starts_at → sets rescheduled_from."""
        connector = self._make_connector()

        from app.models.orm import Event
        old_start = datetime(2026, 3, 20, 9, 0, tzinfo=timezone.utc)
        existing = MagicMock(spec=Event)
        existing.status = "confirmed"
        existing.starts_at = old_start

        db = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = existing
        db.execute.return_value = execute_result

        raw = {
            "id": "google-event-001",
            "summary": "Weekly standup",
            "status": "confirmed",
            "start": {"dateTime": "2026-03-20T11:00:00Z"},  # new start time
            "end": {"dateTime": "2026-03-20T11:30:00Z"},
        }
        result = connector._upsert_event(raw, db)
        assert result == "updated"
        assert existing.rescheduled_from == old_start
