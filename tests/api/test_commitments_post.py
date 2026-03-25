"""Tests for POST /api/v1/commitments.

Tests verify:
- Valid payload + X-User-ID header → 201, returns commitment with title
- Missing required title → 422 validation error
- Missing X-User-ID header → 422 (FastAPI Header(...) raises 422 when header absent)
- Optional fields populated → 201, fields returned
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/commitments"

USER_HEADERS = {"X-User-ID": "user-001"}

VALID_PAYLOAD = {
    "title": "Send the report by Friday",
}

FULL_PAYLOAD = {
    "title": "Deliver the proposal",
    "description": "Proposal for Q2 project",
    "commitment_text": "I'll deliver the proposal by end of week",
    "context_type": "email",
    "resolved_owner": "alice@example.com",
    "confidence_commitment": "0.9",
    "confidence_actionability": "0.85",
}


def _make_mock_db(commitment_id: str = "commit-001"):
    """Return an async mock DB session that simulates a successful commit creation."""
    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()

    # Mock db.execute() to return a result whose .scalars().all() → []
    # (needed for the context auto-assign query added in WO-002)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    added = []

    def mock_add(obj):
        added.append(obj)
        # Simulate what the DB would set via server_default
        if not getattr(obj, "id", None):
            obj.id = commitment_id
        if not getattr(obj, "version", None):
            obj.version = 1
        if not getattr(obj, "lifecycle_state", None):
            obj.lifecycle_state = "proposed"

    mock_session.add = mock_add

    async def mock_refresh(obj):
        # Populate fields that the DB normally sets
        from datetime import datetime, timezone

        obj.id = commitment_id
        obj.version = 1
        obj.lifecycle_state = "proposed"
        obj.is_surfaced = False
        obj.surfaced_at = None
        obj.state_changed_at = datetime.now(timezone.utc)
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)
        obj.confidence_owner = None
        obj.confidence_deadline = None
        obj.confidence_delivery = None
        obj.confidence_closure = None
        obj.missing_pieces_explanation = None
        obj.observe_until = None
        obj.observation_window_hours = None
        obj.surfaced_as = None
        obj.priority_score = None
        obj.timing_strength = None
        obj.business_consequence = None
        obj.cognitive_burden = None
        obj.confidence_for_surfacing = None
        obj.surfacing_reason = None

    mock_session.refresh = mock_refresh

    return mock_session


class TestCreateCommitment:
    def test_valid_payload_returns_201_with_title(self):
        mock_db = _make_mock_db()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == VALID_PAYLOAD["title"]
            assert data["lifecycle_state"] == "proposed"
            assert data["id"] == "commit-001"
            assert data["user_id"] == "user-001"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_missing_title_returns_422(self):
        resp = client.post(URL, json={}, headers=USER_HEADERS)
        assert resp.status_code == 422

    def test_missing_user_id_header_returns_422(self):
        # FastAPI Header(...) raises 422 when a required header is absent
        resp = client.post(URL, json=VALID_PAYLOAD)
        assert resp.status_code == 422

    def test_optional_fields_populated_returns_201(self):
        mock_db = _make_mock_db(commitment_id="commit-002")
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.post(URL, json=FULL_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == FULL_PAYLOAD["title"]
            assert data["description"] == FULL_PAYLOAD["description"]
            assert data["context_type"] == FULL_PAYLOAD["context_type"]
            assert data["resolved_owner"] == FULL_PAYLOAD["resolved_owner"]
            assert data["id"] == "commit-002"
        finally:
            app.dependency_overrides.pop(get_db, None)
