"""Tests for POST /api/v1/sources/setup/* and /{id}/regenerate-secret endpoints.

Covers:
- Email setup: success and IMAP failure
- Slack setup: success and invalid token
- Meeting setup: new source (returns secret), update (no secret)
- Regenerate-secret: meeting source works, non-meeting rejected
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-001"}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_source(
    source_id: str = "src-001",
    source_type: str = "email",
    user_id: str = "user-001",
    credentials: dict | None = None,
    is_active: bool = True,
):
    s = MagicMock()
    s.id = source_id
    s.user_id = user_id
    s.source_type = source_type
    s.provider_account_id = "test@example.com" if source_type == "email" else "T12345"
    s.display_name = "test@example.com" if source_type == "email" else "My Workspace"
    s.is_active = is_active
    s.credentials = credentials or {}
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    s.has_credentials = True
    return s


def _make_db(source=None, second_source=None):
    """Return async mock DB where first execute returns source, second returns second_source."""
    mock_db = AsyncMock()

    results = []
    for src in [source, second_source]:
        r = MagicMock()
        r.scalar_one_or_none.return_value = src
        results.append(r)

    if second_source is not None:
        mock_db.execute = AsyncMock(side_effect=results)
    else:
        mock_db.execute = AsyncMock(return_value=results[0])

    mock_db.flush = AsyncMock()

    async def mock_refresh(obj):
        obj.id = getattr(obj, "id", "src-001") or "src-001"
        obj.user_id = "user-001"
        obj.is_active = True
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)
        obj.has_credentials = True

    mock_db.refresh = mock_refresh
    mock_db.add = MagicMock()
    return mock_db


# ---------------------------------------------------------------------------
# Email setup tests
# ---------------------------------------------------------------------------

EMAIL_SETUP_BODY = {
    "email": "test@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "imap_ssl": True,
    "imap_sent_folder": "Sent",
    "app_password": "secret-pass",
    "internal_domains": [],
}


class TestEmailSetup:
    def test_email_setup_creates_source(self):
        """Successful IMAP test → source created with 200 response."""
        mock_db = _make_db(source=None)  # no existing source → new created

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch(
                "app.api.routes.sources.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=(True, "Connected to test@example.com — 5 messages in INBOX"),
            ):
                with patch("app.api.routes.sources.encrypt_credentials", side_effect=lambda d: d):
                    resp = client.post(
                        "/api/v1/sources/setup/email",
                        json=EMAIL_SETUP_BODY,
                        headers=USER_HEADERS,
                    )
            assert resp.status_code == 200
            data = resp.json()
            assert data["source_type"] == "email"
            assert data["user_id"] == "user-001"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_email_setup_fails_on_bad_imap(self):
        """Failed IMAP test → 422."""
        from app.db.deps import get_db

        async def override():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override
        try:
            with patch(
                "app.api.routes.sources.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=(False, "Auth failed: credentials rejected"),
            ):
                resp = client.post(
                    "/api/v1/sources/setup/email",
                    json=EMAIL_SETUP_BODY,
                    headers=USER_HEADERS,
                )
            assert resp.status_code == 422
            assert "IMAP connection failed" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Slack setup tests
# ---------------------------------------------------------------------------

SLACK_SETUP_BODY = {
    "bot_token": "xoxb-valid-token",
    "signing_secret": "signing-secret-abc",
    "slack_user_id": "U12345",
}


class TestSlackSetup:
    def test_slack_setup_creates_source(self):
        """Valid Slack token → source created."""
        mock_db = _make_db(source=None)

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "ok": True,
                "team": "My Workspace",
                "team_id": "T12345",
                "user": "bot-user",
            }

            with patch("app.api.routes.sources.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                with patch("app.api.routes.sources.encrypt_credentials", side_effect=lambda d: d):
                    resp = client.post(
                        "/api/v1/sources/setup/slack",
                        json=SLACK_SETUP_BODY,
                        headers=USER_HEADERS,
                    )
            assert resp.status_code == 200
            data = resp.json()
            assert data["source_type"] == "slack"
            assert data["user_id"] == "user-001"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_slack_setup_fails_on_invalid_token(self):
        """Invalid Slack token (ok=false) → 422."""
        from app.db.deps import get_db

        async def override():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}

            with patch("app.api.routes.sources.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                resp = client.post(
                    "/api/v1/sources/setup/slack",
                    json=SLACK_SETUP_BODY,
                    headers=USER_HEADERS,
                )
            assert resp.status_code == 422
            assert "Slack token validation failed" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Meeting setup tests
# ---------------------------------------------------------------------------

MEETING_SETUP_BODY = {
    "platform": "fireflies",
    "display_name": "Fireflies Integration",
}


class TestMeetingSetup:
    def test_meeting_setup_creates_source_with_webhook_secret(self):
        """New meeting source → webhook_secret returned in response."""
        mock_db = _make_db(source=None)

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch("app.api.routes.sources.encrypt_credentials", side_effect=lambda d: d):
                with patch("app.api.routes.sources.get_settings") as mock_settings:
                    mock_settings.return_value.base_url = "https://api.rippled.ai"
                    mock_settings.return_value.api_prefix = "/api/v1"
                    resp = client.post(
                        "/api/v1/sources/setup/meeting",
                        json=MEETING_SETUP_BODY,
                        headers=USER_HEADERS,
                    )
            assert resp.status_code == 200
            data = resp.json()
            assert "webhook_secret" in data
            assert data["webhook_secret"] is not None
            assert len(data["webhook_secret"]) > 10
            assert "webhook_url" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_meeting_setup_update_does_not_rotate_secret(self):
        """Existing meeting source → webhook_secret is None in response (use regenerate-secret)."""
        existing = _make_source(
            source_type="meeting",
            credentials={"webhook_secret": "existing-secret"},
        )
        mock_db = _make_db(source=existing)

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch(
                "app.api.routes.sources.decrypt_credentials",
                return_value={"webhook_secret": "existing-secret"},
            ):
                with patch("app.api.routes.sources.encrypt_credentials", side_effect=lambda d: d):
                    with patch("app.api.routes.sources.get_settings") as mock_settings:
                        mock_settings.return_value.base_url = "https://api.rippled.ai"
                        mock_settings.return_value.api_prefix = "/api/v1"
                        resp = client.post(
                            "/api/v1/sources/setup/meeting",
                            json=MEETING_SETUP_BODY,
                            headers=USER_HEADERS,
                        )
            assert resp.status_code == 200
            data = resp.json()
            assert data["webhook_secret"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Regenerate secret tests
# ---------------------------------------------------------------------------

class TestRegenerateSecret:
    def test_regenerate_secret_works(self):
        """Meeting source → new webhook_secret returned."""
        existing = _make_source(source_type="meeting", credentials={"webhook_secret": "old-secret"})
        mock_db = _make_db(source=existing)

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            with patch(
                "app.api.routes.sources.decrypt_credentials",
                return_value={"webhook_secret": "old-secret"},
            ):
                with patch("app.api.routes.sources.encrypt_credentials", side_effect=lambda d: d):
                    resp = client.post(
                        "/api/v1/sources/src-001/regenerate-secret",
                        headers=USER_HEADERS,
                    )
            assert resp.status_code == 200
            data = resp.json()
            assert "webhook_secret" in data
            assert data["webhook_secret"] != "old-secret"
            assert len(data["webhook_secret"]) > 10
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_regenerate_secret_rejects_non_meeting(self):
        """Email source → 422 when trying to regenerate secret."""
        existing = _make_source(source_type="email")
        mock_db = _make_db(source=existing)

        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.post(
                "/api/v1/sources/src-001/regenerate-secret",
                headers=USER_HEADERS,
            )
            assert resp.status_code == 422
            assert "meeting" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)
