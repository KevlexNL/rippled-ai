"""Integration tests for counterparty_name field on commitments."""
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
                    {"id": test_user_id, "email": f"test-cp-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())


class TestCounterpartyName:
    def test_create_commitment_with_counterparty_name(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/commitments",
            json={
                "title": "Counterparty test commitment",
                "counterparty_name": "Acme Corp",
            },
            headers=test_user_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["counterparty_name"] == "Acme Corp"

    def test_create_commitment_without_counterparty_name(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/commitments",
            json={"title": "No counterparty commitment"},
            headers=test_user_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["counterparty_name"] is None

    def test_read_commitment_includes_counterparty_name(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/commitments",
            json={
                "title": "Read counterparty test",
                "counterparty_name": "Widget Inc",
            },
            headers=test_user_headers,
        )
        cid = resp.json()["id"]
        get_resp = client.get(f"/api/v1/commitments/{cid}", headers=test_user_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["counterparty_name"] == "Widget Inc"
