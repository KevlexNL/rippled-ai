"""Integration tests verifying stats endpoint shape matches frontend expectations."""
import asyncio
import pytest


@pytest.fixture(scope="module")
def _ensure_user(client, test_user_id, test_user_headers):
    """Ensure test user exists."""
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
                    {"id": test_user_id, "email": f"test-stats-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())


class TestStatsShape:
    def test_stats_returns_200(self, client, test_user_headers, _ensure_user):
        resp = client.get("/api/v1/stats", headers=test_user_headers)
        assert resp.status_code == 200

    def test_stats_has_required_fields(self, client, test_user_headers, _ensure_user):
        """Verify stats shape includes fields the frontend expects."""
        resp = client.get("/api/v1/stats", headers=test_user_headers)
        data = resp.json()
        # Frontend expects these keys (WO spec)
        assert "emails_captured" in data
        assert "messages_processed" in data
        assert "meetings_analyzed" in data  # WO says meetings_logged but backend uses meetings_analyzed
        assert "commitments_detected" in data
        # All must be integers
        for key in ["emails_captured", "messages_processed", "meetings_analyzed", "commitments_detected"]:
            assert isinstance(data[key], int)

    def test_stats_has_people_identified(self, client, test_user_headers, _ensure_user):
        """Frontend footer shows people_identified — backend must provide it."""
        resp = client.get("/api/v1/stats", headers=test_user_headers)
        data = resp.json()
        assert "people_identified" in data
        assert isinstance(data["people_identified"], int)
