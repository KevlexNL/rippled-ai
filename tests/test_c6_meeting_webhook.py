"""Tests for Phase C6 — Meeting webhook per-source secret verification.

TDD: Tests written before implementation.
Covers:
- When source has webhook_secret in credentials → verify X-Rippled-Webhook-Secret
- When source has no webhook_secret → accept any payload (skip verification)
- When source not found → accept payload (skip verification)
- Still requires X-User-ID header in all cases
- Valid secret passes verification
- Invalid secret is rejected with 401
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
USER_ID = "test-user-" + str(uuid.uuid4())[:8]


def _make_source(webhook_secret: str | None = None):
    source = MagicMock()
    source.id = str(uuid.uuid4())
    source.user_id = USER_ID
    source.source_type = "meeting"
    source.credentials = {"webhook_secret": webhook_secret} if webhook_secret else {}
    return source


def _minimal_payload():
    return {
        "meeting_id": "mtg-123",
        "title": "Team sync",
        "started_at": "2026-03-15T10:00:00Z",
        "ended_at": "2026-03-15T11:00:00Z",
        "participants": [],
        "segments": [],
    }


class TestMeetingWebhookPerSourceAuth:
    def test_accepts_request_when_source_has_no_webhook_secret(self):
        """When source has no webhook_secret, request is accepted without secret header."""

        async def fake_get_db():
            db = AsyncMock()
            source = _make_source(webhook_secret=None)

            # Source lookup result
            source_result = MagicMock()
            source_result.scalar_one_or_none = MagicMock(return_value=source)

            # _get_or_create_source lookup (called inside handler)
            provider_result = MagicMock()
            provider_result.scalar_one_or_none = MagicMock(return_value=source)

            # source_item add/flush
            db.execute = AsyncMock(side_effect=[source_result, provider_result])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            with patch("app.tasks.process_slack_event") as _mock:
                with patch("app.api.routes.source_items._build_item") as mock_build:
                    with patch("app.api.routes.source_items._enqueue_detection"):
                        mock_item = MagicMock()
                        mock_item.id = str(uuid.uuid4())
                        mock_item.source_id = str(uuid.uuid4())
                        mock_item.user_id = USER_ID
                        mock_item.source_type = "meeting"
                        mock_item.external_id = "mtg-123"
                        mock_item.thread_id = None
                        mock_item.direction = None
                        mock_item.sender_name = None
                        mock_item.sender_email = None
                        mock_item.content = None
                        mock_item.has_attachment = False
                        mock_item.source_url = None
                        from datetime import datetime, timezone
                        mock_item.occurred_at = datetime.now(timezone.utc)
                        mock_item.ingested_at = datetime.now(timezone.utc)
                        mock_item.is_quoted_content = False
                        mock_build.return_value = mock_item

                        resp = client.post(
                            "/api/v1/webhooks/meetings/transcript",
                            json=_minimal_payload(),
                            headers={"x-user-id": USER_ID},
                            # No X-Rippled-Webhook-Secret header
                        )
        finally:
            app.dependency_overrides.pop(get_db, None)

        # Should NOT be rejected due to missing secret
        assert resp.status_code != 401

    def test_rejects_request_when_source_has_secret_and_no_header(self):
        """When source has webhook_secret but no header provided → 401."""

        async def fake_get_db():
            db = AsyncMock()
            source = _make_source(webhook_secret="my-secret-key")

            source_result = MagicMock()
            source_result.scalar_one_or_none = MagicMock(return_value=source)

            db.execute = AsyncMock(return_value=source_result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            resp = client.post(
                "/api/v1/webhooks/meetings/transcript",
                json=_minimal_payload(),
                headers={"x-user-id": USER_ID},
                # No X-Rippled-Webhook-Secret
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    def test_rejects_request_when_source_has_secret_and_wrong_header(self):
        """When source has webhook_secret and wrong header is provided → 401."""

        async def fake_get_db():
            db = AsyncMock()
            source = _make_source(webhook_secret="correct-secret")

            source_result = MagicMock()
            source_result.scalar_one_or_none = MagicMock(return_value=source)

            db.execute = AsyncMock(return_value=source_result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            resp = client.post(
                "/api/v1/webhooks/meetings/transcript",
                json=_minimal_payload(),
                headers={
                    "x-user-id": USER_ID,
                    "x-rippled-webhook-secret": "wrong-secret",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    def test_accepts_request_when_source_has_secret_and_correct_header(self):
        """When source has webhook_secret and correct header is provided → accepted."""

        async def fake_get_db():
            db = AsyncMock()
            source = _make_source(webhook_secret="correct-secret")

            source_result = MagicMock()
            source_result.scalar_one_or_none = MagicMock(return_value=source)

            provider_result = MagicMock()
            provider_result.scalar_one_or_none = MagicMock(return_value=source)

            db.execute = AsyncMock(side_effect=[source_result, provider_result])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            with patch("app.api.routes.source_items._build_item") as mock_build:
                with patch("app.api.routes.source_items._enqueue_detection"):
                    mock_item = MagicMock()
                    mock_item.id = str(uuid.uuid4())
                    mock_item.source_id = str(uuid.uuid4())
                    mock_item.user_id = USER_ID
                    mock_item.source_type = "meeting"
                    mock_item.external_id = "mtg-123"
                    mock_item.thread_id = None
                    mock_item.direction = None
                    mock_item.sender_name = None
                    mock_item.sender_email = None
                    mock_item.content = None
                    mock_item.has_attachment = False
                    mock_item.source_url = None
                    from datetime import datetime, timezone
                    mock_item.occurred_at = datetime.now(timezone.utc)
                    mock_item.ingested_at = datetime.now(timezone.utc)
                    mock_item.is_quoted_content = False
                    mock_build.return_value = mock_item

                    resp = client.post(
                        "/api/v1/webhooks/meetings/transcript",
                        json=_minimal_payload(),
                        headers={
                            "x-user-id": USER_ID,
                            "x-rippled-webhook-secret": "correct-secret",
                        },
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code != 401

    def test_accepts_request_when_no_source_found(self):
        """When no meeting source found for user → skip verification, accept payload."""

        async def fake_get_db():
            db = AsyncMock()

            # No source found
            source_result = MagicMock()
            source_result.scalar_one_or_none = MagicMock(return_value=None)

            # _get_or_create_source will create one
            provider_result = MagicMock()
            provider_result.scalar_one_or_none = MagicMock(return_value=None)

            db.execute = AsyncMock(side_effect=[source_result, provider_result])
            db.add = MagicMock()
            db.flush = AsyncMock()

            # db.refresh must set source.id so normalise_meeting_transcript doesn't fail
            async def mock_refresh(obj):
                if not getattr(obj, 'id', None):
                    obj.id = str(uuid.uuid4())

            db.refresh = mock_refresh
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            with patch("app.api.routes.source_items._build_item") as mock_build:
                with patch("app.api.routes.source_items._enqueue_detection"):
                    mock_item = MagicMock()
                    mock_item.id = str(uuid.uuid4())
                    mock_item.source_id = str(uuid.uuid4())
                    mock_item.user_id = USER_ID
                    mock_item.source_type = "meeting"
                    mock_item.external_id = "mtg-123"
                    mock_item.thread_id = None
                    mock_item.direction = None
                    mock_item.sender_name = None
                    mock_item.sender_email = None
                    mock_item.content = None
                    mock_item.has_attachment = False
                    mock_item.source_url = None
                    from datetime import datetime, timezone
                    mock_item.occurred_at = datetime.now(timezone.utc)
                    mock_item.ingested_at = datetime.now(timezone.utc)
                    mock_item.is_quoted_content = False
                    mock_build.return_value = mock_item

                    resp = client.post(
                        "/api/v1/webhooks/meetings/transcript",
                        json=_minimal_payload(),
                        headers={"x-user-id": USER_ID},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code != 401

    def test_requires_user_id_header(self):
        """POST /webhooks/meetings/transcript requires X-User-ID header."""
        resp = client.post(
            "/api/v1/webhooks/meetings/transcript",
            json=_minimal_payload(),
            # No x-user-id header
        )
        assert resp.status_code == 401
