"""Tests for POST /api/v1/webhooks/email/inbound.

Tests verify:
- Valid payload, no secret configured → 200, item accepted
- Valid payload with correct secret → 200
- Valid payload with wrong secret → 403 (when EMAIL_WEBHOOK_SECRET set)
- Invalid payload (missing required field) → 422
- Duplicate message_id → 409
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app

client = TestClient(app)
URL = "/api/v1/webhooks/email/inbound"

VALID_PAYLOAD = {
    "message_id": "<msg001@example.com>",
    "from_email": "alice@example.com",
    "from_name": "Alice Smith",
    "to": ["bob@example.com"],
    "subject": "Project Update",
    "body_plain": "I'll send the report by Friday.",
    "date": "2024-01-01T12:00:00Z",
    "direction": "inbound",
}
USER_HEADERS = {"X-User-ID": "user-001"}


def _make_mock_db(source_id="src-001", item_id="item-001", duplicate=False):
    """Return an async mock DB session."""
    mock_session = AsyncMock()

    # source lookup: no existing source
    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None

    # Track added objects and set id on them
    added = []

    def mock_add(obj):
        added.append(obj)
        if not getattr(obj, "id", None):
            obj.id = source_id if len(added) == 1 else item_id

    mock_session.add = mock_add
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    if duplicate:
        # First flush (source creation) succeeds; second flush (item) raises IntegrityError
        flush_call_count = 0

        async def mock_flush_dup():
            nonlocal flush_call_count
            flush_call_count += 1
            if flush_call_count >= 2:
                raise IntegrityError("dup", {}, None)

        mock_session.flush = mock_flush_dup

        # First execute: source lookup → None; second: find existing item
        mock_existing_result = MagicMock()
        mock_existing_item = MagicMock()
        mock_existing_item.id = "existing-item-id"
        mock_existing_result.scalar_one_or_none.return_value = mock_existing_item
        mock_session.execute = AsyncMock(side_effect=[mock_result_none, mock_existing_result])
    else:
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result_none)

    return mock_session


def _make_settings(email_secret: str = ""):
    m = MagicMock()
    m.email_webhook_secret = email_secret
    m.internal_domains = ""
    return m


async def _override_db_factory(mock_db):
    async def _override():
        yield mock_db
    return _override


class TestEmailWebhook:
    def test_valid_payload_no_secret_configured(self):
        mock_db = _make_mock_db()

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.email.get_settings", return_value=_make_settings("")):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["accepted"] == 1
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_correct_secret_accepted(self):
        mock_db = _make_mock_db()
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.email.get_settings", return_value=_make_settings("my-secret")):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(
                        URL,
                        json=VALID_PAYLOAD,
                        headers={**USER_HEADERS, "X-Email-Webhook-Secret": "my-secret"},
                    )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_wrong_secret_returns_403(self):
        with patch("app.api.routes.webhooks.email.get_settings", return_value=_make_settings("real-secret")):
            resp = client.post(
                URL,
                json=VALID_PAYLOAD,
                headers={**USER_HEADERS, "X-Email-Webhook-Secret": "wrong-secret"},
            )
        assert resp.status_code == 403

    def test_invalid_payload_returns_422(self):
        # Missing required 'from_email' and 'date' fields
        resp = client.post(URL, json={"message_id": "abc"}, headers=USER_HEADERS)
        assert resp.status_code == 422

    def test_duplicate_message_id_returns_409(self):
        mock_db = _make_mock_db(duplicate=True)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.webhooks.email.get_settings", return_value=_make_settings("")):
                with patch("app.api.routes.source_items._enqueue_detection"):
                    resp = client.post(URL, json=VALID_PAYLOAD, headers=USER_HEADERS)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_db, None)
