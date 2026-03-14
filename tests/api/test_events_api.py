"""Tests for Phase C3 — Events API.

Covers:
- GET /events returns list
- GET /events/{id} with linked commitment count
- POST /events creates implicit event → 201
- PATCH /events/{id} reschedule updates rescheduled_from
- PATCH /events/{id} cancel sets status='cancelled'
- GET /events with no events → empty list
- GET /events/{id} not found → 404
- PATCH /events/{id} invalid status → 422
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-001"}
URL = "/api/v1/events"

NOW = datetime.now(timezone.utc)


def _make_event(event_id=None, **kwargs):
    """Create a mock Event ORM object."""
    defaults = {
        "id": event_id or str(uuid.uuid4()),
        "external_id": None,
        "title": "Client sync",
        "description": None,
        "starts_at": NOW + timedelta(hours=4),
        "ends_at": NOW + timedelta(hours=5),
        "event_type": "explicit",
        "status": "confirmed",
        "is_recurring": False,
        "recurrence_rule": None,
        "location": None,
        "attendees": None,
        "rescheduled_from": None,
        "cancelled_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    event = MagicMock()
    for k, v in defaults.items():
        setattr(event, k, v)
    return event


def _make_mock_db(events=None, links_count=0):
    """Create async mock DB session."""
    mock_session = AsyncMock()

    if events is None:
        events = []

    # Scalars result for list query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = events

    # For count query
    count_result = MagicMock()
    count_result.scalar.return_value = links_count
    count_result.all.return_value = []

    call_count = [0]

    async def execute(q):
        call_count[0] += 1
        # First call: events list; subsequent calls: counts
        if call_count[0] == 1:
            return events_result
        return count_result

    mock_session.execute = execute
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


# ---------------------------------------------------------------------------
# GET /events
# ---------------------------------------------------------------------------


class TestGetEvents:

    def test_returns_empty_list_when_no_events(self):
        """No events → empty list."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_db = _make_mock_db(events=[])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(URL, headers=USER_HEADERS)
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_returns_events_list(self):
        """Events in next 30d → returned in response."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        event = _make_event()
        mock_db = _make_mock_db(events=[event])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(URL, headers=USER_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["title"] == "Client sync"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# GET /events/{id}
# ---------------------------------------------------------------------------


class TestGetEvent:

    def test_not_found_returns_404(self):
        """Unknown event ID → 404."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(f"{URL}/nonexistent-id", headers=USER_HEADERS)
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_returns_event_with_linked_count(self):
        """Found event → returned with linked_commitment_count."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        event_id = str(uuid.uuid4())
        event = _make_event(event_id=event_id)
        mock_session = AsyncMock()
        call_count = [0]

        async def execute(q):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = event
            else:
                result.scalar.return_value = 2  # 2 linked commitments
            return result

        mock_session.execute = execute
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(f"{URL}/{event_id}", headers=USER_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == event_id
            assert data["linked_commitment_count"] == 2
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------


class TestCreateEvent:

    def test_creates_implicit_event(self):
        """Valid payload → 201, event_type='implicit'."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        new_id = str(uuid.uuid4())
        event = _make_event(event_id=new_id, event_type="implicit")
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        async def mock_refresh(obj):
            obj.id = new_id
            obj.event_type = "implicit"
            obj.status = "confirmed"
            obj.is_recurring = False
            obj.created_at = NOW
            obj.updated_at = NOW
            obj.external_id = None
            obj.description = None
            obj.ends_at = None
            obj.location = None
            obj.attendees = None
            obj.rescheduled_from = None

        mock_session.refresh = mock_refresh
        mock_session.add = MagicMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.post(
                URL,
                json={
                    "title": "Delivery checkpoint",
                    "starts_at": (NOW + timedelta(hours=24)).isoformat(),
                },
                headers=USER_HEADERS,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["event_type"] == "implicit"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_missing_title_returns_422(self):
        """Missing required title → 422."""
        response = client.post(
            URL,
            json={"starts_at": (NOW + timedelta(hours=24)).isoformat()},
            headers=USER_HEADERS,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /events/{id}
# ---------------------------------------------------------------------------


class TestPatchEvent:

    def _setup(self, event):
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = AsyncMock()
        call_count = [0]

        async def execute(q):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = event
            else:
                result.scalar.return_value = 0  # linked count
            return result

        mock_session.execute = execute
        mock_session.flush = AsyncMock()

        async def mock_refresh(obj):
            pass

        mock_session.refresh = mock_refresh
        mock_session.add = MagicMock()
        return mock_session

    def test_reschedule_sets_rescheduled_from(self):
        """PATCH with new starts_at → rescheduled_from updated."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        original_start = NOW + timedelta(hours=4)
        event = _make_event(starts_at=original_start)
        mock_session = self._setup(event)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            new_start = (NOW + timedelta(hours=8)).isoformat()
            response = client.patch(
                f"{URL}/{event.id}",
                json={"starts_at": new_start},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            assert event.rescheduled_from == original_start
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_cancel_sets_status_cancelled(self):
        """PATCH with status='cancelled' → event.status='cancelled'."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        event = _make_event()
        mock_session = self._setup(event)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.patch(
                f"{URL}/{event.id}",
                json={"status": "cancelled"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            assert event.status == "cancelled"
            assert event.cancelled_at is not None
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_invalid_status_returns_422(self):
        """PATCH with invalid status → 422."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        event = _make_event()
        mock_session = self._setup(event)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.patch(
                f"{URL}/{event.id}",
                json={"status": "deleted"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)
