"""Tests for Phase C6 — Stats endpoint.

TDD: Tests written before implementation.
Covers:
- GET /api/v1/stats returns correct shape
- Counts meetings_analyzed, messages_processed, emails_captured from source_items
- Counts commitments_detected from commitments table
- Counts sources_connected (is_active=True) from sources table
- Returns all zeros when user has no data
- Requires X-User-ID auth
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
USER_HEADERS = {"x-user-id": USER_ID}


def _make_stats_db(
    meetings: int = 0,
    slack: int = 0,
    email: int = 0,
    commitments: int = 0,
    sources: int = 0,
):
    """Build a mock DB that returns the given stat counts."""

    async def fake_get_db():
        db = AsyncMock()

        # First execute: source_items counts (one() row)
        items_row = MagicMock()
        items_row.meetings = meetings
        items_row.slack = slack
        items_row.email = email
        items_result = MagicMock()
        items_result.one = MagicMock(return_value=items_row)

        # Second execute: commitments count (scalar())
        commitments_result = MagicMock()
        commitments_result.scalar = MagicMock(return_value=commitments)

        # Third execute: sources count (scalar())
        sources_result = MagicMock()
        sources_result.scalar = MagicMock(return_value=sources)

        db.execute = AsyncMock(side_effect=[items_result, commitments_result, sources_result])
        yield db

    return fake_get_db


class TestStatsEndpoint:
    def test_stats_returns_correct_shape(self):
        """GET /api/v1/stats returns all expected fields."""
        app.dependency_overrides[get_db] = _make_stats_db()
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/stats", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "meetings_analyzed" in data
        assert "messages_processed" in data
        assert "emails_captured" in data
        assert "commitments_detected" in data
        assert "sources_connected" in data

    def test_stats_returns_all_zeros_for_new_user(self):
        """GET /api/v1/stats returns zeros when user has no data."""
        app.dependency_overrides[get_db] = _make_stats_db()
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/stats", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["meetings_analyzed"] == 0
        assert data["messages_processed"] == 0
        assert data["emails_captured"] == 0
        assert data["commitments_detected"] == 0
        assert data["sources_connected"] == 0

    def test_stats_returns_correct_counts(self):
        """GET /api/v1/stats returns non-zero counts correctly."""
        app.dependency_overrides[get_db] = _make_stats_db(
            meetings=5, slack=12, email=3, commitments=8, sources=2
        )
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/stats", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["meetings_analyzed"] == 5
        assert data["messages_processed"] == 12
        assert data["emails_captured"] == 3
        assert data["commitments_detected"] == 8
        assert data["sources_connected"] == 2

    def test_stats_requires_auth(self):
        """GET /api/v1/stats returns 422 without X-User-ID header."""
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 422
