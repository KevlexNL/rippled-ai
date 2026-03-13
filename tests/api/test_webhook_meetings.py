"""Tests for POST /api/v1/webhooks/meetings/transcript.

Tests verify:
- Valid transcript, X-User-ID authenticated → 201, SourceItemRead returned
- Missing X-User-ID → 401
- Missing required fields → 422
- Duplicate meeting_id → 409
- Webhook secret auth mode works when MEETING_WEBHOOK_SECRET is set
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


def _make_mock_db(duplicate=False):
    mock_session = AsyncMock()

    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None

    added = []

    def mock_add(obj):
        added.append(obj)
        if not getattr(obj, "id", None):
            obj.id = f"test-id-{len(added)}"

    mock_session.add = mock_add
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    if duplicate:
        # First flush (source creation) succeeds; second (item) raises IntegrityError
        flush_call_count = 0

        async def mock_flush_dup():
            nonlocal flush_call_count
            flush_call_count += 1
            if flush_call_count >= 2:
                raise IntegrityError("dup", {}, None)

        mock_session.flush = mock_flush_dup

        mock_existing_result = MagicMock()
        mock_existing_item = MagicMock()
        mock_existing_item.id = "existing-item-id"
        mock_existing_result.scalar_one_or_none.return_value = mock_existing_item
        mock_session.execute = AsyncMock(side_effect=[mock_result_none, mock_existing_result])
    else:
        mock_session.execute = AsyncMock(return_value=mock_result_none)
        mock_session.flush = AsyncMock()

    return mock_session


def _no_secret_settings():
    m = MagicMock()
    m.meeting_webhook_secret = ""
    m.internal_domains = ""
    return m


def _with_secret_settings(secret: str = "meeting-secret"):
    m = MagicMock()
    m.meeting_webhook_secret = secret
    m.internal_domains = ""
    return m


class TestMeetingWebhook:
    def test_valid_transcript_authenticated(self):
        mock_db = _make_mock_db()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.meetings.get_settings", return_value=_no_secret_settings()):
                with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
                    with patch("app.api.routes.source_items._enqueue_detection"):
                        resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 201
            data = resp.json()
            assert "id" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_missing_user_id_returns_401(self):
        with patch("app.api.routes.webhooks.meetings.get_settings", return_value=_no_secret_settings()):
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
        mock_db = _make_mock_db(duplicate=True)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.meetings.get_settings", return_value=_no_secret_settings()):
                with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
                    with patch("app.api.routes.source_items._enqueue_detection"):
                        resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_webhook_secret_auth_accepted(self):
        mock_db = _make_mock_db()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.meetings.get_settings", return_value=_with_secret_settings("meeting-secret")):
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
