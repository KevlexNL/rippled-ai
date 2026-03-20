"""Tests for GET /admin/review/audit-sample endpoint.

Verifies the audit-sample endpoint returns detection_audit rows
filtered by prompt_version.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"
HEADERS = {"X-User-ID": ADMIN_USER_ID}
ENDPOINT = "/api/v1/admin/review/audit-sample"
NOW = datetime.now(timezone.utc)


def _uid():
    return str(uuid.uuid4())


def _make_audit_row(prompt_version="ongoing-v4", **kwargs):
    defaults = {
        "detection_audit_id": _uid(),
        "source_item_id": _uid(),
        "content": "I'll send the report by Friday",
        "sender_name": "Alice",
        "parsed_result": {"is_commitment": True, "confidence": 0.9},
        "prompt_version": prompt_version,
        "model": "gpt-4.1-mini",
        "created_at": NOW,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_audit_sample_requires_auth():
    resp = client.get(ENDPOINT, params={"prompt_version": "v1"})
    assert resp.status_code in (401, 403, 422)


def test_audit_sample_rejects_non_admin():
    resp = client.get(
        ENDPOINT,
        params={"prompt_version": "v1"},
        headers={"X-User-ID": _uid()},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Missing required param
# ---------------------------------------------------------------------------


def test_audit_sample_requires_prompt_version():
    resp = client.get(ENDPOINT, headers=HEADERS)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@patch("app.api.routes.admin_review.get_db")
def test_audit_sample_returns_rows(mock_get_db):
    rows = [_make_audit_row(), _make_audit_row(), _make_audit_row()]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    async def override_db():
        yield mock_db

    app.dependency_overrides[mock_get_db] = override_db

    # Also need to override the actual get_db
    from app.db.deps import get_db

    app.dependency_overrides[get_db] = override_db

    try:
        resp = client.get(
            ENDPOINT,
            params={"prompt_version": "ongoing-v4"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        for item in data:
            assert "detection_audit_id" in item
            assert "content" in item
            assert "prompt_version" in item
            assert item["prompt_version"] == "ongoing-v4"
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.admin_review.get_db")
def test_audit_sample_respects_limit(mock_get_db):
    rows = [_make_audit_row()]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    async def override_db():
        yield mock_db

    from app.db.deps import get_db

    app.dependency_overrides[get_db] = override_db

    try:
        resp = client.get(
            ENDPOINT,
            params={"prompt_version": "ongoing-v4", "limit": 1},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.admin_review.get_db")
def test_audit_sample_empty_result(mock_get_db):
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    async def override_db():
        yield mock_db

    from app.db.deps import get_db

    app.dependency_overrides[get_db] = override_db

    try:
        resp = client.get(
            ENDPOINT,
            params={"prompt_version": "nonexistent-v99"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()
