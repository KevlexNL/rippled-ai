"""Tests for Phase C5 — Delivery State Extensions.

TDD: Tests for PATCH /commitments/{id}/delivery-state extensions.
Covers:
- state='pending' sets post_event_reviewed=True, does NOT change delivery_state
- state='pending' still returns full CommitmentRead
- state='delivered' sets delivery_state AND lifecycle_state='delivered' atomically
- state='delivered' writes a LifecycleTransition record
- Invalid state still returns 422
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
BASE_URL = "/api/v1/commitments"
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
USER_HEADERS = {"x-user-id": USER_ID}
NOW = datetime.now(timezone.utc)


def _uid():
    return str(uuid.uuid4())


def _make_commitment(**kwargs):
    defaults = {
        "id": _uid(),
        "user_id": USER_ID,
        "version": 1,
        "title": "Send the report",
        "description": "Send by Friday",
        "commitment_text": None,
        "commitment_type": None,
        "priority_class": None,
        "context_type": None,
        "owner_candidates": None,
        "resolved_owner": None,
        "suggested_owner": None,
        "ownership_ambiguity": None,
        "deadline_candidates": None,
        "resolved_deadline": NOW + timedelta(days=3),
        "vague_time_phrase": None,
        "suggested_due_date": None,
        "timing_ambiguity": None,
        "deliverable": None,
        "target_entity": None,
        "suggested_next_step": None,
        "deliverable_ambiguity": None,
        "lifecycle_state": "active",
        "state_changed_at": NOW,
        "confidence_commitment": None,
        "confidence_owner": None,
        "confidence_deadline": None,
        "confidence_delivery": None,
        "confidence_closure": None,
        "confidence_actionability": None,
        "commitment_explanation": None,
        "missing_pieces_explanation": None,
        "is_surfaced": True,
        "surfaced_at": NOW,
        "observe_until": None,
        "observation_window_hours": None,
        "surfaced_as": "main",
        "priority_score": Decimal("75.00"),
        "timing_strength": None,
        "business_consequence": None,
        "cognitive_burden": None,
        "confidence_for_surfacing": None,
        "surfacing_reason": None,
        "delivery_state": None,
        "counterparty_type": None,
        "counterparty_email": None,
        "counterparty_name": None,
        "counterparty_resolved": None,
        "user_relationship": "mine",
        "structure_complete": True,
        "post_event_reviewed": False,
        "skipped_at": None,
        "skip_reason": None,
        "created_at": NOW,
        "updated_at": NOW,
        "delivery_explanation": None,
        "closure_explanation": None,
        "delivered_at": None,
        "auto_close_after_hours": 48,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _empty_result():
    r = MagicMock()
    r.__iter__ = MagicMock(return_value=iter([]))
    return r


class TestDeliveryStatePending:
    def test_pending_sets_post_event_reviewed_true(self):
        """state='pending' sets post_event_reviewed=True."""
        c = _make_commitment(post_event_reviewed=False, delivery_state=None)
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "pending"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert c.post_event_reviewed is True

    def test_pending_does_not_change_delivery_state(self):
        """state='pending' does NOT mutate delivery_state field."""
        c = _make_commitment(post_event_reviewed=False, delivery_state=None)
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "pending"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert c.delivery_state is None

    def test_pending_returns_full_commitment_read(self):
        """state='pending' returns 200 with full CommitmentRead shape."""
        c = _make_commitment()
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "pending"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "title" in data
        assert "lifecycle_state" in data

    def test_pending_on_already_reviewed_commitment(self):
        """state='pending' on already-reviewed commitment is idempotent (200)."""
        c = _make_commitment(post_event_reviewed=True, delivery_state=None)
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "pending"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200


class TestDeliveryStateDelivered:
    def test_delivered_sets_delivery_state(self):
        """state='delivered' sets delivery_state='delivered' on the commitment."""
        c = _make_commitment(delivery_state=None, lifecycle_state="active")
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert c.delivery_state == "delivered"

    def test_delivered_sets_lifecycle_state_to_delivered(self):
        """state='delivered' sets lifecycle_state='delivered' atomically."""
        c = _make_commitment(delivery_state=None, lifecycle_state="active")
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert c.lifecycle_state == "delivered"

    def test_delivered_writes_lifecycle_transition(self):
        """state='delivered' calls db.add with at least one object (LifecycleTransition)."""
        c = _make_commitment(delivery_state=None, lifecycle_state="active")
        cid = c.id
        added_objects = []

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert len(added_objects) >= 1

    def test_delivered_returns_full_commitment_read(self):
        """state='delivered' returns 200 with full CommitmentRead shape."""
        c = _make_commitment(delivery_state=None, lifecycle_state="active")
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(side_effect=[result, _empty_result()])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "lifecycle_state" in data


class TestDeliveryStateValidation:
    def test_invalid_state_returns_422(self):
        """Invalid delivery state value returns 422."""
        c = _make_commitment()
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = c
            db.execute = AsyncMock(return_value=result)
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={"state": "not_a_real_state"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422

    def test_missing_state_field_returns_422(self):
        """PATCH without 'state' field returns 422."""
        c = _make_commitment()
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.patch(
                f"{BASE_URL}/{cid}/delivery-state",
                json={},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422

    def test_commitment_not_found_returns_404(self):
        """PATCH on non-existent commitment returns 404."""
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
            resp = client.patch(
                f"{BASE_URL}/{fake_id}/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 404
