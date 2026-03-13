"""Tests for POST /api/v1/sources/test/email and /test/slack endpoints.

Covers:
- Email test success and failure
- Slack test success and failure
- Auth required (no X-User-ID header → 422)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-001"}

EMAIL_TEST_BODY = {
    "email": "test@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "imap_ssl": True,
    "imap_sent_folder": "Sent",
    "app_password": "secret-pass",
    "internal_domains": [],
}

SLACK_TEST_BODY = {
    "bot_token": "xoxb-test-token",
}


class TestEmailTestEndpoint:
    def test_email_test_success(self):
        """Successful IMAP connection returns {success: true, message: ...}."""
        with patch(
            "app.api.routes.sources.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=(True, "Connected to test@example.com — 10 messages in INBOX"),
        ):
            resp = client.post(
                "/api/v1/sources/test/email",
                json=EMAIL_TEST_BODY,
                headers=USER_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "message" in data

    def test_email_test_failure(self):
        """Failed IMAP connection returns {success: false, error: ...}."""
        with patch(
            "app.api.routes.sources.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=(False, "Auth error: invalid credentials"),
        ):
            resp = client.post(
                "/api/v1/sources/test/email",
                json=EMAIL_TEST_BODY,
                headers=USER_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data
        assert "Auth error" in data["error"]

    def test_email_test_requires_auth(self):
        """Missing X-User-ID header → 422 (FastAPI Header(...) raises 422)."""
        resp = client.post(
            "/api/v1/sources/test/email",
            json=EMAIL_TEST_BODY,
        )
        assert resp.status_code == 422


class TestSlackTestEndpoint:
    def test_slack_test_success(self):
        """Valid Slack token → {success: true, workspace: ..., bot_user: ...}."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "team": "My Workspace",
            "user": "rippled-bot",
        }

        with patch("app.api.routes.sources.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/sources/test/slack",
                json=SLACK_TEST_BODY,
                headers=USER_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["workspace"] == "My Workspace"
        assert data["bot_user"] == "rippled-bot"

    def test_slack_test_failure(self):
        """Invalid Slack token → {success: false, error: ...}."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}

        with patch("app.api.routes.sources.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/sources/test/slack",
                json=SLACK_TEST_BODY,
                headers=USER_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data
        assert "invalid_auth" in data["error"]

    def test_slack_test_requires_auth(self):
        """Missing X-User-ID header → 422."""
        resp = client.post(
            "/api/v1/sources/test/slack",
            json=SLACK_TEST_BODY,
        )
        assert resp.status_code == 422
