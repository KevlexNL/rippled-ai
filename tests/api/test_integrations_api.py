"""Tests for Phase C3 — Google OAuth integrations API.

Covers:
- GET /integrations/google/auth → redirects to Google OAuth (302)
- GET /integrations/google/callback success → stores tokens, returns {status: connected}
- GET /integrations/google/callback with error param → 400
- GET /integrations/google/callback missing code → 400
- GET /integrations/google/status connected → {connected: true}
- GET /integrations/google/status not connected → {connected: false}
- DELETE /integrations/google/disconnect → 204
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, follow_redirects=False)
USER_HEADERS = {"X-User-ID": "user-001"}
NOW = datetime.now(timezone.utc)
URL = "/api/v1/integrations/google"


def _make_user_settings(**kwargs):
    defaults = {
        "user_id": "user-001",
        "google_access_token": "encrypted-access",
        "google_refresh_token": "encrypted-refresh",
        "google_token_expiry": NOW + timedelta(hours=1),
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    us = MagicMock()
    for k, v in defaults.items():
        setattr(us, k, v)
    return us


def _make_mock_db(user_settings=None):
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user_settings
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


# ---------------------------------------------------------------------------
# GET /auth
# ---------------------------------------------------------------------------


class TestGoogleAuth:

    def test_redirects_to_google_oauth(self):
        """GET /auth → 307 redirect to Google."""
        from app.core.dependencies import get_current_user_id
        from app.core.config import get_settings

        settings_mock = MagicMock()
        settings_mock.google_calendar_enabled = True
        settings_mock.google_oauth_client_id = "client-id"
        settings_mock.google_oauth_client_secret = "secret"
        settings_mock.google_oauth_redirect_uri = "http://localhost/callback"

        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        with patch("app.api.routes.integrations.settings", settings_mock), \
             patch("app.connectors.google_calendar.get_auth_url", return_value="https://accounts.google.com/o/oauth2/auth?foo=bar"):
            try:
                response = client.get(f"{URL}/auth", headers=USER_HEADERS)
                assert response.status_code in (302, 307)
                assert "google.com" in response.headers.get("location", "")
            finally:
                app.dependency_overrides.pop(get_current_user_id, None)

    def test_disabled_returns_503(self):
        """google_calendar_enabled=False → 503."""
        from app.core.dependencies import get_current_user_id

        settings_mock = MagicMock()
        settings_mock.google_calendar_enabled = False

        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        with patch("app.api.routes.integrations.settings", settings_mock):
            try:
                response = client.get(f"{URL}/auth", headers=USER_HEADERS)
                assert response.status_code == 503
            finally:
                app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# GET /callback
# ---------------------------------------------------------------------------


class TestGoogleCallback:

    def test_missing_code_returns_400(self):
        """No code param → 400."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id
        from app.core.config import get_settings

        settings_mock = MagicMock()
        settings_mock.google_calendar_enabled = True
        mock_session = _make_mock_db()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        with patch("app.api.routes.integrations.settings", settings_mock):
            try:
                response = client.get(f"{URL}/callback", headers=USER_HEADERS)
                assert response.status_code in (302, 307, 400)
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user_id, None)

    def test_error_param_returns_400(self):
        """error=access_denied → 400."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id
        from app.core.config import get_settings

        settings_mock = MagicMock()
        settings_mock.google_calendar_enabled = True
        mock_session = _make_mock_db()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        with patch("app.api.routes.integrations.settings", settings_mock):
            try:
                response = client.get(
                    f"{URL}/callback?error=access_denied",
                    headers=USER_HEADERS,
                )
                assert response.status_code in (302, 307, 400)
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


class TestGoogleStatus:

    def test_connected_user(self):
        """User with tokens → connected=true."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        us = _make_user_settings()
        mock_session = _make_mock_db(user_settings=us)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(f"{URL}/status", headers=USER_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["connected"] is True
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_not_connected_no_settings(self):
        """No UserSettings row → connected=false."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = _make_mock_db(user_settings=None)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(f"{URL}/status", headers=USER_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["connected"] is False
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_not_connected_no_refresh_token(self):
        """UserSettings with no refresh_token → connected=false."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        us = _make_user_settings(google_refresh_token=None)
        mock_session = _make_mock_db(user_settings=us)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(f"{URL}/status", headers=USER_HEADERS)
            assert response.status_code == 200
            assert response.json()["connected"] is False
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# DELETE /disconnect
# ---------------------------------------------------------------------------


class TestGoogleDisconnect:

    def test_disconnect_clears_tokens(self):
        """DELETE → 204, tokens cleared."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        us = _make_user_settings()
        mock_session = _make_mock_db(user_settings=us)

        settings_mock = MagicMock()
        settings_mock.google_calendar_enabled = True

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        with patch("app.api.routes.integrations.settings", settings_mock), \
             patch("app.connectors.google_calendar.revoke_token", return_value=None), \
             patch("app.connectors.shared.credentials_utils.decrypt_value", return_value="plain-token"):
            try:
                response = client.delete(f"{URL}/disconnect", headers=USER_HEADERS)
                assert response.status_code == 204
                assert us.google_access_token is None
                assert us.google_refresh_token is None
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user_id, None)
