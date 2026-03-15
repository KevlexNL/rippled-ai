"""Integration tests for GET /surface/best-next-moves endpoint."""
import uuid

import pytest

# Module-level fixtures from conftest: client, test_user_id, test_user_headers


@pytest.fixture(scope="module")
def _seed_commitments(client, test_user_id, test_user_headers):
    """Seed commitments with various surfacing states for best-next-moves testing."""
    # We need a user row first (FK constraint)
    from tests.integration.conftest import _make_async_url, _get_db_url
    import asyncio

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
                # Insert test user
                await conn.execute(
                    text("INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT DO NOTHING").bindparams(
                        bindparam("id", type_=PGUUID(as_uuid=False)),
                    ),
                    {"id": test_user_id, "email": f"test-{test_user_id[:8]}@test.com"},
                )
        finally:
            await engine.dispose()

    asyncio.run(_seed())

    # Create commitments via API — shortlist items (quick win candidates)
    ids = []
    for i in range(3):
        resp = client.post(
            "/api/v1/commitments",
            json={
                "title": f"Quick win item {i}",
                "commitment_type": "confirm",
                "confidence_commitment": "0.850",
                "confidence_actionability": "0.800",
            },
            headers=test_user_headers,
        )
        assert resp.status_code == 201, resp.text
        cid = resp.json()["id"]
        ids.append(cid)
        # Transition to active
        client.patch(
            f"/api/v1/commitments/{cid}",
            json={"lifecycle_state": "active"},
            headers=test_user_headers,
        )

    # Create a main-surfaced item (will land in "needs focus")
    resp = client.post(
        "/api/v1/commitments",
        json={
            "title": "Needs focus item",
            "commitment_type": "deliver",
            "confidence_commitment": "0.900",
            "confidence_actionability": "0.900",
        },
        headers=test_user_headers,
    )
    assert resp.status_code == 201
    nf_id = resp.json()["id"]
    ids.append(nf_id)
    client.patch(
        f"/api/v1/commitments/{nf_id}",
        json={"lifecycle_state": "active"},
        headers=test_user_headers,
    )

    return ids


class TestBestNextMoves:
    def test_endpoint_returns_200(self, client, test_user_headers, _seed_commitments):
        resp = client.get("/api/v1/surface/best-next-moves", headers=test_user_headers)
        assert resp.status_code == 200

    def test_response_has_groups_key(self, client, test_user_headers, _seed_commitments):
        resp = client.get("/api/v1/surface/best-next-moves", headers=test_user_headers)
        data = resp.json()
        assert "groups" in data

    def test_groups_have_correct_labels(self, client, test_user_headers, _seed_commitments):
        resp = client.get("/api/v1/surface/best-next-moves", headers=test_user_headers)
        data = resp.json()
        labels = {g["label"] for g in data["groups"]}
        assert labels <= {"Quick wins", "Likely blockers", "Needs focus"}

    def test_group_items_are_commitment_shaped(self, client, test_user_headers, _seed_commitments):
        resp = client.get("/api/v1/surface/best-next-moves", headers=test_user_headers)
        data = resp.json()
        for group in data["groups"]:
            assert isinstance(group["items"], list)
            for item in group["items"]:
                assert "id" in item
                assert "title" in item

    def test_max_5_items_total(self, client, test_user_headers, _seed_commitments):
        resp = client.get("/api/v1/surface/best-next-moves", headers=test_user_headers)
        data = resp.json()
        total = sum(len(g["items"]) for g in data["groups"])
        assert total <= 5
