"""Integration tests for sources API against the real Supabase DB.

These tests:
- Use a real DB connection (no mocks for DB layer)
- Mock only the external IMAP connection (no real email credentials needed)
- Verify that DB writes actually persist, not just that endpoints return 200
- Clean up all test data in teardown (via conftest.py module fixture)

Run with:
    make test-integration
or:
    pytest tests/integration/ -v
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

# Ensure .env is loaded (conftest loads it too, but be defensive for direct pytest invocations)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMAIL_SETUP_BODY = {
    "email": "integration-test@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "imap_ssl": True,
    "imap_sent_folder": "Sent",
    "app_password": "test-app-password",
    "internal_domains": [],
}

IMAP_SUCCESS = (True, "Connected to integration-test@example.com — 42 messages in INBOX")


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
                    "SELECT id, source_type, display_name, is_active "
                    "FROM sources WHERE user_id = :uid"
                ).bindparams(bindparam("uid", type_=PGUUID(as_uuid=False))),
                {"uid": user_id},
            )
            return [dict(row._mapping) for row in result]
    finally:
        await engine.dispose()


async def _query_user(user_id: str) -> dict | None:
    """Directly query the DB for the test user row."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text, bindparam
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    engine = create_async_engine(_db_url(), connect_args={"statement_cache_size": 0})
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id, email FROM users WHERE id = :uid").bindparams(
                    bindparam("uid", type_=PGUUID(as_uuid=False))
                ),
                {"uid": user_id},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSourcesAPIIntegration:
    """Full-stack integration tests against real DB.

    Tests run in definition order — each builds on the previous state,
    simulating the real onboarding flow.
    """

    def test_01_onboarding_status_initially_empty(self, client, test_user_headers):
        """First call auto-provisions user row; has_sources must be false."""
        resp = client.get("/api/v1/sources/onboarding-status", headers=test_user_headers)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["has_sources"] is False
        assert data["sources"] == []

    def test_02_user_row_was_provisioned(self, test_user_id):
        """After onboarding-status, the user row should exist in the DB."""
        user = asyncio.run(_query_user(test_user_id))

        assert user is not None, "User row was not created in the DB"
        assert str(user["id"]) == test_user_id

    def test_03_setup_email_creates_source(self, client, test_user_headers):
        """POST /setup/email with mocked IMAP → 200, source in response."""
        with patch(
            "app.api.routes.sources.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=IMAP_SUCCESS,
        ):
            resp = client.post(
                "/api/v1/sources/setup/email",
                json=EMAIL_SETUP_BODY,
                headers=test_user_headers,
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source_type"] == "email"
        assert data["is_active"] is True
        assert data["display_name"] == EMAIL_SETUP_BODY["email"]
        assert data["has_credentials"] is True

    def test_04_db_write_actually_persisted(self, test_user_id):
        """Verify the source row exists in the real DB — not just the API response."""
        sources = asyncio.run(_query_sources(test_user_id))

        assert len(sources) == 1, f"Expected 1 source in DB, found {len(sources)}"
        source = sources[0]
        assert str(source["source_type"]) == "email"
        assert source["is_active"] is True
        assert source["display_name"] == EMAIL_SETUP_BODY["email"]

    def test_05_onboarding_status_shows_has_sources(self, client, test_user_headers):
        """After email setup, onboarding-status must return has_sources=true."""
        resp = client.get("/api/v1/sources/onboarding-status", headers=test_user_headers)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["has_sources"] is True
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source_type"] == "email"
        assert data["sources"][0]["is_active"] is True

    def test_06_setup_email_is_idempotent(self, client, test_user_headers):
        """Calling setup/email again updates the source, does not create a duplicate."""
        updated_body = {**EMAIL_SETUP_BODY, "email": "updated@example.com"}

        with patch(
            "app.api.routes.sources.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=(True, "Connected to updated@example.com — 10 messages"),
        ):
            resp = client.post(
                "/api/v1/sources/setup/email",
                json=updated_body,
                headers=test_user_headers,
            )

        assert resp.status_code == 200, resp.text

        sources = asyncio.run(_query_sources(test_user_id := resp.json()["user_id"]))
        email_sources = [s for s in sources if str(s["source_type"]) == "email"]
        assert len(email_sources) == 1, "Upsert should not create duplicate rows"
        assert email_sources[0]["display_name"] == "updated@example.com"
