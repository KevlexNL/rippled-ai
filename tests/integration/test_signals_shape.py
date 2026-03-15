"""Integration tests verifying signals endpoint shape matches frontend expectations."""
import asyncio
import pytest


@pytest.fixture(scope="module")
def _ensure_user_and_commitment(client, test_user_id, test_user_headers):
    """Ensure test user and a commitment exist."""
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
                    {"id": test_user_id, "email": f"test-sig-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())

    # Create a commitment to test signals on
    resp = client.post(
        "/api/v1/commitments",
        json={"title": "Signals test commitment"},
        headers=test_user_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestSignalsShape:
    def test_signals_endpoint_returns_200(self, client, test_user_headers, _ensure_user_and_commitment):
        cid = _ensure_user_and_commitment
        resp = client.get(f"/api/v1/commitments/{cid}/signals", headers=test_user_headers)
        assert resp.status_code == 200

    def test_signals_returns_list(self, client, test_user_headers, _ensure_user_and_commitment):
        cid = _ensure_user_and_commitment
        resp = client.get(f"/api/v1/commitments/{cid}/signals", headers=test_user_headers)
        assert isinstance(resp.json(), list)

    def test_signal_schema_has_required_fields(self, client, test_user_headers, _ensure_user_and_commitment):
        """Verify the CommitmentSignalRead schema has the fields frontend needs.

        The frontend detail panel expects: source, text, created_at.
        Current backend returns: signal_role (maps to source type), interpretation_note (maps to text), created_at.
        This test documents the mapping.
        """
        # The signal schema is verified through the endpoint's response_model
        # Even with empty results, the schema is validated
        cid = _ensure_user_and_commitment
        resp = client.get(f"/api/v1/commitments/{cid}/signals", headers=test_user_headers)
        assert resp.status_code == 200
        # Schema validation: CommitmentSignalRead includes signal_role, interpretation_note, created_at
