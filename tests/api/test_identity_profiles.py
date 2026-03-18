"""Tests for identity profile API routes.

Tests verify:
- GET /api/v1/identity/profile — list profiles for current user
- POST /api/v1/identity/manual — add a new identity manually
- DELETE /api/v1/identity/{id} — remove an identity
- GET /api/v1/identity/status — check if user has confirmed identities
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.models.orm import UserIdentityProfile

client = TestClient(app)
URL_PREFIX = "/api/v1/identity"
USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"
USER_HEADERS = {"X-User-ID": USER_ID}


def _make_profile(
    id: str = "prof-001",
    identity_type: str = "full_name",
    identity_value: str = "Kevin Beeftink",
    source: str = "seed_detected",
    confirmed: bool = False,
) -> UserIdentityProfile:
    p = UserIdentityProfile()
    p.id = id
    p.user_id = USER_ID
    p.identity_type = identity_type
    p.identity_value = identity_value
    p.source = source
    p.confirmed = confirmed
    p.created_at = datetime.now(timezone.utc)
    return p


class _FakeScalars:
    """Supports both iteration and .all() for mock DB results."""
    def __init__(self, items):
        self._items = items
    def all(self):
        return self._items
    def __iter__(self):
        return iter(self._items)


def _make_execute_result(items):
    """Create a mock result that supports .scalars() and .scalar_one_or_none()."""
    result = MagicMock()
    result.scalars.return_value = _FakeScalars(items)
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


class TestGetProfile:
    def test_returns_profiles_for_user(self):
        profiles = [
            _make_profile(id="p1", identity_value="Kevin Beeftink"),
            _make_profile(id="p2", identity_type="email", identity_value="kevin@kevlex.digital"),
        ]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result(profiles))

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(f"{URL_PREFIX}/profile", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["identity_value"] == "Kevin Beeftink"
            assert data[1]["identity_type"] == "email"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_missing_user_id_returns_422(self):
        resp = client.get(f"{URL_PREFIX}/profile")
        assert resp.status_code == 422


class TestManualAdd:
    def test_add_manual_identity(self):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        async def mock_refresh(obj):
            obj.id = "new-prof-001"
            obj.created_at = datetime.now(timezone.utc)

        mock_db.refresh = mock_refresh

        def mock_add(obj):
            obj.id = "new-prof-001"
            obj.created_at = datetime.now(timezone.utc)

        mock_db.add = mock_add

        # For backfill query (no unresolved commitments)
        mock_db.execute = AsyncMock(return_value=_make_execute_result([]))

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.post(
                f"{URL_PREFIX}/manual",
                json={"identity_type": "alias", "identity_value": "KB"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["identity_type"] == "alias"
            assert data["identity_value"] == "KB"
            assert data["source"] == "manual"
            assert data["confirmed"] is True
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_invalid_type_returns_422(self):
        mock_db = AsyncMock()
        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.post(
                f"{URL_PREFIX}/manual",
                json={"identity_type": "invalid_type", "identity_value": "test"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestDeleteProfile:
    def test_delete_existing_profile(self):
        profile = _make_profile(id="p-del")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result([profile]))
        mock_db.delete = AsyncMock()

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.delete(f"{URL_PREFIX}/p-del", headers=USER_HEADERS)
            assert resp.status_code == 204
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_delete_nonexistent_returns_404(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.delete(f"{URL_PREFIX}/nonexistent", headers=USER_HEADERS)
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestIdentityStatus:
    def test_returns_has_confirmed_true(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = 2
        mock_db.execute = AsyncMock(return_value=result)

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(f"{URL_PREFIX}/status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_confirmed_identities"] is True
            assert data["confirmed_count"] == 2
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_returns_has_confirmed_false_when_zero(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = 0
        mock_db.execute = AsyncMock(return_value=result)

        from app.db.deps import get_db
        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(f"{URL_PREFIX}/status", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_confirmed_identities"] is False
        finally:
            app.dependency_overrides.pop(get_db, None)
