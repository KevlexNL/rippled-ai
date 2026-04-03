"""Tests for POST /candidates/{id}/reanalyze — E2 re-analysis workflow.

Covers:
- POST /candidates/{id}/reanalyze → 200, flag_reanalysis set to true
- POST /candidates/{id}/reanalyze on promoted candidate → 409
- POST /candidates/{id}/reanalyze on discarded candidate → 409
- POST /candidates/{id}/reanalyze not found → 404
- Idempotent: already-flagged candidate → 200 (no error)
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
PREFIX = "/api/v1"


def _make_candidate(candidate_id=None, **kwargs):
    defaults = {
        "id": candidate_id or str(uuid.uuid4()),
        "user_id": "user-001",
        "originating_item_id": str(uuid.uuid4()),
        "source_type": "meeting",
        "raw_text": "I will send the report by Friday",
        "trigger_class": "explicit_promise",
        "is_explicit": True,
        "detection_explanation": "Matched pattern",
        "confidence_score": Decimal("0.55"),
        "priority_hint": "medium",
        "commitment_class_hint": "small_commitment",
        "context_window": {"trigger_text": "I will send"},
        "linked_entities": None,
        "observe_until": None,
        "flag_reanalysis": False,
        "was_promoted": False,
        "was_discarded": False,
        "discard_reason": None,
        "model_confidence": None,
        "model_classification": None,
        "model_explanation": None,
        "model_called_at": None,
        "detection_method": "tier_2",
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    c = MagicMock(spec=[])
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


def _override_db(candidate=None):
    mock_session = AsyncMock()

    async def execute(q):
        result = MagicMock()
        result.scalar_one_or_none.return_value = candidate
        return result

    mock_session.execute = execute
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    return mock_session


class TestReanalyzeCandidate:

    def test_flags_candidate_for_reanalysis(self):
        """POST /candidates/{id}/reanalyze → 200, flag_reanalysis=true."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        candidate = _make_candidate(candidate_id=cid)
        mock_session = _override_db(candidate=candidate)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            resp = client.post(f"{PREFIX}/candidates/{cid}/reanalyze", headers=USER_HEADERS)
            assert resp.status_code == 200
            assert candidate.flag_reanalysis is True
        finally:
            app.dependency_overrides.clear()

    def test_reanalyze_not_found(self):
        """POST /candidates/{id}/reanalyze on nonexistent → 404."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        mock_session = _override_db(candidate=None)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            resp = client.post(f"{PREFIX}/candidates/{uuid.uuid4()}/reanalyze", headers=USER_HEADERS)
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_reanalyze_promoted_candidate_rejected(self):
        """POST /candidates/{id}/reanalyze on promoted → 409."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        candidate = _make_candidate(candidate_id=cid, was_promoted=True)
        mock_session = _override_db(candidate=candidate)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            resp = client.post(f"{PREFIX}/candidates/{cid}/reanalyze", headers=USER_HEADERS)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.clear()

    def test_reanalyze_discarded_candidate_rejected(self):
        """POST /candidates/{id}/reanalyze on discarded → 409."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        candidate = _make_candidate(candidate_id=cid, was_discarded=True)
        mock_session = _override_db(candidate=candidate)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            resp = client.post(f"{PREFIX}/candidates/{cid}/reanalyze", headers=USER_HEADERS)
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.clear()

    def test_reanalyze_already_flagged_is_idempotent(self):
        """POST /candidates/{id}/reanalyze on already-flagged → 200 (no error)."""
        from app.db.deps import get_db
        from app.core.dependencies import get_current_user_id

        cid = str(uuid.uuid4())
        candidate = _make_candidate(candidate_id=cid, flag_reanalysis=True)
        mock_session = _override_db(candidate=candidate)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_id] = lambda: "user-001"
        try:
            resp = client.post(f"{PREFIX}/candidates/{cid}/reanalyze", headers=USER_HEADERS)
            assert resp.status_code == 200
            assert candidate.flag_reanalysis is True
        finally:
            app.dependency_overrides.clear()
