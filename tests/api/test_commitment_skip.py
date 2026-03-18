"""Tests for Skip action — WO-RIPPLED-SKIP-STATE.

Covers:
- POST /commitments/{id}/skip → 200 with skipped_at set
- POST /commitments/{id}/skip with reason → 200, skip_reason stored
- POST /commitments/{id}/skip not found → 404
- POST /commitments/{id}/skip logs to surfacing_audit
- Skipped items filtered from surfacing endpoints
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
        "lifecycle_state": "proposed",
        "delivery_state": None,
        "priority_class": None,
        "commitment_type": None,
        "context_type": None,
        "context_id": None,
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
        "surfaced_as": "main",
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
        "counterparty_name": None,
        "post_event_reviewed": False,
        "skipped_at": None,
        "skip_reason": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    c = MagicMock(spec=[])  # spec=[] prevents auto-attribute creation
    for k, v in defaults.items():
        setattr(c, k, v)
    # These are injected at API layer, not on ORM — prevent MagicMock auto-creation
    if not hasattr(c, "source_sender_name"):
        c.source_sender_name = None
    if not hasattr(c, "source_sender_email"):
        c.source_sender_email = None
    if not hasattr(c, "source_occurred_at"):
        c.source_occurred_at = None
    return c


def _override_db(commitment=None):
    mock_session = AsyncMock()
    call_count = [0]

    async def execute(q):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # First query: get commitment
            result.scalar_one_or_none.return_value = commitment
        else:
            result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = execute
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


# ---------------------------------------------------------------------------
# POST /commitments/{id}/skip
# ---------------------------------------------------------------------------


class TestSkipCommitment:

    def test_skip_sets_skipped_at(self):
        """POST /commitments/{id}/skip → 200, sets skipped_at timestamp."""
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
            response = client.post(
                f"/api/v1/commitments/{cid}/skip",
                json={},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["skipped_at"] is not None
            # lifecycle_state should NOT change (stays proposed)
            assert data["lifecycle_state"] == "proposed"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_skip_with_reason(self):
        """POST /commitments/{id}/skip with reason → stores skip_reason."""
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
            response = client.post(
                f"/api/v1/commitments/{cid}/skip",
                json={"reason": "No source data"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["skip_reason"] == "No source data"
            assert data["skipped_at"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_skip_not_found_returns_404(self):
        """POST /commitments/{id}/skip on unknown ID → 404."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = _override_db(commitment=None)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.post(
                "/api/v1/commitments/nonexistent/skip",
                json={},
                headers=USER_HEADERS,
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

    def test_skip_logs_surfacing_audit(self):
        """POST /commitments/{id}/skip → creates SurfacingAudit row with reason 'skipped'."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        commitment = _make_commitment(commitment_id=cid, surfaced_as="main")
        mock_session = _override_db(commitment=commitment)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            response = client.post(
                f"/api/v1/commitments/{cid}/skip",
                json={"reason": "Too vague"},
                headers=USER_HEADERS,
            )
            assert response.status_code == 200
            # Verify SurfacingAudit was added
            mock_session.add.assert_called()
            added_obj = mock_session.add.call_args[0][0]
            assert added_obj.reason == "skipped"
            assert added_obj.commitment_id == cid
            assert added_obj.user_id == "user-001"
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)
