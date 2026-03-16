"""Integration tests for Slack OAuth flow against the real Supabase DB.

These tests:
- Use a real DB connection (no mocks for DB layer)
- Mock only the external Slack API calls
- Verify that OAuth callback creates/updates Source rows
- Clean up all test data in teardown (via conftest.py module fixture)
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from dotenv import load_dotenv
load_dotenv(override=True)


def _make_async_url(url: str) -> str:
    return (
        url
        .replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
    )


def _db_url() -> str:
    return _make_async_url(os.environ.get("DATABASE_URL", ""))


async def _query_sources(user_id: str) -> list[dict]:
    """Directly query the DB for sources belonging to user_id."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text, bindparam
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    engine = create_async_engine(_db_url(), connect_args={"statement_cache_size": 0})
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id, source_type, display_name, is_active, provider_account_id "
                    "FROM sources WHERE user_id = :uid"
                ).bindparams(bindparam("uid", type_=PGUUID(as_uuid=False))),
                {"uid": user_id},
            )
            return [dict(row._mapping) for row in result]
    finally:
        await engine.dispose()


# Mock Slack OAuth response
SLACK_OAUTH_RESPONSE = {
    "ok": True,
    "access_token": "xoxb-test-token-12345",
    "token_type": "bot",
    "scope": "channels:history,channels:read,im:history,im:read,users:read",
    "bot_user_id": "U_BOT_TEST",
    "app_id": "A_TEST",
    "team": {"id": "T_TEST_TEAM", "name": "Test Workspace"},
    "authed_user": {"id": "U_TEST_USER"},
}


class TestSlackOAuth:
    """Integration tests for Slack OAuth install flow."""

    def test_01_oauth_start_redirects_to_slack(self, client, test_user_headers):
        """GET /integrations/slack/oauth/start should redirect to Slack authorize URL."""
        with patch("app.api.routes.integrations.settings") as mock_settings:
            mock_settings.slack_client_id = "test-client-id"
            mock_settings.slack_client_secret = "test-client-secret"
            mock_settings.slack_oauth_redirect_uri = "https://example.com/callback"
            mock_settings.base_url = "https://example.com"
            mock_settings.api_prefix = "/api/v1"

            resp = client.get(
                "/api/v1/integrations/slack/oauth/start",
                headers=test_user_headers,
                follow_redirects=False,
            )

        assert resp.status_code == 307, resp.text
        location = resp.headers["location"]
        assert "slack.com/oauth/v2/authorize" in location
        assert "client_id=test-client-id" in location
        assert "im%3Ahistory" in location or "im:history" in location

    def test_02_oauth_start_returns_503_when_not_configured(self, client, test_user_headers):
        """Should return 503 when SLACK_CLIENT_ID is not set."""
        with patch("app.api.routes.integrations.settings") as mock_settings:
            mock_settings.slack_client_id = ""
            mock_settings.slack_client_secret = ""

            resp = client.get(
                "/api/v1/integrations/slack/oauth/start",
                headers=test_user_headers,
            )

        assert resp.status_code == 503

    def test_03_oauth_callback_creates_source(self, client, test_user_id, test_user_headers):
        """OAuth callback with valid code should create a Slack source in DB."""
        # First, ensure user row exists
        client.get("/api/v1/sources/onboarding-status", headers=test_user_headers)

        mock_response = MagicMock()
        mock_response.json.return_value = SLACK_OAUTH_RESPONSE

        with patch("app.api.routes.integrations.settings") as mock_settings, \
             patch("app.api.routes.integrations.httpx.AsyncClient") as mock_client_cls:
            mock_settings.slack_client_id = "test-client-id"
            mock_settings.slack_client_secret = "test-client-secret"
            mock_settings.slack_oauth_redirect_uri = "https://example.com/callback"
            mock_settings.slack_signing_secret = "test-signing-secret"
            mock_settings.base_url = "https://example.com"
            mock_settings.api_prefix = "/api/v1"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = client.get(
                f"/api/v1/integrations/slack/oauth/callback?code=test-code&state={test_user_id}",
                follow_redirects=False,
            )

        assert resp.status_code == 307, resp.text
        assert "slack=connected" in resp.headers["location"]

        # Verify source was created in DB
        sources = asyncio.run(_query_sources(test_user_id))
        slack_sources = [s for s in sources if str(s["source_type"]) == "slack"]
        assert len(slack_sources) == 1, f"Expected 1 Slack source, found {len(slack_sources)}"
        assert slack_sources[0]["display_name"] == "Test Workspace"
        assert str(slack_sources[0]["provider_account_id"]) == "T_TEST_TEAM"
        assert slack_sources[0]["is_active"] is True

    def test_04_oauth_callback_error_redirects(self, client):
        """OAuth callback with error param should redirect to settings with error."""
        with patch("app.api.routes.integrations.settings") as mock_settings:
            mock_settings.slack_client_id = "test-client-id"
            mock_settings.slack_client_secret = "test-client-secret"

            resp = client.get(
                "/api/v1/integrations/slack/oauth/callback?error=access_denied",
                follow_redirects=False,
            )

        assert resp.status_code == 307
        assert "slack=error" in resp.headers["location"]

    def test_05_oauth_callback_is_idempotent(self, client, test_user_id, test_user_headers):
        """Calling OAuth callback again should update, not duplicate, the Slack source."""
        updated_response = {
            **SLACK_OAUTH_RESPONSE,
            "team": {"id": "T_TEST_TEAM", "name": "Updated Workspace"},
        }

        mock_response = MagicMock()
        mock_response.json.return_value = updated_response

        with patch("app.api.routes.integrations.settings") as mock_settings, \
             patch("app.api.routes.integrations.httpx.AsyncClient") as mock_client_cls:
            mock_settings.slack_client_id = "test-client-id"
            mock_settings.slack_client_secret = "test-client-secret"
            mock_settings.slack_oauth_redirect_uri = "https://example.com/callback"
            mock_settings.slack_signing_secret = "test-signing-secret"
            mock_settings.base_url = "https://example.com"
            mock_settings.api_prefix = "/api/v1"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = client.get(
                f"/api/v1/integrations/slack/oauth/callback?code=test-code-2&state={test_user_id}",
                follow_redirects=False,
            )

        assert resp.status_code == 307

        sources = asyncio.run(_query_sources(test_user_id))
        slack_sources = [s for s in sources if str(s["source_type"]) == "slack"]
        assert len(slack_sources) == 1, "OAuth upsert should not create duplicate Slack sources"
        assert slack_sources[0]["display_name"] == "Updated Workspace"
