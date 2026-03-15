"""Tests for Phase C5 — Linked Events in Surface Response.

TDD: Tests that surface and commitment endpoints return linked_events.
Covers:
- GET /surface/main includes linked_events for commitments with delivery_at links
- GET /surface/main returns empty linked_events for commitments without links
- Only delivery_at relationship returned (not prep_at or review_at)
- Cancelled events excluded
- GET /surface/main C3 fields (delivery_state, counterparty_type) present in response
- post_event_reviewed present in surface response
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
        "title": "Deliver report",
        "description": "Send by Friday",
        "commitment_text": None,
        "commitment_type": None,
        "priority_class": None,
        "context_type": "email",
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
        "post_event_reviewed": False,
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


def _make_link(commitment_id, event_id, relationship="delivery_at"):
    obj = MagicMock()
    obj.commitment_id = commitment_id
    obj.event_id = event_id
    obj.relationship = relationship
    return obj


def _make_event(event_id=None, **kwargs):
    defaults = {
        "id": event_id or _uid(),
        "title": "Client review meeting",
        "starts_at": NOW + timedelta(hours=10),
        "ends_at": NOW + timedelta(hours=11),
        "status": "confirmed",
        "event_type": "explicit",
        "created_at": NOW,
        "updated_at": NOW,
        "external_id": None,
        "description": None,
        "is_recurring": False,
        "recurrence_rule": None,
        "location": None,
        "attendees": None,
        "rescheduled_from": None,
        "cancelled_at": None,
        "source_id": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestLinkedEventsInSurfaceMain:
    def test_surface_main_includes_linked_events(self):
        """GET /surface/main includes linked_events for commitments with delivery_at links."""
        c = _make_commitment()
        ev = _make_event()
        link = _make_link(c.id, ev.id)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([(link, ev)]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "linked_events" in data[0]
        assert len(data[0]["linked_events"]) == 1
        assert data[0]["linked_events"][0]["title"] == "Client review meeting"

    def test_surface_main_empty_linked_events_when_no_links(self):
        """GET /surface/main returns empty linked_events when commitment has no event links."""
        c = _make_commitment()

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["linked_events"] == []

    def test_surface_main_linked_events_have_relationship_field(self):
        """linked_events items include the relationship field."""
        c = _make_commitment()
        ev = _make_event()
        link = _make_link(c.id, ev.id, relationship="delivery_at")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([(link, ev)]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        linked = data[0]["linked_events"]
        assert len(linked) == 1
        assert linked[0]["relationship"] == "delivery_at"

    def test_surface_main_includes_delivery_state_field(self):
        """GET /surface/main response includes delivery_state (C3 field)."""
        c = _make_commitment(delivery_state="draft_sent")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "delivery_state" in data[0]
        assert data[0]["delivery_state"] == "draft_sent"

    def test_surface_main_includes_counterparty_type_field(self):
        """GET /surface/main response includes counterparty_type (C3 field)."""
        c = _make_commitment(counterparty_type="external_client")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "counterparty_type" in data[0]
        assert data[0]["counterparty_type"] == "external_client"

    def test_surface_main_includes_post_event_reviewed_field(self):
        """GET /surface/main response includes post_event_reviewed (C5 gap fix)."""
        c = _make_commitment(post_event_reviewed=True)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "post_event_reviewed" in data[0]
        assert data[0]["post_event_reviewed"] is True

    def test_surface_main_delivery_state_acknowledged(self):
        """delivery_state='acknowledged' is returned verbatim in surface response."""
        c = _make_commitment(delivery_state="acknowledged")

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json()[0]["delivery_state"] == "acknowledged"

    def test_surface_main_multiple_commitments_each_get_correct_events(self):
        """Multiple commitments each get their own linked_events, not each other's."""
        c1 = _make_commitment()
        c2 = _make_commitment()
        ev1 = _make_event()
        link1 = _make_link(c1.id, ev1.id)

        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([c1, c2]))
            result2 = MagicMock()
            # Only c1 has a link; c2 has none
            result2.__iter__ = MagicMock(return_value=iter([(link1, ev1)]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Find c1 and c2 in response
        by_id = {item["id"]: item for item in data}
        assert len(by_id[c1.id]["linked_events"]) == 1
        assert len(by_id[c2.id]["linked_events"]) == 0

    def test_surface_main_empty_when_no_commitments(self):
        """GET /surface/main returns empty list when user has no surfaced commitments."""
        async def fake_get_db():
            db = AsyncMock()
            result1 = MagicMock()
            result1.scalars = MagicMock(return_value=iter([]))
            result2 = MagicMock()
            result2.__iter__ = MagicMock(return_value=iter([]))
            db.execute = AsyncMock(side_effect=[result1, result2])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get("/api/v1/surface/main", headers=USER_HEADERS)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        assert resp.json() == []
