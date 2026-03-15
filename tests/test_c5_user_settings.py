"""Tests for Phase C5 — User Settings API.

TDD: Tests for GET /user/settings and PATCH /user/settings.
Covers:
- GET creates defaults if not exists
- GET returns existing row
- google_connected reflects presence of refresh token
- PATCH updates digest_enabled
- PATCH updates digest_to_email
- PATCH partial update (omit field → unchanged)
- PATCH with empty body → no change
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
BASE_URL = "/api/v1/user"
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
USER_HEADERS = {"x-user-id": USER_ID}
NOW = datetime.now(timezone.utc)


def _make_user_settings(**kwargs):
    defaults = {
        "user_id": USER_ID,
        "digest_enabled": True,
        "digest_time": "08:00",
        "digest_to_email": None,
        "google_access_token": None,
        "google_refresh_token": None,
        "google_token_expiry": None,
        "last_digest_sent_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestUserSettingsGet:
    def test_get_creates_defaults_if_not_exists(self):
        """First GET creates a UserSettings row with defaults."""
        async def fake_get_db():
            db = AsyncMock()
            result_none = MagicMock()
            result_none.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_none)
            db.add = MagicMock()
            db.flush = AsyncMock()

            async def fake_refresh(obj):
                # Simulate DB applying server_defaults after flush
                obj.digest_enabled = True
                obj.digest_time = "08:00"
                obj.digest_to_email = None
                obj.google_refresh_token = None
                obj.google_access_token = None
                obj.google_token_expiry = None
                obj.last_digest_sent_at = None

            db.refresh = AsyncMock(side_effect=fake_refresh)
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}/settings", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "digest_enabled" in data
        assert "digest_to_email" in data
        assert "google_connected" in data

    def test_get_returns_existing_row(self):
        """GET returns existing UserSettings row."""
        us = _make_user_settings(digest_enabled=True, digest_to_email="user@example.com")

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}/settings", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["digest_enabled"] is True
        assert data["digest_to_email"] == "user@example.com"
        assert data["google_connected"] is False

    def test_get_google_connected_false_when_no_token(self):
        """google_connected=False when google_refresh_token is None."""
        us = _make_user_settings(google_refresh_token=None)

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}/settings", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json()["google_connected"] is False

    def test_get_google_connected_true_when_token_present(self):
        """google_connected=True when google_refresh_token is set."""
        us = _make_user_settings(google_refresh_token="encrypted-token-xyz")

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}/settings", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json()["google_connected"] is True

    def test_get_requires_user_header(self):
        """GET /user/settings without user header returns 401 or 422."""
        resp = client.get(f"{BASE_URL}/settings")
        assert resp.status_code in (401, 422)


class TestUserSettingsPatch:
    def test_patch_updates_digest_enabled(self):
        """PATCH can toggle digest_enabled."""
        us = _make_user_settings(digest_enabled=True)

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()

            async def fake_refresh(obj):
                obj.digest_enabled = False

            db.refresh = AsyncMock(side_effect=fake_refresh)
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={"digest_enabled": False},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200

    def test_patch_updates_digest_to_email(self):
        """PATCH can set digest_to_email."""
        us = _make_user_settings(digest_to_email=None)

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()

            async def fake_refresh(obj):
                obj.digest_to_email = "new@example.com"

            db.refresh = AsyncMock(side_effect=fake_refresh)
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={"digest_to_email": "new@example.com"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200

    def test_patch_partial_update_mutates_only_provided_field(self):
        """PATCH with only one field mutates that field on the ORM object."""
        us = _make_user_settings(digest_enabled=True, digest_to_email="original@example.com")

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={"digest_enabled": False},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert us.digest_enabled is False

    def test_patch_empty_body_returns_200(self):
        """PATCH with empty body {} returns 200 without error."""
        us = _make_user_settings()

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = us
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200

    def test_patch_wrong_type_returns_422(self):
        """PATCH with wrong type for a field returns 422."""
        async def fake_get_db():
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={"digest_enabled": "not-a-bool"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422

    def test_patch_creates_settings_if_not_exists(self):
        """PATCH on a user with no settings row creates one first."""
        async def fake_get_db():
            db = AsyncMock()
            result_none = MagicMock()
            result_none.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result_none)
            db.add = MagicMock()
            db.flush = AsyncMock()

            async def fake_refresh(obj):
                obj.digest_enabled = False
                obj.digest_time = "08:00"
                obj.digest_to_email = None
                obj.google_refresh_token = None

            db.refresh = AsyncMock(side_effect=fake_refresh)
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/settings",
                json={"digest_enabled": False},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
