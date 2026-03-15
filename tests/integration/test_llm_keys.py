"""Integration tests for LLM key storage in user settings."""
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
                    {"id": test_user_id, "email": f"test-llm-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())


class TestLLMKeys:
    def test_settings_includes_llm_key_status(self, client, test_user_headers, _ensure_user):
        resp = client.get("/api/v1/user/settings", headers=test_user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "anthropic_key_connected" in data
        assert "openai_key_connected" in data

    def test_set_anthropic_key(self, client, test_user_headers, _ensure_user):
        resp = client.patch(
            "/api/v1/user/settings",
            json={"anthropic_api_key": "sk-ant-test-key-1234567890"},
            headers=test_user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["anthropic_key_connected"] is True
        # Must NOT return the raw key
        assert "sk-ant-test" not in str(data)

    def test_set_openai_key(self, client, test_user_headers, _ensure_user):
        resp = client.patch(
            "/api/v1/user/settings",
            json={"openai_api_key": "sk-openai-test-key-9876543210"},
            headers=test_user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["openai_key_connected"] is True

    def test_clear_anthropic_key(self, client, test_user_headers, _ensure_user):
        # Set first
        client.patch(
            "/api/v1/user/settings",
            json={"anthropic_api_key": "sk-ant-key"},
            headers=test_user_headers,
        )
        # Clear by sending empty string
        resp = client.patch(
            "/api/v1/user/settings",
            json={"anthropic_api_key": ""},
            headers=test_user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["anthropic_key_connected"] is False
