"""Tests for POST /api/v1/webhooks/meetings/transcript.

Tests verify:
- Valid transcript, X-User-ID authenticated → 201, SourceItemRead returned
- Missing X-User-ID → 401
- Missing required fields → 422
- Duplicate meeting_id → 409
- Webhook secret auth mode works when source has webhook_secret in credentials
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app

client = TestClient(app)
URL = "/api/v1/webhooks/meetings/transcript"

VALID_PAYLOAD = {
    "meeting_id": "meeting-001",
    "meeting_title": "Sprint Planning",
    "started_at": "2024-01-15T09:00:00Z",
    "ended_at": "2024-01-15T10:00:00Z",
    "participants": [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob", "email": "bob@example.com"},
    ],
    "segments": [
        {"speaker": "Alice", "text": "I'll prepare the report.", "start_seconds": 0.0, "end_seconds": 5.0},
        {"speaker": "Bob", "text": "Sounds good.", "start_seconds": 5.0, "end_seconds": 8.0},
    ],
}
USER_HEADERS = {"X-User-ID": "user-001"}


def _make_no_source_result():
    """DB execute result that returns no source (None)."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    return r


def _make_source_with_secret(secret: str):
    """DB execute result returning a source with webhook_secret in credentials."""
    source = MagicMock()
    source.id = "source-with-secret"
    source.user_id = "user-001"
    source.source_type = "meeting"
    source.credentials = {"webhook_secret": secret}
    r = MagicMock()
    r.scalar_one_or_none.return_value = source
    return r


def _make_mock_db_no_secret():
    """Mock DB where all source lookups return None (no secret required)."""
    mock_session = AsyncMock()

    added = []

    def mock_add(obj):
        added.append(obj)
        if not getattr(obj, "id", None):
            obj.id = f"test-id-{len(added)}"

    mock_session.add = mock_add
    mock_session.flush = AsyncMock()

    async def mock_refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = f"refreshed-id-{len(added)}"

    mock_session.refresh = mock_refresh
    mock_session.rollback = AsyncMock()
    # All execute calls return no source
    mock_session.execute = AsyncMock(return_value=_make_no_source_result())
    return mock_session


def _make_mock_db_duplicate():
    """Mock DB for duplicate item scenario."""
    mock_session = AsyncMock()

    added = []

    def mock_add(obj):
        added.append(obj)
        if not getattr(obj, "id", None):
            obj.id = f"test-id-{len(added)}"

    mock_session.add = mock_add
    mock_session.rollback = AsyncMock()

    flush_call_count = 0

    async def mock_flush_dup():
        nonlocal flush_call_count
        flush_call_count += 1
        if flush_call_count >= 2:
            raise IntegrityError("dup", {}, None)

    mock_session.flush = mock_flush_dup

    async def mock_refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = f"refreshed-id-{len(added)}"

    mock_session.refresh = mock_refresh

    mock_existing_item = MagicMock()
    mock_existing_item.id = "existing-item-id"
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = mock_existing_item

    # Execute order:
    # 1. _verify_meeting_auth → no source (no secret needed)
    # 2. _get_or_create_source → no existing source (creates new)
    # 3. duplicate SourceItem lookup after IntegrityError → existing item
    mock_session.execute = AsyncMock(side_effect=[
        _make_no_source_result(),
        _make_no_source_result(),
        mock_existing_result,
    ])
    return mock_session


def _make_mock_db_with_secret(secret: str):
    """Mock DB where source lookup returns a source with a configured webhook_secret."""
    mock_session = AsyncMock()

    added = []

    def mock_add(obj):
        added.append(obj)
        if not getattr(obj, "id", None):
            obj.id = f"test-id-{len(added)}"

    mock_session.add = mock_add
    mock_session.flush = AsyncMock()

    async def mock_refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = f"refreshed-id-{len(added)}"

    mock_session.refresh = mock_refresh
    mock_session.rollback = AsyncMock()

    # Execute order:
    # 1. _verify_meeting_auth → source with webhook_secret (verification required)
    # 2. _get_or_create_source → source exists (reuses it)
    source = MagicMock()
    source.id = "existing-source-id"
    source.user_id = "user-001"
    source.source_type = "meeting"
    source.credentials = {"webhook_secret": secret}
    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = source

    mock_session.execute = AsyncMock(return_value=source_result)
    return mock_session


class TestMeetingWebhook:
    def test_valid_transcript_authenticated(self):
        mock_db = _make_mock_db_no_secret()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 201
            data = resp.json()
            assert "id" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_missing_user_id_returns_401(self):
        # _verify_meeting_auth checks user_id before DB access → 401 without DB needed
        resp = client.post(URL, json=VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_invalid_payload_returns_422(self):
        # Missing required 'segments' and 'participants'
        resp = client.post(
            URL,
            json={"meeting_id": "m1", "started_at": "2024-01-01T09:00:00Z"},
            headers=USER_HEADERS,
        )
        assert resp.status_code == 422

    def test_duplicate_meeting_id_returns_409(self):
        mock_db = _make_mock_db_duplicate()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_webhook_secret_auth_accepted(self):
        mock_db = _make_mock_db_with_secret("meeting-secret")
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(
                        URL,
                        json=VALID_PAYLOAD,
                        headers={**USER_HEADERS, "X-Rippled-Webhook-Secret": "meeting-secret"},
                    )
            assert resp.status_code == 201
        finally:
            app.dependency_overrides.pop(get_db, None)
