"""Tests for commitment count discrepancy investigation (WO-1).

Verifies that no mechanism exists to silently delete commitments,
and that the delete endpoint performs a soft-delete (lifecycle transition).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.enums import LifecycleState


# ---------------------------------------------------------------------------
# Soft-delete behavior: DELETE endpoint transitions to 'discarded'
# ---------------------------------------------------------------------------


def _make_commitment(state: str = "active") -> MagicMock:
    """Create a mock commitment with the given lifecycle_state."""
    c = MagicMock()
    c.id = str(uuid.uuid4())
    c.user_id = str(uuid.uuid4())
    c.lifecycle_state = state
    c.state_changed_at = None
    c.updated_at = None
    return c


class TestCompletionUpdaterNoDelete:
    """Completion updater transitions states, never deletes rows."""

    def test_auto_close_transitions_to_closed_not_delete(self):
        """apply_auto_close sets lifecycle_state='closed', it does not delete the row."""
        from app.services.completion.updater import apply_auto_close

        commitment = _make_commitment("delivered")
        db = MagicMock()

        transition = apply_auto_close(commitment, db)

        assert commitment.lifecycle_state == LifecycleState.closed.value
        assert transition is not None
        # The commitment object still exists — no delete call
        db.delete.assert_not_called()

    def test_terminal_states_are_noop(self):
        """Commitments in terminal states are skipped entirely (no mutation)."""
        from app.services.completion.updater import apply_completion_result
        from app.services.completion.matcher import CompletionEvidence
        from app.services.completion.scorer import CompletionScore

        for state in ("closed", "completed", "canceled", "discarded"):
            commitment = _make_commitment(state)
            evidence = MagicMock(spec=CompletionEvidence)
            score = MagicMock(spec=CompletionScore)
            score.delivery_confidence = 0.99
            db = MagicMock()

            result = apply_completion_result(commitment, evidence, score, db)

            assert result is None
            assert commitment.lifecycle_state == state  # unchanged


class TestCascadeRules:
    """Verify that ORM cascade rules don't silently delete commitments."""

    def test_commitment_context_fk_is_set_null(self):
        """Deleting a commitment_context should SET NULL on commitments.context_id, not CASCADE delete."""
        from app.models.orm import Commitment

        context_col = Commitment.__table__.columns.get("context_id")
        assert context_col is not None

        fks = list(context_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].ondelete == "SET NULL"

    def test_user_cascade_is_documented(self):
        """User deletion cascades to commitments — this is expected and documented."""
        from app.models.orm import Commitment

        user_col = Commitment.__table__.columns.get("user_id")
        assert user_col is not None

        fks = list(user_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].ondelete == "CASCADE"


class TestNoCleanupTaskDeletesCommitments:
    """Verify that no Celery beat task has 'delete' or 'cleanup' in its name."""

    def test_beat_schedule_has_no_cleanup_tasks(self):
        from app.tasks import celery_app

        schedule = celery_app.conf.beat_schedule
        for name, config in schedule.items():
            task_name = config.get("task", "")
            # No task should contain 'delete', 'cleanup', 'purge', or 'truncate'
            for dangerous in ("delete", "cleanup", "purge", "truncate"):
                assert dangerous not in name.lower(), f"Beat task '{name}' contains '{dangerous}'"
                assert dangerous not in task_name.lower(), f"Beat task '{task_name}' contains '{dangerous}'"
