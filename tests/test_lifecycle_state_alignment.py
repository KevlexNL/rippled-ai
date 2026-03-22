"""Tests for WO-RIPPLED-LIFECYCLE-STATE-ALIGNMENT.

Covers:
- New enum values: in_progress, completed, canceled
- Lifecycle transition rules (allowed/disallowed transitions)
- Surfacing exclusions for completed and canceled states
- Updater: user-confirmed completed vs system-detected delivered
- Updater: cancellation signal → canceled transition
- No-op guards for terminal states (completed, canceled, closed, discarded)
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.models.enums import LifecycleState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_3D = _NOW - timedelta(days=3)


def _make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "lifecycle_state": "active",
        "commitment_type": "send",
        "resolved_owner": "Alice",
        "suggested_owner": None,
        "deliverable": "revised proposal",
        "commitment_text": "I'll send the revised proposal by Friday",
        "target_entity": "Bob",
        "observe_until": None,
        "created_at": _PAST_3D,
        "state_changed_at": _PAST_3D,
        "delivered_at": None,
        "auto_close_after_hours": 48,
        "confidence_delivery": None,
        "confidence_closure": None,
        "is_external_participant": False,
        "delivery_explanation": None,
        "_origin_thread_ids": [],
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_mock_db():
    added = []
    mock_db = MagicMock()
    mock_db.add.side_effect = lambda obj: added.append(obj)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mock_db._added = added
    return mock_db


# ---------------------------------------------------------------------------
# TestLifecycleStateEnum — new values exist
# ---------------------------------------------------------------------------

class TestLifecycleStateEnum:
    """Verify new enum values exist."""

    def test_in_progress_exists(self):
        assert LifecycleState.in_progress.value == "in_progress"

    def test_completed_exists(self):
        assert LifecycleState.completed.value == "completed"

    def test_canceled_exists(self):
        assert LifecycleState.canceled.value == "canceled"

    def test_all_spec_states_present(self):
        """All states from the spec + extensions are present."""
        expected = {
            "proposed", "needs_clarification", "active", "confirmed",
            "in_progress", "dormant", "delivered", "completed",
            "canceled", "closed", "discarded",
        }
        actual = {s.value for s in LifecycleState}
        assert expected == actual


# ---------------------------------------------------------------------------
# TestLifecycleTransitionRules — allowed/disallowed transitions
# ---------------------------------------------------------------------------

class TestLifecycleTransitionRules:
    """Verify transition rule enforcement."""

    def test_proposed_to_active_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("proposed", "active") is True

    def test_proposed_to_needs_clarification_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("proposed", "needs_clarification") is True

    def test_proposed_to_confirmed_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("proposed", "confirmed") is True

    def test_proposed_to_discarded_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("proposed", "discarded") is True

    def test_proposed_to_delivered_disallowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("proposed", "delivered") is False

    def test_active_to_in_progress_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("active", "in_progress") is True

    def test_confirmed_to_in_progress_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("confirmed", "in_progress") is True

    def test_active_to_delivered_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("active", "delivered") is True

    def test_in_progress_to_delivered_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("in_progress", "delivered") is True

    def test_in_progress_to_canceled_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("in_progress", "canceled") is True

    def test_in_progress_to_dormant_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("in_progress", "dormant") is True

    def test_delivered_to_completed_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("delivered", "completed") is True

    def test_delivered_to_closed_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("delivered", "closed") is True

    def test_delivered_to_active_allowed(self):
        """Reopening: delivered → active."""
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("delivered", "active") is True

    def test_completed_to_closed_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("completed", "closed") is True

    def test_completed_to_active_disallowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("completed", "active") is False

    def test_canceled_to_closed_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("canceled", "closed") is True

    def test_canceled_to_active_disallowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("canceled", "active") is False

    def test_closed_to_active_allowed(self):
        """Reopening: closed → active."""
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("closed", "active") is True

    def test_dormant_to_active_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("dormant", "active") is True

    def test_dormant_to_discarded_allowed(self):
        from app.services.lifecycle_transitions import is_transition_allowed
        assert is_transition_allowed("dormant", "discarded") is True

    def test_discarded_is_terminal(self):
        """Discarded is terminal — no transitions allowed out."""
        from app.services.lifecycle_transitions import is_transition_allowed
        for state in LifecycleState:
            if state.value != "discarded":
                assert is_transition_allowed("discarded", state.value) is False


# ---------------------------------------------------------------------------
# TestSurfacingExclusions — completed/canceled don't surface
# ---------------------------------------------------------------------------

class TestSurfacingExclusions:
    """Verify that completed, canceled states are excluded from surfacing."""

    def test_in_progress_included_in_active_states(self):
        from app.services.surfacing_runner import _ACTIVE_STATES
        assert "in_progress" in _ACTIVE_STATES

    def test_confirmed_included_in_active_states(self):
        from app.services.surfacing_runner import _ACTIVE_STATES
        assert "confirmed" in _ACTIVE_STATES

    def test_completed_excluded_from_active_states(self):
        from app.services.surfacing_runner import _ACTIVE_STATES
        assert "completed" not in _ACTIVE_STATES

    def test_canceled_excluded_from_active_states(self):
        from app.services.surfacing_runner import _ACTIVE_STATES
        assert "canceled" not in _ACTIVE_STATES


# ---------------------------------------------------------------------------
# TestUpdaterTerminalStates — completed/canceled are no-ops
# ---------------------------------------------------------------------------

class TestUpdaterTerminalStates:
    """Verify that completed and canceled are no-op states in the updater."""

    def test_completed_commitment_is_noop(self):
        from app.services.completion.updater import apply_completion_result
        from app.services.completion.matcher import CompletionEvidence
        from app.services.completion.scorer import CompletionScore

        commitment = _make_commitment(lifecycle_state="completed")
        evidence = CompletionEvidence(
            source_item_id=str(uuid.uuid4()),
            source_type="email",
            occurred_at=_PAST_3D,
            raw_text="sent it",
            normalized_text="sent it",
            matched_patterns=["delivery_keyword"],
            actor_name="Alice",
            actor_email="alice@example.com",
            recipients=["bob@example.com"],
            has_attachment=False,
            attachment_metadata=None,
            thread_id=None,
            direction="outbound",
            evidence_strength="strong",
        )
        score = CompletionScore(
            delivery_confidence=0.90,
            completion_confidence=0.85,
            evidence_strength="strong",
            recipient_match_confidence=0.90,
            artifact_match_confidence=0.90,
            closure_readiness_confidence=0.88,
            primary_pattern="delivery_keyword",
            notes=["strong evidence"],
        )
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        assert len(db._added) == 0
        assert result is None

    def test_canceled_commitment_is_noop(self):
        from app.services.completion.updater import apply_completion_result
        from app.services.completion.matcher import CompletionEvidence
        from app.services.completion.scorer import CompletionScore

        commitment = _make_commitment(lifecycle_state="canceled")
        evidence = CompletionEvidence(
            source_item_id=str(uuid.uuid4()),
            source_type="email",
            occurred_at=_PAST_3D,
            raw_text="sent it",
            normalized_text="sent it",
            matched_patterns=["delivery_keyword"],
            actor_name="Alice",
            actor_email="alice@example.com",
            recipients=["bob@example.com"],
            has_attachment=False,
            attachment_metadata=None,
            thread_id=None,
            direction="outbound",
            evidence_strength="strong",
        )
        score = CompletionScore(
            delivery_confidence=0.90,
            completion_confidence=0.85,
            evidence_strength="strong",
            recipient_match_confidence=0.90,
            artifact_match_confidence=0.90,
            closure_readiness_confidence=0.88,
            primary_pattern="delivery_keyword",
            notes=["strong evidence"],
        )
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        assert len(db._added) == 0
        assert result is None


# ---------------------------------------------------------------------------
# TestCancellationTransition
# ---------------------------------------------------------------------------

class TestCancellationTransition:
    """Verify apply_cancellation transitions active/in_progress → canceled."""

    def test_active_to_canceled_disallowed(self):
        """Per spec: only in_progress can transition to canceled."""
        from app.services.completion.updater import apply_cancellation

        commitment = _make_commitment(lifecycle_state="active")
        db = _make_mock_db()

        result = apply_cancellation(commitment, db, trigger_source_item_id="item-1")

        assert commitment.lifecycle_state == "active"
        assert result is None

    def test_in_progress_to_canceled(self):
        from app.services.completion.updater import apply_cancellation

        commitment = _make_commitment(lifecycle_state="in_progress")
        db = _make_mock_db()

        transition = apply_cancellation(commitment, db, trigger_source_item_id="item-1")

        assert commitment.lifecycle_state == "canceled"
        assert transition is not None

    def test_delivered_to_canceled_disallowed(self):
        """Cannot cancel a delivered commitment — should return None."""
        from app.services.completion.updater import apply_cancellation

        commitment = _make_commitment(lifecycle_state="delivered")
        db = _make_mock_db()

        result = apply_cancellation(commitment, db, trigger_source_item_id="item-1")

        assert commitment.lifecycle_state == "delivered"
        assert result is None


# ---------------------------------------------------------------------------
# TestUserConfirmedCompletion
# ---------------------------------------------------------------------------

class TestUserConfirmedCompletion:
    """Verify apply_user_confirmed_completion transitions delivered → completed."""

    def test_delivered_to_completed(self):
        from app.services.completion.updater import apply_user_confirmed_completion

        commitment = _make_commitment(lifecycle_state="delivered")
        db = _make_mock_db()

        transition = apply_user_confirmed_completion(commitment, db)

        assert commitment.lifecycle_state == "completed"
        assert transition is not None
        assert transition.to_state == "completed"

    def test_active_to_completed_disallowed(self):
        """Cannot complete an active commitment without delivery first."""
        from app.services.completion.updater import apply_user_confirmed_completion

        commitment = _make_commitment(lifecycle_state="active")
        db = _make_mock_db()

        result = apply_user_confirmed_completion(commitment, db)

        assert commitment.lifecycle_state == "active"
        assert result is None
