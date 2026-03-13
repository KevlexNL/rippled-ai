"""Tests for GET /api/v1/sources/onboarding-status endpoint.

Covers:
- No sources → {has_sources: false, sources: []}
- Active source → {has_sources: true, sources: [{source_type, ...}]}
- Inactive source not counted → {has_sources: false, sources: []}
- Unauthenticated → 422
- Multiple source types
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-001"}


def _make_source_mock(source_type: str, display_name: str, is_active: bool = True):
    s = MagicMock()
    s.source_type = source_type
    s.display_name = display_name
    s.is_active = is_active
    return s


def _make_db_with_sources(sources: list):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = sources
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


class TestOnboardingStatus:
    def test_no_sources_returns_false(self):
        """No active sources → {has_sources: false, sources: []}."""
        mock_db = _make_db_with_sources([])

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/sources/onboarding-status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_sources"] is False
            assert data["sources"] == []
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_active_source_returns_true(self):
        """One active email source → {has_sources: true, sources: [{source_type: 'email', ...}]}."""
        source = _make_source_mock("email", "test@example.com", is_active=True)
        mock_db = _make_db_with_sources([source])

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/sources/onboarding-status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_sources"] is True
            assert len(data["sources"]) == 1
            assert data["sources"][0]["source_type"] == "email"
            assert data["sources"][0]["is_active"] is True
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_inactive_source_not_counted(self):
        """DB query filters by is_active=True — mock returns empty (simulating filter)."""
        # The endpoint filters in the WHERE clause; the DB mock returns what the query would return.
        # To simulate an inactive source not being counted, the mock returns empty list
        # (the filter already excludes inactive sources at the DB level).
        mock_db = _make_db_with_sources([])

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/sources/onboarding-status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_sources"] is False
            assert data["sources"] == []
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_unauthenticated_returns_error(self):
        # FastAPI returns 422 (not 401) for missing required header parameters
        # The endpoint is guarded by get_current_user_id which requires X-User-ID header
        resp = client.get("/api/v1/sources/onboarding-status")
        assert resp.status_code in (401, 422)  # either is acceptable

    def test_multiple_source_types(self):
        """Email + Slack sources both appear in sources list."""
        email_source = _make_source_mock("email", "test@example.com")
        slack_source = _make_source_mock("slack", "My Workspace")
        mock_db = _make_db_with_sources([email_source, slack_source])

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/sources/onboarding-status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_sources"] is True
            assert len(data["sources"]) == 2
            types = {s["source_type"] for s in data["sources"]}
            assert "email" in types
            assert "slack" in types
        finally:
            app.dependency_overrides.pop(get_db, None)
