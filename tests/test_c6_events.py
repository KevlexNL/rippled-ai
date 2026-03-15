"""Tests for Phase C6 — Events user_id scoping.

TDD: Tests written before implementation.
Covers:
- GET /api/v1/events only returns events for current user (user_id filter)
- GET /api/v1/events returns empty list when user has no events
- GoogleCalendarConnector._upsert_event sets user_id on created Event row
- GoogleCalendarConnector.sync passes user_id into _upsert_event
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
OTHER_USER_ID = "other-user-" + str(uuid.uuid4())[:8]
USER_HEADERS = {"x-user-id": USER_ID}
NOW = datetime.now(timezone.utc)


def _make_event(user_id: str = USER_ID, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "external_id": None,
        "title": "Team standup",
        "description": None,
        "starts_at": NOW + timedelta(hours=2),
        "ends_at": NOW + timedelta(hours=3),
        "event_type": "explicit",
        "status": "confirmed",
        "is_recurring": False,
        "recurrence_rule": None,
        "location": None,
        "attendees": None,
        "rescheduled_from": None,
        "cancelled_at": None,
        "source_id": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestEventsUserIdFilter:
    def test_list_events_returns_only_current_user_events(self):
        """GET /api/v1/events only returns events belonging to current user."""
        my_event = _make_event(user_id=USER_ID, title="My meeting")

        async def fake_get_db():
            db = AsyncMock()
            # events query
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[my_event])))
            # commitment event links count query
            result2 = MagicMock()
            result2.all = MagicMock(return_value=[])
            db.execute = AsyncMock(side_effect=[result1, result2])
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/events", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "My meeting"

    def test_list_events_empty_when_no_events(self):
        """GET /api/v1/events returns empty list when user has no events."""

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            result2 = MagicMock()
            result2.all = MagicMock(return_value=[])
            db.execute = AsyncMock(side_effect=[result1, result2])
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/events", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json() == []


class TestGoogleCalendarConnectorUserIdPropagation:
    def test_upsert_event_sets_user_id_on_new_event(self):
        """_upsert_event sets user_id on newly created Event rows."""
        from app.connectors.google_calendar import GoogleCalendarConnector

        connector = GoogleCalendarConnector(settings=MagicMock(), db=MagicMock())

        raw = {
            "id": "abc123",
            "status": "confirmed",
            "summary": "Planning meeting",
            "start": {"dateTime": (NOW + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
        }

        db = MagicMock()
        # No existing event
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = MagicMock(return_value=mock_result)
        db.add = MagicMock()

        connector._upsert_event(raw, db, user_id=USER_ID)

        # Verify db.add was called with an Event that has user_id set
        assert db.add.called
        added_event = db.add.call_args[0][0]
        assert added_event.user_id == USER_ID

    def test_sync_passes_user_id_to_upsert_event(self):
        """GoogleCalendarConnector.sync passes user_id into _upsert_event calls."""
        from app.connectors.google_calendar import GoogleCalendarConnector

        settings = MagicMock()
        settings.google_calendar_enabled = True
        settings.google_oauth_client_id = "client-id"

        db = MagicMock()

        user_settings = MagicMock()
        user_settings.google_refresh_token = "refresh-token"
        user_settings.google_access_token = "enc-access-token"
        user_settings.google_token_expiry = NOW + timedelta(hours=1)

        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=user_settings)
        db.execute = MagicMock(return_value=result)

        connector = GoogleCalendarConnector(settings=settings, db=db)

        raw_event = {
            "id": "evt1",
            "status": "confirmed",
            "summary": "Sync meeting",
            "start": {"dateTime": (NOW + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=2)).isoformat()},
        }

        with patch.object(connector, "_fetch_events", return_value=[raw_event]):
            with patch("app.connectors.shared.credentials_utils.decrypt_value", return_value="access-token"):
                with patch.object(connector, "_upsert_event", return_value="created") as mock_upsert:
                    connector.sync(USER_ID)
                    # _upsert_event must be called with user_id kwarg
                    assert mock_upsert.called
                    call_args = mock_upsert.call_args
                    # Check user_id was passed (positionally or as keyword)
                    assert USER_ID in call_args.args or call_args.kwargs.get("user_id") == USER_ID
