"""Integration tests for Phase D4 — User Feedback Loops.

TDD RED phase: these tests define the API + pipeline integration contract.
~10 tests covering feedback endpoint, stats endpoint, lifecycle transitions,
and Celery recompute task.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id

client = TestClient(app)
BASE_URL = "/api/v1/commitments"
USER_URL = "/api/v1/user"
USER_ID = "test-user-" + str(uuid.uuid4())[:8]
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
        "context_id": None,
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
        "requester_name": None,
        "requester_email": None,
        "beneficiary_name": None,
        "beneficiary_email": None,
        "detection_method": None,
        "model_classification": None,
        "model_confidence": None,
        "due_precision": None,
        "context_tags": None,
        "speech_act": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_candidate(**kwargs):
    defaults = {
        "id": _uid(),
        "source_type": "email",
        "trigger_class": "explicit_self_commitment",
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_feedback_mock(commitment_id: str, action: str = "confirm"):
    """Return a mock UserFeedback object with valid fields for FeedbackRead."""
    return MagicMock(
        id=_uid(),
        user_id=USER_ID,
        commitment_id=commitment_id,
        action=action,
        field_changed=None,
        old_value=None,
        new_value=None,
        source_type="email",
        trigger_class="explicit_self_commitment",
        created_at=NOW,
    )


def _make_profile(**kwargs):
    defaults = {
        "id": _uid(),
        "user_id": USER_ID,
        "threshold_adjustments": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _empty_result():
    r = MagicMock()
    r.__iter__ = MagicMock(return_value=iter([]))
    r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    return r


def _scalar_result(val):
    r = MagicMock()
    r.scalar_one_or_none.return_value = val
    return r


def _count_result(val):
    r = MagicMock()
    r.scalar.return_value = val
    return r


# ---------------------------------------------------------------------------
# POST /commitments/{id}/feedback
# ---------------------------------------------------------------------------


class TestFeedbackEndpoint:
    def test_post_feedback_creates_record(self):
        """POST feedback with valid action returns 201."""
        c = _make_commitment()
        cid = c.id
        candidate = _make_candidate()

        async def _refresh(obj):
            obj.id = _uid()
            obj.created_at = NOW

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(side_effect=[
                _scalar_result(c),
                _scalar_result(candidate),
                _count_result(5),
            ])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = _refresh
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{cid}/feedback",
                json={"action": "confirm"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 201

    def test_post_feedback_dismiss_transitions_to_discarded(self):
        """POST feedback with action='dismiss' transitions commitment to discarded."""
        c = _make_commitment(lifecycle_state="active")
        cid = c.id
        candidate = _make_candidate()

        async def _refresh(obj):
            obj.id = _uid()
            obj.created_at = NOW

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(side_effect=[
                _scalar_result(c),
                _scalar_result(candidate),
                _count_result(5),
            ])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = _refresh
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{cid}/feedback",
                json={"action": "dismiss"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 201
        assert c.lifecycle_state == "discarded"

    def test_post_feedback_confirm_transitions_to_confirmed(self):
        """POST feedback with action='confirm' transitions commitment to confirmed."""
        c = _make_commitment(lifecycle_state="active")
        cid = c.id
        candidate = _make_candidate()

        async def _refresh(obj):
            obj.id = _uid()
            obj.created_at = NOW

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(side_effect=[
                _scalar_result(c),
                _scalar_result(candidate),
                _count_result(5),
            ])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = _refresh
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{cid}/feedback",
                json={"action": "confirm"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 201
        assert c.lifecycle_state == "confirmed"

    def test_post_feedback_mark_not_commitment_transitions_to_discarded(self):
        """POST feedback with action='mark_not_commitment' transitions to discarded."""
        c = _make_commitment(lifecycle_state="proposed")
        cid = c.id
        candidate = _make_candidate()

        async def _refresh(obj):
            obj.id = _uid()
            obj.created_at = NOW

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(side_effect=[
                _scalar_result(c),
                _scalar_result(candidate),
                _count_result(5),
            ])
            db.add = MagicMock()
            db.flush = AsyncMock()
            db.refresh = _refresh
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{cid}/feedback",
                json={"action": "mark_not_commitment"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 201
        assert c.lifecycle_state == "discarded"

    def test_post_feedback_nonexistent_commitment_returns_404(self):
        """POST feedback on nonexistent commitment returns 404."""

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_result(None))
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{_uid()}/feedback",
                json={"action": "confirm"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 404

    def test_post_feedback_invalid_action_returns_422(self):
        """POST feedback with invalid action returns 422."""
        c = _make_commitment()
        cid = c.id

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_result(c))
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.post(
                f"{BASE_URL}/{cid}/feedback",
                json={"action": "invalid_action"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /user/feedback-stats
# ---------------------------------------------------------------------------


class TestFeedbackStatsEndpoint:
    def test_get_feedback_stats_returns_adjustments(self):
        """GET feedback-stats returns current adjustments and summary."""
        profile = _make_profile(threshold_adjustments={
            "surfacing_threshold_delta": 0.05,
            "detection_confidence_delta": -0.03,
            "sender_adjustments": {},
            "pattern_adjustments": {},
            "completion_confidence_delta": 0.0,
            "last_computed_at": NOW.isoformat(),
            "feedback_count": 45,
        })

        async def fake_get_db():
            db = AsyncMock()
            # 1. profile lookup
            # 2. feedback count queries (dismiss, confirm, correct)
            db.execute = AsyncMock(side_effect=[
                _scalar_result(profile),
                _count_result(12),  # dismiss_count
                _count_result(28),  # confirm_count
                _count_result(5),   # correct_count
            ])
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{USER_URL}/feedback-stats")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "threshold_adjustments" in data
        assert "feedback_summary" in data

    def test_get_feedback_stats_no_feedback_returns_zeros(self):
        """GET feedback-stats with no feedback returns zeros."""

        async def fake_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(side_effect=[
                _scalar_result(None),  # no profile
                _count_result(0),
                _count_result(0),
                _count_result(0),
            ])
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID
        try:
            resp = client.get(f"{USER_URL}/feedback-stats")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user_id, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_feedback_count"] == 0


# ---------------------------------------------------------------------------
# Pipeline integration: apply functions with real scorer
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_completion_scorer_with_user_profile(self):
        """score_evidence with user_profile applies completion adjustment."""
        from app.services.completion.scorer import score_evidence
        from app.services.completion.matcher import CompletionEvidence

        commitment = MagicMock()
        commitment.commitment_type = "send"
        commitment.target_entity = "alice"
        commitment.deliverable = "report"
        commitment.is_external_participant = False

        evidence = CompletionEvidence(
            source_item_id=_uid(),
            source_type="email",
            occurred_at=NOW,
            raw_text="Sent the report to Alice",
            normalized_text="Sent the report to Alice",
            matched_patterns=["deliverable_keyword"],
            actor_name="Bob",
            actor_email="bob@example.com",
            recipients=["alice@example.com"],
            has_attachment=True,
            attachment_metadata=None,
            thread_id=None,
            direction="outbound",
            evidence_strength="strong",
        )

        profile = _make_profile(threshold_adjustments={
            "completion_confidence_delta": -0.05,
            "feedback_count": 25,
        })

        # Without profile
        score_no_profile = score_evidence(commitment, evidence)
        # With profile
        score_with_profile = score_evidence(commitment, evidence, user_profile=profile)

        assert score_with_profile.completion_confidence < score_no_profile.completion_confidence

    def test_recompute_threshold_task_updates_profile(self):
        """Celery recompute task runs without error."""
        # This is a smoke test — full DB integration requires a real session
        from app.services.feedback_adapter import compute_threshold_adjustments

        rows = []
        for _ in range(25):
            row = MagicMock()
            row.action = "confirm"
            row.source_type = "email"
            row.trigger_class = "explicit_self_commitment"
            row.created_at = NOW
            rows.append(row)

        result = compute_threshold_adjustments(rows)
        assert result["feedback_count"] == 25
        assert isinstance(result["surfacing_threshold_delta"], float)
