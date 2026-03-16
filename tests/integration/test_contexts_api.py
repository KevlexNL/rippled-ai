"""Integration tests for the /contexts endpoints."""
import asyncio
import pytest


@pytest.fixture(scope="module")
def _ensure_user(client, test_user_id, test_user_headers):
    """Ensure test user exists in the DB."""
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
                    {"id": test_user_id, "email": f"test-ctx-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())


class TestCreateContext:
    def test_create_context_returns_201(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/contexts",
            json={"name": "Test Context Alpha", "summary": "A test context"},
            headers=test_user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Context Alpha"
        assert data["summary"] == "A test context"
        assert data["commitment_count"] == 0
        assert "id" in data
        assert "created_at" in data

    def test_create_context_without_summary(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/contexts",
            json={"name": "No Summary Context"},
            headers=test_user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["summary"] is None

    def test_create_context_missing_name_returns_422(self, client, test_user_headers, _ensure_user):
        resp = client.post(
            "/api/v1/contexts",
            json={"summary": "missing name"},
            headers=test_user_headers,
        )
        assert resp.status_code == 422


class TestListContexts:
    def test_list_contexts_returns_seeded(self, client, test_user_headers, _ensure_user):
        # Seed two contexts
        client.post(
            "/api/v1/contexts",
            json={"name": "List Test A"},
            headers=test_user_headers,
        )
        client.post(
            "/api/v1/contexts",
            json={"name": "List Test B"},
            headers=test_user_headers,
        )

        resp = client.get("/api/v1/contexts", headers=test_user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [c["name"] for c in data]
        assert "List Test A" in names
        assert "List Test B" in names

    def test_list_contexts_commitment_count(self, client, test_user_headers, _ensure_user):
        # Create a context
        ctx_resp = client.post(
            "/api/v1/contexts",
            json={"name": "Count Test Context"},
            headers=test_user_headers,
        )
        ctx_id = ctx_resp.json()["id"]

        # Create a commitment linked to that context
        commit_resp = client.post(
            "/api/v1/commitments",
            json={"title": "Test commitment in context", "context_id": ctx_id},
            headers=test_user_headers,
        )
        assert commit_resp.status_code == 201

        # List contexts and check count
        resp = client.get("/api/v1/contexts", headers=test_user_headers)
        data = resp.json()
        ctx_data = next((c for c in data if c["id"] == ctx_id), None)
        assert ctx_data is not None
        assert ctx_data["commitment_count"] >= 1


class TestContextCommitments:
    def test_get_context_commitments(self, client, test_user_headers, _ensure_user):
        # Create context
        ctx_resp = client.post(
            "/api/v1/contexts",
            json={"name": "Commitments List Context"},
            headers=test_user_headers,
        )
        ctx_id = ctx_resp.json()["id"]

        # Create commitments
        client.post(
            "/api/v1/commitments",
            json={"title": "Ctx commit 1", "context_id": ctx_id},
            headers=test_user_headers,
        )
        client.post(
            "/api/v1/commitments",
            json={"title": "Ctx commit 2", "context_id": ctx_id},
            headers=test_user_headers,
        )

        resp = client.get(f"/api/v1/contexts/{ctx_id}/commitments", headers=test_user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        titles = [c["title"] for c in data]
        assert "Ctx commit 1" in titles
        assert "Ctx commit 2" in titles

    def test_get_context_commitments_404_for_nonexistent(self, client, test_user_headers, _ensure_user):
        resp = client.get(
            "/api/v1/contexts/00000000-0000-0000-0000-000000000000/commitments",
            headers=test_user_headers,
        )
        assert resp.status_code == 404


class TestCommitmentContextAssignment:
    def test_patch_commitment_context_id(self, client, test_user_headers, _ensure_user):
        # Create context
        ctx_resp = client.post(
            "/api/v1/contexts",
            json={"name": "Patch Test Context"},
            headers=test_user_headers,
        )
        ctx_id = ctx_resp.json()["id"]

        # Create commitment without context
        commit_resp = client.post(
            "/api/v1/commitments",
            json={"title": "Orphan commitment"},
            headers=test_user_headers,
        )
        commit_id = commit_resp.json()["id"]

        # Assign context via PATCH
        patch_resp = client.patch(
            f"/api/v1/commitments/{commit_id}",
            json={"context_id": ctx_id},
            headers=test_user_headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["context_id"] == ctx_id

    def test_create_commitment_with_context_id(self, client, test_user_headers, _ensure_user):
        ctx_resp = client.post(
            "/api/v1/contexts",
            json={"name": "Create With Context"},
            headers=test_user_headers,
        )
        ctx_id = ctx_resp.json()["id"]

        commit_resp = client.post(
            "/api/v1/commitments",
            json={"title": "Born with context", "context_id": ctx_id},
            headers=test_user_headers,
        )
        assert commit_resp.status_code == 201
        assert commit_resp.json()["context_id"] == ctx_id
