"""Tests for Phase C4 — Super Admin API.

TDD: These tests are written before implementation. They will pass once
app/api/routes/admin.py is implemented and registered in app/main.py.

Covers:
- Auth middleware (valid key, invalid key, missing header, unconfigured key)
- GET /admin/health
- GET /admin/commitments (filter params, pagination)
- GET /admin/commitments/{id} (detail with linked events, transitions, audit, candidate)
- GET /admin/candidates (filter params)
- GET /admin/candidates/{id}
- GET /admin/surfacing-audit (filter params)
- GET /admin/events (filter params)
- GET /admin/events/{id}
- GET /admin/digests + GET /admin/digests/{id}
- POST /admin/pipeline/run-surfacing
- POST /admin/pipeline/run-linker
- POST /admin/pipeline/run-nudge
- POST /admin/pipeline/run-digest-preview
- POST /admin/pipeline/run-post-event-resolver
- POST /admin/test/seed-commitment
- DELETE /admin/test/cleanup
- PATCH /admin/commitments/{id}/state
"""
from __future__ import annotations

import json as _json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_URL = "/api/v1/admin"
VALID_KEY = "test-admin-secret-key"
VALID_HEADERS = {"X-Admin-Key": VALID_KEY}
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    return str(uuid.uuid4())


def _make_commitment(commitment_id=None, **kwargs):
    defaults = {
        "id": commitment_id or _uid(),
        "user_id": _uid(),
        "title": "Deliver the report",
        "description": "Send by Friday",
        "lifecycle_state": "active",
        "surfaced_as": "main",
        "priority_score": Decimal("72.50"),
        "counterparty_type": "external_client",
        "delivery_state": None,
        "resolved_deadline": NOW + timedelta(days=3),
        "created_at": NOW,
        "updated_at": NOW,
        "is_surfaced": True,
        "surfaced_at": NOW,
        "timing_strength": 2,
        "business_consequence": 3,
        "cognitive_burden": 2,
        "confidence_for_surfacing": Decimal("0.780"),
        "surfacing_reason": "high priority",
        "commitment_text": None,
        "commitment_type": None,
        "priority_class": None,
        "context_type": None,
        "owner_candidates": None,
        "resolved_owner": None,
        "suggested_owner": None,
        "ownership_ambiguity": None,
        "deadline_candidates": None,
        "vague_time_phrase": None,
        "suggested_due_date": None,
        "timing_ambiguity": None,
        "deliverable": None,
        "target_entity": None,
        "suggested_next_step": None,
        "deliverable_ambiguity": None,
        "state_changed_at": NOW,
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
        "delivered_at": None,
        "auto_close_after_hours": 48,
        "observe_until": None,
        "observation_window_hours": None,
        "version": 1,
        "post_event_reviewed": False,
        "counterparty_email": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_candidate(candidate_id=None, **kwargs):
    defaults = {
        "id": candidate_id or _uid(),
        "user_id": _uid(),
        "raw_text": "I'll send the report by Friday",
        "trigger_class": "explicit_commitment",
        "model_classification": "commitment",
        "model_confidence": Decimal("0.92"),
        "model_explanation": "Clear commitment detected",
        "was_promoted": True,
        "was_discarded": False,
        "source_type": "email",
        "created_at": NOW,
        "updated_at": NOW,
        "originating_item_id": _uid(),
        "context_window": {"messages": []},
        "detection_method": "model",
        "model_called_at": NOW,
        "confidence_score": Decimal("0.85"),
        "is_explicit": True,
        "detection_explanation": None,
        "priority_hint": None,
        "commitment_class_hint": None,
        "linked_entities": None,
        "observe_until": None,
        "flag_reanalysis": False,
        "discard_reason": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_event(event_id=None, **kwargs):
    defaults = {
        "id": event_id or _uid(),
        "title": "Client review",
        "event_type": "explicit",
        "status": "confirmed",
        "starts_at": NOW + timedelta(hours=2),
        "ends_at": NOW + timedelta(hours=3),
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


def _make_audit(audit_id=1, commitment_id=None, **kwargs):
    defaults = {
        "id": audit_id,
        "commitment_id": commitment_id or _uid(),
        "old_surfaced_as": "shortlist",
        "new_surfaced_as": "main",
        "priority_score": Decimal("72.50"),
        "reason": "nudge: delivery event within 25h",
        "created_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_transition(transition_id=None, **kwargs):
    defaults = {
        "id": transition_id or _uid(),
        "commitment_id": _uid(),
        "user_id": _uid(),
        "from_state": "proposed",
        "to_state": "active",
        "trigger_reason": "auto",
        "created_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_link(link_id=None, **kwargs):
    defaults = {
        "id": link_id or _uid(),
        "commitment_id": _uid(),
        "event_id": _uid(),
        "relationship": "delivery_at",
        "confidence": Decimal("0.90"),
        "created_at": NOW,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_digest(digest_id=None, **kwargs):
    defaults = {
        "id": digest_id or _uid(),
        "sent_at": NOW,
        "commitment_count": 5,
        "delivery_method": "email",
        "status": "sent",
        "error_message": None,
        "digest_content": {"main": [], "shortlist": [], "clarifications": [], "subject": "test"},
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_mock_db(scalars_result=None, all_result=None, scalar_result=None, execute_result=None):
    """Create an async mock DB session."""
    mock_session = AsyncMock()

    mock_execute = AsyncMock()
    if execute_result is not None:
        mock_execute.return_value = execute_result
    else:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = scalars_result or []
        mock_result.all.return_value = all_result or []
        mock_result.scalar_one_or_none.return_value = scalar_result
        mock_result.scalars.return_value.first.return_value = scalar_result
        mock_execute.return_value = mock_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# TestAdminAuthMiddleware
# ---------------------------------------------------------------------------

class TestAdminAuthMiddleware:

    def test_valid_key_returns_200(self):
        """A valid admin key bypasses auth and reaches the endpoint (not 401/503)."""
        from app.core.config import get_settings as _gs
        from app.db.deps import get_db

        _gs.cache_clear()

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 0
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch("app.api.deps.admin_auth.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(admin_secret_key=VALID_KEY)
                resp = client.get(f"{ADMIN_URL}/health", headers={"X-Admin-Key": VALID_KEY})
        finally:
            app.dependency_overrides.pop(get_db, None)
            _gs.cache_clear()

        assert resp.status_code != 401
        assert resp.status_code != 503

    def test_invalid_key_returns_401(self):
        """A wrong admin key → 401."""
        with patch("app.api.deps.admin_auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(admin_secret_key=VALID_KEY)
            resp = client.get(f"{ADMIN_URL}/health", headers={"X-Admin-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_missing_header_returns_422(self):
        """Missing X-Admin-Key header → 422 (FastAPI validation)."""
        resp = client.get(f"{ADMIN_URL}/health")
        assert resp.status_code == 422

    def test_empty_admin_secret_key_returns_503(self):
        """If admin_secret_key is empty/unconfigured → 503."""
        with patch("app.api.deps.admin_auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(admin_secret_key="")
            resp = client.get(f"{ADMIN_URL}/health", headers={"X-Admin-Key": "any-key"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Fixture: patch admin key for all subsequent tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=False)
def admin_key_configured(monkeypatch):
    """Patch get_settings to have a known admin key."""
    with patch("app.api.deps.admin_auth.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(admin_secret_key=VALID_KEY)
        yield


# ---------------------------------------------------------------------------
# TestAdminHealthEndpoint
# ---------------------------------------------------------------------------

class TestAdminHealthEndpoint:

    def test_health_returns_expected_shape(self, admin_key_configured):
        """GET /admin/health returns tasks, counts, error_count_24h."""
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        # Make all execute calls return a result with scalar_one_or_none=0 and scalars().all()=[]
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 0
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(f"{ADMIN_URL}/health", headers=VALID_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert "tasks" in data
            assert "counts" in data
            assert "error_count_24h" in data
            counts = data["counts"]
            assert "commitments" in counts
            assert "candidates" in counts
            assert "events" in counts
            assert "sources" in counts
            assert "digests_sent" in counts
            assert "surfaced_main" in counts
            assert "surfaced_shortlist" in counts
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# TestAdminCommitmentsFilter
# ---------------------------------------------------------------------------

class TestAdminCommitmentsFilter:

    def _get_with_filter(self, params: dict):
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = 0
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/commitments",
                params=params,
                headers=VALID_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_no_filter_returns_200(self, admin_key_configured):
        resp = self._get_with_filter({})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_lifecycle_state_filter(self, admin_key_configured):
        resp = self._get_with_filter({"lifecycle_state": "active"})
        assert resp.status_code == 200

    def test_surfaced_as_filter(self, admin_key_configured):
        resp = self._get_with_filter({"surfaced_as": "main"})
        assert resp.status_code == 200

    def test_delivery_state_filter(self, admin_key_configured):
        resp = self._get_with_filter({"delivery_state": "delivered"})
        assert resp.status_code == 200

    def test_counterparty_type_filter(self, admin_key_configured):
        resp = self._get_with_filter({"counterparty_type": "external_client"})
        assert resp.status_code == 200

    def test_created_after_filter(self, admin_key_configured):
        resp = self._get_with_filter({"created_after": NOW.isoformat()})
        assert resp.status_code == 200

    def test_sort_param(self, admin_key_configured):
        resp = self._get_with_filter({"sort": "created_at"})
        assert resp.status_code == 200

    def test_limit_offset(self, admin_key_configured):
        resp = self._get_with_filter({"limit": 10, "offset": 20})
        assert resp.status_code == 200

    def test_commitment_detail_returns_expected_shape(self, admin_key_configured):
        """GET /admin/commitments/{id} returns full detail shape."""
        from app.db.deps import get_db
        commitment = _make_commitment()

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        # Detail endpoint calls db.get(Commitment, id)
        mock_db.get = AsyncMock(return_value=commitment)
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/commitments/{commitment.id}",
                headers=VALID_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "commitment" in data
            assert "linked_events" in data
            assert "lifecycle_transitions" in data
            assert "surfacing_audit" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_commitment_detail_not_found(self, admin_key_configured):
        """GET /admin/commitments/{id} with unknown id → 404."""
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=None)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/commitments/{_uid()}",
                headers=VALID_HEADERS,
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# TestAdminCandidatesFilter
# ---------------------------------------------------------------------------

class TestAdminCandidatesFilter:

    def _get_with_filter(self, params: dict):
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = 0
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/candidates",
                params=params,
                headers=VALID_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_no_filter_returns_200(self, admin_key_configured):
        resp = self._get_with_filter({})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_trigger_class_filter(self, admin_key_configured):
        resp = self._get_with_filter({"trigger_class": "explicit_commitment"})
        assert resp.status_code == 200

    def test_model_classification_filter(self, admin_key_configured):
        resp = self._get_with_filter({"model_classification": "commitment"})
        assert resp.status_code == 200

    def test_candidate_detail_returns_shape(self, admin_key_configured):
        """GET /admin/candidates/{id} returns full candidate row."""
        from app.db.deps import get_db
        candidate = _make_candidate()

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=candidate)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/candidates/{candidate.id}",
                headers=VALID_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "id" in data
            assert "context_window" in data
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# TestAdminSurfacingAuditFilter
# ---------------------------------------------------------------------------

class TestAdminSurfacingAuditFilter:

    def _get_with_filter(self, params: dict):
        from app.db.deps import get_db

        commitment = _make_commitment()
        audit = _make_audit(commitment_id=commitment.id)

        mock_db = _make_mock_db()
        mock_result = MagicMock()

        # Simulate joined query returning (audit, title_snippet) pairs
        mock_result.all.return_value = [(audit, "Deliver the report")]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = 1
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/surfacing-audit",
                params=params,
                headers=VALID_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_no_filter_returns_200(self, admin_key_configured):
        resp = self._get_with_filter({})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_commitment_id_filter(self, admin_key_configured):
        resp = self._get_with_filter({"commitment_id": _uid()})
        assert resp.status_code == 200

    def test_surfaced_as_filter(self, admin_key_configured):
        resp = self._get_with_filter({"new_surfaced_as": "main"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestAdminEventsFilter
# ---------------------------------------------------------------------------

class TestAdminEventsFilter:

    def _get_with_filter(self, params: dict):
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = 0
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/events",
                params=params,
                headers=VALID_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_no_filter_returns_200(self, admin_key_configured):
        resp = self._get_with_filter({})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_event_type_filter(self, admin_key_configured):
        resp = self._get_with_filter({"event_type": "explicit"})
        assert resp.status_code == 200

    def test_status_filter(self, admin_key_configured):
        resp = self._get_with_filter({"status": "confirmed"})
        assert resp.status_code == 200

    def test_event_detail_returns_shape(self, admin_key_configured):
        """GET /admin/events/{id} returns event + linked_commitments."""
        from app.db.deps import get_db
        event = _make_event()

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=event)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/events/{event.id}",
                headers=VALID_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "event" in data
            assert "linked_commitments" in data
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# TestAdminDigests
# ---------------------------------------------------------------------------

class TestAdminDigests:

    def test_digests_list_returns_200(self, admin_key_configured):
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = 0
        mock_db.execute.return_value = mock_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(f"{ADMIN_URL}/digests", headers=VALID_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_digest_detail_returns_digest_content(self, admin_key_configured):
        from app.db.deps import get_db
        digest = _make_digest()

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=digest)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.get(
                f"{ADMIN_URL}/digests/{digest.id}",
                headers=VALID_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "digest_content" in data
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# TestPipelineTriggers
# ---------------------------------------------------------------------------

class TestPipelineTriggerSurfacing:

    def test_run_surfacing_calls_service_and_returns_shape(self, admin_key_configured):
        """POST /admin/pipeline/run-surfacing returns correct shape."""
        with patch("app.api.routes.admin.run_surfacing_sweep") as mock_sweep:
            mock_sweep.return_value = {
                "evaluated": 10, "changed": 3, "surfaced": 5, "held": 5,
                "surfaced_main": 3, "surfaced_shortlist": 2,
            }
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-surfacing",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "commitments_scored" in data
        assert "surfaced_to_main" in data
        assert "surfaced_to_shortlist" in data
        assert "duration_ms" in data

    def test_run_surfacing_handles_service_exception(self, admin_key_configured):
        """POST /admin/pipeline/run-surfacing returns 500 on service exception."""
        with patch("app.api.routes.admin.run_surfacing_sweep") as mock_sweep:
            mock_sweep.side_effect = Exception("DB error")
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-surfacing",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 500


class TestPipelineTriggerLinker:

    def test_run_linker_returns_shape(self, admin_key_configured):
        """POST /admin/pipeline/run-linker returns linked and created_implicit."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("app.api.routes.admin.get_sync_session", return_value=mock_ctx):
            with patch("app.api.routes.admin.DeadlineEventLinker") as mock_linker_cls:
                mock_linker = MagicMock()
                mock_linker.run.return_value = {"links_created": 2, "implicit_events_created": 1}
                mock_linker_cls.return_value = mock_linker
                resp = client.post(
                    f"{ADMIN_URL}/pipeline/run-linker",
                    headers=VALID_HEADERS,
                )
        assert resp.status_code == 200
        data = resp.json()
        assert "linked" in data
        assert "created_implicit" in data
        assert "duration_ms" in data

    def test_run_linker_handles_exception(self, admin_key_configured):
        with patch("app.api.routes.admin.DeadlineEventLinker") as mock_linker_cls:
            mock_linker_cls.side_effect = Exception("fail")
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-linker",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 500


class TestPipelineTriggerNudge:

    def test_run_nudge_returns_nudged_count(self, admin_key_configured):
        """POST /admin/pipeline/run-nudge returns nudged count."""
        with patch("app.api.routes.admin.NudgeService") as mock_nudge_cls, \
             patch("app.api.routes.admin.NudgeService.load_pairs") as mock_load:
            mock_load.return_value = []
            mock_nudge = MagicMock()
            mock_nudge.run.return_value = {"nudged": 2}
            mock_nudge_cls.return_value = mock_nudge
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-nudge",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "nudged" in data
        assert "duration_ms" in data

    def test_run_nudge_handles_exception(self, admin_key_configured):
        with patch("app.api.routes.admin.NudgeService") as mock_nudge_cls:
            mock_nudge_cls.side_effect = Exception("fail")
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-nudge",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 500


class TestPipelineTriggerDigestPreview:

    def test_run_digest_preview_returns_shape(self, admin_key_configured):
        """POST /admin/pipeline/run-digest-preview returns full shape without delivering."""
        mock_commitment = _make_commitment()
        mock_digest = MagicMock()
        mock_digest.main = [mock_commitment]
        mock_digest.shortlist = []
        mock_digest.clarifications = []
        mock_digest.is_empty = False

        mock_formatted = MagicMock()
        mock_formatted.subject = "Daily digest: 1 commitment"

        with patch("app.api.routes.admin.DigestAggregator") as mock_agg_cls, \
             patch("app.api.routes.admin.DigestFormatter") as mock_fmt_cls:
            mock_agg = MagicMock()
            mock_agg.aggregate_sync.return_value = mock_digest
            mock_agg_cls.return_value = mock_agg

            mock_fmt = MagicMock()
            mock_fmt.format.return_value = mock_formatted
            mock_fmt_cls.return_value = mock_fmt

            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-digest-preview",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "main" in data
        assert "shortlist" in data
        assert "clarifications" in data
        assert "commitment_count" in data
        assert "subject" in data
        assert "duration_ms" in data

    def test_digest_preview_does_not_call_delivery(self, admin_key_configured):
        """Digest preview must NOT call DigestDelivery."""
        mock_digest = MagicMock()
        mock_digest.main = []
        mock_digest.shortlist = []
        mock_digest.clarifications = []
        mock_digest.is_empty = True

        with patch("app.api.routes.admin.DigestAggregator") as mock_agg_cls, \
             patch("app.api.routes.admin.DigestFormatter"), \
             patch("app.api.routes.admin.DigestDelivery") as mock_delivery_cls:
            mock_agg = MagicMock()
            mock_agg.aggregate_sync.return_value = mock_digest
            mock_agg_cls.return_value = mock_agg

            client.post(
                f"{ADMIN_URL}/pipeline/run-digest-preview",
                headers=VALID_HEADERS,
            )
            mock_delivery_cls.assert_not_called()


class TestPipelineTriggerPostEventResolver:

    def test_run_post_event_resolver_returns_shape(self, admin_key_configured):
        """POST /admin/pipeline/run-post-event-resolver returns processed/escalated."""
        with patch("app.api.routes.admin.PostEventResolver") as mock_cls, \
             patch("app.api.routes.admin.PostEventResolver.load_pairs") as mock_load:
            mock_load.return_value = ([], {})
            mock_resolver = MagicMock()
            mock_resolver.run.return_value = {"processed": 3, "escalated": 1}
            mock_cls.return_value = mock_resolver
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-post-event-resolver",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "processed" in data
        assert "escalated" in data
        assert "duration_ms" in data

    def test_run_post_event_resolver_handles_exception(self, admin_key_configured):
        with patch("app.api.routes.admin.PostEventResolver") as mock_cls:
            mock_cls.side_effect = Exception("fail")
            resp = client.post(
                f"{ADMIN_URL}/pipeline/run-post-event-resolver",
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# TestAdminTestSeed
# ---------------------------------------------------------------------------

class TestAdminTestSeed:

    def test_seed_creates_full_chain(self, admin_key_configured):
        """POST /admin/test/seed-commitment returns all IDs."""
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        # Simulate user lookup returning None (creates new user)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.post(
                f"{ADMIN_URL}/test/seed-commitment",
                headers=VALID_HEADERS,
                json={"description": "Test commitment"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert "commitment_id" in data
            assert "user_id" in data
            assert "source_id" in data
            assert "source_item_id" in data
            assert "candidate_id" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_seed_uses_admin_test_seed_label(self, admin_key_configured):
        """Seed endpoint creates Source with display_name='admin-test-seed'."""
        from app.db.deps import get_db

        added_objects = []
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client.post(
                f"{ADMIN_URL}/test/seed-commitment",
                headers=VALID_HEADERS,
                json={"description": "Test commitment"},
            )
            # Check that a Source with display_name='admin-test-seed' was added
            from app.models.orm import Source
            source_objs = [o for o in added_objects if isinstance(o, Source)]
            assert any(
                getattr(s, "display_name", None) == "admin-test-seed"
                for s in source_objs
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_seed_default_lifecycle_state_is_active(self, admin_key_configured):
        """Seed uses lifecycle_state='active' when not specified."""
        from app.db.deps import get_db

        added_objects = []
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client.post(
                f"{ADMIN_URL}/test/seed-commitment",
                headers=VALID_HEADERS,
                json={"description": "Test commitment"},
            )
            from app.models.orm import Commitment
            commitment_objs = [o for o in added_objects if isinstance(o, Commitment)]
            assert any(
                getattr(c, "lifecycle_state", None) == "active"
                for c in commitment_objs
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_seed_wrong_body_returns_422(self, admin_key_configured):
        """Missing required 'description' field → 422."""
        resp = client.post(
            f"{ADMIN_URL}/test/seed-commitment",
            headers=VALID_HEADERS,
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestAdminTestCleanup
# ---------------------------------------------------------------------------

class TestAdminTestCleanup:

    def test_cleanup_deletes_seed_rows(self, admin_key_configured):
        """DELETE /admin/test/cleanup returns deleted counts."""
        from app.db.deps import get_db

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db.delete = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.request(
                "DELETE",
                f"{ADMIN_URL}/test/cleanup",
                headers=VALID_HEADERS,
                json={"confirm": "delete-test-data"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "deleted_commitments" in data
            assert "deleted_candidates" in data
            assert "deleted_source_items" in data
            assert "deleted_sources" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_cleanup_wrong_confirm_returns_422(self, admin_key_configured):
        """Wrong 'confirm' value → 422."""
        from app.db.deps import get_db

        mock_db = _make_mock_db()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.request(
                "DELETE",
                f"{ADMIN_URL}/test/cleanup",
                headers=VALID_HEADERS,
                json={"confirm": "wrong-value"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_cleanup_missing_body_returns_422(self, admin_key_configured):
        """Missing body → 422."""
        resp = client.delete(
            f"{ADMIN_URL}/test/cleanup",
            headers=VALID_HEADERS,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestAdminStateOverride
# ---------------------------------------------------------------------------

class TestAdminStateOverride:

    def test_lifecycle_state_override_bypasses_transitions(self, admin_key_configured):
        """PATCH /admin/commitments/{id}/state can set any lifecycle_state."""
        from app.db.deps import get_db
        commitment = _make_commitment(lifecycle_state="discarded")

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=commitment)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.patch(
                f"{ADMIN_URL}/commitments/{commitment.id}/state",
                headers=VALID_HEADERS,
                json={"lifecycle_state": "active", "reason": "admin test override"},
            )
            assert resp.status_code == 200
            # Verify commitment.lifecycle_state was set to "active"
            assert commitment.lifecycle_state == "active"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_delivery_state_override(self, admin_key_configured):
        """PATCH /admin/commitments/{id}/state can set delivery_state."""
        from app.db.deps import get_db
        commitment = _make_commitment(delivery_state=None)

        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=commitment)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.patch(
                f"{ADMIN_URL}/commitments/{commitment.id}/state",
                headers=VALID_HEADERS,
                json={"delivery_state": "delivered", "reason": "manually confirmed"},
            )
            assert resp.status_code == 200
            assert commitment.delivery_state == "delivered"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_state_override_writes_surfacing_audit(self, admin_key_configured):
        """State override writes SurfacingAudit row with 'admin-override:' reason."""
        from app.db.deps import get_db
        commitment = _make_commitment()

        added_objects = []
        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=commitment)
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client.patch(
                f"{ADMIN_URL}/commitments/{commitment.id}/state",
                headers=VALID_HEADERS,
                json={"lifecycle_state": "active", "reason": "test reason"},
            )
            from app.models.orm import SurfacingAudit
            audit_objs = [o for o in added_objects if isinstance(o, SurfacingAudit)]
            assert len(audit_objs) >= 1
            assert "admin-override:" in (audit_objs[0].reason or "")
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_state_override_writes_lifecycle_transition(self, admin_key_configured):
        """State override writes LifecycleTransition with commitment's user_id."""
        from app.db.deps import get_db
        user_id = _uid()
        commitment = _make_commitment(user_id=user_id)

        added_objects = []
        mock_db = _make_mock_db()
        mock_db.get = AsyncMock(return_value=commitment)
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client.patch(
                f"{ADMIN_URL}/commitments/{commitment.id}/state",
                headers=VALID_HEADERS,
                json={"lifecycle_state": "active", "reason": "test"},
            )
            from app.models.orm import LifecycleTransition
            lt_objs = [o for o in added_objects if isinstance(o, LifecycleTransition)]
            assert len(lt_objs) >= 1
            assert lt_objs[0].user_id == user_id
        finally:
            app.dependency_overrides.pop(get_db, None)
