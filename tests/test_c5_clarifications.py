"""Tests for Phase C5 — Clarifications API.

TDD: Tests for GET /clarifications and POST /clarifications/{id}/respond.
Covers:
- GET returns open (unresolved) clarifications for commitment_id
- GET returns empty list when all clarifications are resolved
- GET requires commitment_id query param
- POST respond sets resolved_at
- POST respond transitions commitment to active
- POST respond writes LifecycleTransition with trigger_reason='clarification_answered'
- POST respond 404 if clarification not found
- POST respond 409 if already resolved
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
BASE_URL = "/api/v1/clarifications"
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
USER_HEADERS = {"x-user-id": USER_ID}
NOW = datetime.now(timezone.utc)


def _uid():
    return str(uuid.uuid4())


def _make_commitment_mock(cid=None, **kwargs):
    defaults = {
        "id": cid or _uid(),
        "user_id": USER_ID,
        "lifecycle_state": "needs_clarification",
        "state_changed_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_clarification(clar_id=None, commitment_id=None, resolved=False, **kwargs):
    defaults = {
        "id": clar_id or _uid(),
        "commitment_id": commitment_id or _uid(),
        "suggested_clarification_prompt": "What is the deadline?",
        "suggested_values": {"options": ["EOD Friday", "End of month", "ASAP"]},
        "resolved_at": NOW if resolved else None,
        "updated_at": NOW,
        "created_at": NOW,
        "issue_types": ["timing_missing"],
        "issue_severity": "high",
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestClarificationGet:
    def test_returns_open_clarifications_for_commitment(self):
        """GET /clarifications?commitment_id= returns open clarifications."""
        cid = _uid()
        c = _make_commitment_mock(cid=cid)
        clar = _make_clarification(commitment_id=cid)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = c
            result2 = MagicMock()
            result2.scalars.return_value.all.return_value = [clar]
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["suggested_clarification_prompt"] == "What is the deadline?"
        assert data[0]["resolved_at"] is None

    def test_returns_empty_when_all_resolved(self):
        """GET /clarifications returns empty list when all clarifications are resolved."""
        cid = _uid()
        c = _make_commitment_mock(cid=cid)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = c
            result2 = MagicMock()
            result2.scalars.return_value.all.return_value = []
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_multiple_clarifications(self):
        """GET /clarifications returns all open clarifications for a commitment."""
        cid = _uid()
        c = _make_commitment_mock(cid=cid)
        clar1 = _make_clarification(commitment_id=cid, suggested_clarification_prompt="What is the deadline?")
        clar2 = _make_clarification(commitment_id=cid, suggested_clarification_prompt="Who is the recipient?")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = c
            result2 = MagicMock()
            result2.scalars.return_value.all.return_value = [clar1, clar2]
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_commitment_not_found_returns_404(self):
        """GET /clarifications returns 404 when commitment does not exist."""
        cid = _uid()

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result1)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 404

    def test_missing_commitment_id_returns_422(self):
        """GET /clarifications without commitment_id returns 422."""
        async def fake_get_db():
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(BASE_URL, headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422

    def test_clarification_response_includes_issue_types(self):
        """GET /clarifications response includes issue_types field."""
        cid = _uid()
        c = _make_commitment_mock(cid=cid)
        clar = _make_clarification(commitment_id=cid, issue_types=["timing_missing", "owner_ambiguous"])

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = c
            result2 = MagicMock()
            result2.scalars.return_value.all.return_value = [clar]
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "issue_types" in data[0]

    def test_clarification_response_includes_suggested_values(self):
        """GET /clarifications response includes suggested_values field."""
        cid = _uid()
        c = _make_commitment_mock(cid=cid)
        options = {"options": ["EOD Friday", "Next Monday"]}
        clar = _make_clarification(commitment_id=cid, suggested_values=options)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = c
            result2 = MagicMock()
            result2.scalars.return_value.all.return_value = [clar]
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{BASE_URL}?commitment_id={cid}", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert "suggested_values" in resp.json()[0]


class TestClarificationRespond:
    def test_respond_sets_resolved_at(self):
        """POST /clarifications/{id}/respond sets resolved_at on the clarification."""
        cid = _uid()
        clar_id = _uid()
        clar = _make_clarification(clar_id=clar_id, commitment_id=cid)
        c = _make_commitment_mock(cid=cid)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = clar
            result2 = MagicMock()
            result2.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={"answer": "EOD Friday"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert clar.resolved_at is not None

    def test_respond_transitions_commitment_to_active(self):
        """POST respond transitions commitment lifecycle_state to 'active'."""
        cid = _uid()
        clar_id = _uid()
        clar = _make_clarification(clar_id=clar_id, commitment_id=cid)
        c = _make_commitment_mock(cid=cid, lifecycle_state="needs_clarification")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = clar
            result2 = MagicMock()
            result2.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={"answer": "EOD Friday"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert c.lifecycle_state == "active"

    def test_respond_writes_lifecycle_transition_with_correct_trigger(self):
        """POST respond writes LifecycleTransition with trigger_reason='clarification_answered'."""
        cid = _uid()
        clar_id = _uid()
        clar = _make_clarification(clar_id=clar_id, commitment_id=cid)
        c = _make_commitment_mock(cid=cid, lifecycle_state="needs_clarification")
        added_objects = []

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = clar
            result2 = MagicMock()
            result2.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={"answer": "EOD Friday"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert len(added_objects) >= 1
        transition = added_objects[0]
        assert transition.trigger_reason == "clarification_answered"

    def test_respond_404_if_clarification_not_found(self):
        """POST respond returns 404 when clarification doesn't exist."""
        fake_id = _uid()

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{fake_id}/respond",
                json={"answer": "whatever"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 404

    def test_respond_409_if_already_resolved(self):
        """POST respond returns 409 when clarification is already resolved."""
        clar_id = _uid()
        clar = _make_clarification(clar_id=clar_id, resolved=True)

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = clar
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={"answer": "too late"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 409

    def test_respond_missing_answer_returns_422(self):
        """POST respond without 'answer' field returns 422."""
        clar_id = _uid()

        async def fake_get_db():
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422

    def test_respond_returns_200_with_body(self):
        """POST respond returns 200 with a non-empty response body."""
        cid = _uid()
        clar_id = _uid()
        clar = _make_clarification(clar_id=clar_id, commitment_id=cid)
        c = _make_commitment_mock(cid=cid)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalar_one_or_none.return_value = clar
            result2 = MagicMock()
            result2.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{clar_id}/respond",
                json={"answer": "EOD Friday"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json() is not None
