"""Tests for GET /stats response shape.

Verifies the stats endpoint returns the fields the frontend expects,
including the meetings_logged alias.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/stats"
USER_HEADERS = {"X-User-ID": "user-stats-001"}


def _mock_db_for_stats(
    meetings: int = 3,
    slack: int = 12,
    email: int = 7,
    commitments: int = 5,
    sources: int = 2,
    people: int = 4,
):
    """Return a mock session that returns canned stats."""
    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # source_items by type
            row = MagicMock()
            row.meetings = meetings
            row.slack = slack
            row.email = email
            result.one.return_value = row
        elif call_count == 2:
            # commitments count
            result.scalar.return_value = commitments
        elif call_count == 3:
            # sources count
            result.scalar.return_value = sources
        elif call_count == 4:
            # people count
            result.scalar.return_value = people
        return result

    mock_session.execute = mock_execute
    return mock_session


class TestStatsShape:
    def test_returns_200(self):
        mock_db = _mock_db_for_stats()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_has_frontend_required_fields(self):
        """Frontend expects: emails_captured, messages_processed, meetings_logged, people_identified."""
        mock_db = _mock_db_for_stats()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            for field in ("emails_captured", "messages_processed", "meetings_logged", "people_identified"):
                assert field in data, f"Missing field: {field}"
                assert isinstance(data[field], int), f"{field} should be int"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_meetings_logged_matches_meetings_analyzed(self):
        """meetings_logged should be an alias that returns the same value as meetings_analyzed."""
        mock_db = _mock_db_for_stats(meetings=42)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            assert data["meetings_logged"] == 42
            # Backwards compat: meetings_analyzed should also be present
            assert data["meetings_analyzed"] == 42
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_all_values_are_integers(self):
        mock_db = _mock_db_for_stats(meetings=1, slack=2, email=3, commitments=4, sources=5, people=6)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            for key, val in data.items():
                assert isinstance(val, int), f"{key} should be int, got {type(val)}"
        finally:
            app.dependency_overrides.pop(get_db, None)
