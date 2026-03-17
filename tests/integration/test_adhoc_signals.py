"""Integration tests for ad-hoc signal endpoints (WO-RIPPLED-ADHOC-SIGNAL).

Covers:
  POST /admin/adhoc-signals          — intake
  POST /admin/adhoc-signals/{id}/check-match — match check
  GET  /admin/adhoc-signals          — list pending
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.usefixtures("cleanup_test_user")

_TEST_ADMIN_KEY = "test-admin-key-adhoc"


@pytest.fixture(scope="module")
def admin_headers() -> dict:
    return {"X-Admin-Key": _TEST_ADMIN_KEY}


@pytest.fixture(scope="module")
def client(test_engine):
    """TestClient with admin_secret_key guaranteed to match _TEST_ADMIN_KEY."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.deps import get_db
    from app.core.config import get_settings
    from app.main import app

    settings = get_settings()
    original_key = settings.admin_secret_key
    settings.admin_secret_key = _TEST_ADMIN_KEY

    AsyncTestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with AsyncTestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    settings.admin_secret_key = original_key


@pytest.fixture(scope="module")
def _ensure_user(client, test_user_id):
    """Ensure test user exists in the DB (separate engine to avoid loop conflicts)."""
    from tests.integration.conftest import _make_async_url, _get_db_url

    async def _seed():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text, bindparam
        from sqlalchemy.dialects.postgresql import UUID as PGUUID

        engine = create_async_engine(
            _make_async_url(_get_db_url()),
            connect_args={"statement_cache_size": 0},
        )
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT DO NOTHING").bindparams(
                        bindparam("id", type_=PGUUID(as_uuid=False)),
                    ),
                    {"id": test_user_id, "email": f"adhoc-test-{test_user_id[:8]}@rippled.ai"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())


# ---------------------------------------------------------------------------
# POST /admin/adhoc-signals — intake
# ---------------------------------------------------------------------------

class TestAdhocSignalIntake:
    def test_create_adhoc_signal(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """Intake endpoint creates an adhoc_signal with match_status=pending."""
        resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "committed to sending Matt the RevEngine report by Friday",
                "source": "telegram",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["match_status"] == "pending"
        assert data["raw_text"] == "committed to sending Matt the RevEngine report by Friday"
        assert data["source"] == "telegram"
        assert "id" in data

    def test_create_adhoc_signal_default_source(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """Source defaults to 'telegram' if not provided."""
        resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "will review the Q2 budget doc tonight",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["source"] == "telegram"

    def test_create_adhoc_signal_missing_text(self, client: TestClient, admin_headers: dict, test_user_id: str):
        """raw_text is required."""
        resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={"user_id": test_user_id},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_create_adhoc_signal_no_admin_key(self, client: TestClient, test_user_id: str):
        """Endpoint requires admin auth."""
        resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "some commitment",
            },
        )
        assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# GET /admin/adhoc-signals — list
# ---------------------------------------------------------------------------

class TestAdhocSignalList:
    def test_list_pending(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """List returns adhoc signals for user."""
        client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "need to file the tax extension by April 15",
            },
            headers=admin_headers,
        )
        resp = client.get(
            f"/api/v1/admin/adhoc-signals?user_id={test_user_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert all(d["user_id"] == test_user_id for d in data)

    def test_list_filter_status(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """Can filter by match_status."""
        resp = client.get(
            f"/api/v1/admin/adhoc-signals?user_id={test_user_id}&match_status=pending",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["match_status"] == "pending" for d in data)


# ---------------------------------------------------------------------------
# POST /admin/adhoc-signals/{id}/check-match — match check
# ---------------------------------------------------------------------------

class TestAdhocSignalMatchCheck:
    def test_check_match_not_found(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """Match check with no matching commitments returns not_found."""
        create_resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "unique xyz commitment that will never match anything 12345",
            },
            headers=admin_headers,
        )
        signal_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/admin/adhoc-signals/{signal_id}/check-match",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_status"] == "not_found"
        assert data["was_found"] is False
        assert data["match_checked_at"] is not None

    def test_check_match_nonexistent_signal(self, client: TestClient, admin_headers: dict):
        """404 for nonexistent signal ID."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/admin/adhoc-signals/{fake_id}/check-match",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_check_match_already_checked(self, client: TestClient, admin_headers: dict, test_user_id: str, _ensure_user):
        """Re-running match check on already-checked signal still works (idempotent)."""
        create_resp = client.post(
            "/api/v1/admin/adhoc-signals",
            json={
                "user_id": test_user_id,
                "raw_text": "another unique commitment that wont match 67890",
            },
            headers=admin_headers,
        )
        signal_id = create_resp.json()["id"]

        client.post(
            f"/api/v1/admin/adhoc-signals/{signal_id}/check-match",
            headers=admin_headers,
        )
        resp = client.post(
            f"/api/v1/admin/adhoc-signals/{signal_id}/check-match",
            headers=admin_headers,
        )
        assert resp.status_code == 200
