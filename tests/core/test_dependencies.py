"""Tests for app.core.dependencies — user ID resolution."""
from __future__ import annotations

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user_id, get_user_id_for_redirect


# ---------------------------------------------------------------------------
# Fixtures — lightweight FastAPI app wired to each dependency
# ---------------------------------------------------------------------------

def _make_app():
    app = FastAPI()

    @app.get("/header-only")
    async def header_only(uid: str = Depends(get_current_user_id)):
        return {"user_id": uid}

    @app.get("/flexible")
    async def flexible(uid: str = Depends(get_user_id_for_redirect)):
        return {"user_id": uid}

    return app


app = _make_app()
client = TestClient(app)


# ---------------------------------------------------------------------------
# get_current_user_id (header-only)
# ---------------------------------------------------------------------------

class TestGetCurrentUserId:

    def test_returns_user_id_from_header(self):
        resp = client.get("/header-only", headers={"X-User-ID": "user-abc"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-abc"

    def test_missing_header_returns_422(self):
        resp = client.get("/header-only")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# get_user_id_for_redirect (query param or header)
# ---------------------------------------------------------------------------

class TestGetUserIdForRedirect:

    def test_query_param_accepted(self):
        resp = client.get("/flexible?user_id=user-from-query")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-from-query"

    def test_header_accepted(self):
        resp = client.get("/flexible", headers={"X-User-ID": "user-from-header"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-from-header"

    def test_query_param_takes_precedence_over_header(self):
        resp = client.get(
            "/flexible?user_id=query-wins",
            headers={"X-User-ID": "header-loses"},
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "query-wins"

    def test_neither_provided_returns_400(self):
        resp = client.get("/flexible")
        assert resp.status_code == 400
        assert "user_id" in resp.json()["detail"].lower()
