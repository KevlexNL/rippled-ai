"""Tests for Phase C3 — Commitment delivery-state and events sub-routes.

Covers:
- PATCH /commitments/{id}/delivery-state valid state → 200
- PATCH /commitments/{id}/delivery-state invalid state → 422
- PATCH /commitments/{id}/delivery-state not found → 404
- GET /commitments/{id}/events → list of links
- POST /commitments/{id}/events → create manual link → 201
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-001"}
NOW = datetime.now(timezone.utc)


def _make_commitment(commitment_id=None, **kwargs):
    defaults = {
        "id": commitment_id or str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Send report",
        "lifecycle_state": "active",
        "delivery_state": None,
        "priority_class": None,
        "commitment_type": None,
        "context_type": None,
        "owner_candidates": None,
        "resolved_owner": None,
        "suggested_owner": None,
        "ownership_ambiguity": None,
        "deadline_candidates": None,
        "resolved_deadline": None,
        "vague_time_phrase": None,
        "suggested_due_date": None,
        "timing_ambiguity": None,
        "deliverable": None,
        "target_entity": None,
        "suggested_next_step": None,
        "deliverable_ambiguity": None,
        "confidence_commitment": None,
        "confidence_owner": None,
        "confidence_deadline": None,
        "confidence_delivery": None,
        "confidence_closure": None,
        "confidence_actionability": None,
        "commitment_explanation": None,
        "missing_pieces_explanation": None,
        "delivery_explanation": None,
        "closure_explanation": None,
        "commitment_text": None,
        "description": None,
        "version": 1,
        "is_surfaced": False,
        "surfaced_at": None,
        "surfaced_as": None,
        "priority_score": None,
        "timing_strength": None,
        "business_consequence": None,
        "cognitive_burden": None,
        "confidence_for_surfacing": None,
        "surfacing_reason": None,
        "delivered_at": None,
        "auto_close_after_hours": 48,
        "observe_until": None,
        "observation_window_hours": None,
        "state_changed_at": NOW,
        "counterparty_type": None,
        "counterparty_email": None,
        "post_event_reviewed": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    c = MagicMock()
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


def _make_link(link_id=None, commitment_id="c-001", event_id="e-001"):
    l = MagicMock()
    l.id = link_id or str(uuid.uuid4())
    l.commitment_id = commitment_id
    l.event_id = event_id
    l.relationship = "delivery_at"
    l.confidence = Decimal("0.900")
    l.created_at = NOW
    return l


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _override_db(commitment=None, links=None, event=None):
    mock_session = AsyncMock()
    call_count = [0]

    async def execute(q):
        call_count[0] += 1
        result = MagicMock()
        idx = call_count[0]
        if idx == 1:
            result.scalar_one_or_none.return_value = commitment
        elif idx == 2:
            result.scalars.return_value.all.return_value = links or []
        elif idx == 3:
            result.scalar_one_or_none.return_value = event
        else:
            result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = execute
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


# ---------------------------------------------------------------------------
# PATCH /commitments/{id}/delivery-state
# ---------------------------------------------------------------------------


class TestDeliveryStatePatch:

    def test_valid_state_transitions(self):
        """Valid delivery state → 200 and state updated."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        commitment = _make_commitment(commitment_id=cid)
        mock_session = _override_db(commitment=commitment)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.patch(
                f"/api/v1/commitments/{cid}/delivery-state",
                json={"state": "draft_sent"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            assert commitment.delivery_state == "draft_sent"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_invalid_state_returns_422(self):
        """Invalid delivery state → 422."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        commitment = _make_commitment(commitment_id=cid)
        mock_session = _override_db(commitment=commitment)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.patch(
                f"/api/v1/commitments/{cid}/delivery-state",
                json={"state": "not_a_state"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_not_found_returns_404(self):
        """Unknown commitment ID → 404."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = _override_db(commitment=None)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.patch(
                "/api/v1/commitments/nonexistent/delivery-state",
                json={"state": "delivered"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# GET /commitments/{id}/events
# ---------------------------------------------------------------------------


class TestCommitmentEvents:

    def test_list_event_links(self):
        """GET /commitments/{id}/events → returns list of CommitmentEventLink."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        commitment = _make_commitment(commitment_id=cid)
        link = _make_link(commitment_id=cid)
        mock_session = AsyncMock()
        call_count = [0]

        async def execute(q):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = commitment
            else:
                result.scalars.return_value.all.return_value = [link]
            return result

        mock_session.execute = execute
        mock_session.flush = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.get(
                f"/api/v1/commitments/{cid}/events",
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["relationship"] == "delivery_at"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_post_manual_event_link(self):
        """POST /commitments/{id}/events → creates CommitmentEventLink → 201."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        eid = str(uuid.uuid4())
        commitment = _make_commitment(commitment_id=cid)
        event = MagicMock()
        event.id = eid
        link = _make_link(commitment_id=cid, event_id=eid)
        mock_session = AsyncMock()
        call_count = [0]

        async def execute(q):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = commitment
            elif call_count[0] == 2:
                result.scalar_one_or_none.return_value = event
            return result

        mock_session.execute = execute
        mock_session.flush = AsyncMock()

        async def mock_refresh(obj):
            obj.id = link.id
            obj.commitment_id = cid
            obj.event_id = eid
            obj.relationship = "delivery_at"
            obj.confidence = Decimal("1.000")
            obj.created_at = NOW

        mock_session.refresh = mock_refresh
        mock_session.add = MagicMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.post(
                f"/api/v1/commitments/{cid}/events",
                json={"event_id": eid, "relationship": "delivery_at"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["event_id"] == eid
            assert data["relationship"] == "delivery_at"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)
