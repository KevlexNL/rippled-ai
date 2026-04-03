"""Tests for Phase E3 — cross-source merge detector.

Strategy:
- find_merge_candidates: pure function unit tests via SimpleNamespace (no DB).
- execute_merge: unit tests with MagicMock DB session.

All tests run without a real database.
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from app.services.detection.merge_detector import (
    MergeConfig,
    execute_merge,
    find_merge_candidates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_1H = _NOW - timedelta(hours=1)
_PAST_2H = _NOW - timedelta(hours=2)
_PAST_5D = _NOW - timedelta(days=5)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal Commitment-like namespace for merge tests."""
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
        "created_at": _PAST_2H,
        "confidence_commitment": Decimal("0.80"),
        "context_tags": ["meeting"],
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# TestFindMergeCandidates
# ---------------------------------------------------------------------------

class TestFindMergeCandidates:
    """Unit tests for find_merge_candidates()."""

    def test_same_actor_same_deliverable_close_time_merges(self):
        """Same actor + similar deliverable + close timeframe → merge candidate."""
        new = make_commitment(
            id="new-1",
            resolved_owner="Alice",
            deliverable="revised proposal",
            commitment_text="Send the revised proposal to Bob",
            created_at=_PAST_1H,
        )
        existing = make_commitment(
            id="existing-1",
            resolved_owner="Alice",
            deliverable="revised proposal",
            commitment_text="I'll send the revised proposal by Friday",
            created_at=_PAST_2H,
        )

        candidates = find_merge_candidates(new, [existing])

        assert len(candidates) == 1
        assert candidates[0].id == "existing-1"

    def test_different_actor_no_merge(self):
        """Different actor → no merge candidate."""
        new = make_commitment(resolved_owner="Alice", deliverable="proposal")
        existing = make_commitment(resolved_owner="Bob", deliverable="proposal")

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_different_deliverable_no_merge(self):
        """Same actor but entirely different deliverable → no merge."""
        new = make_commitment(
            deliverable="quarterly report",
            commitment_text="I'll send the quarterly report",
        )
        existing = make_commitment(
            deliverable="budget spreadsheet",
            commitment_text="I'll send the budget spreadsheet",
        )

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_too_far_apart_in_time_no_merge(self):
        """Same actor + same deliverable but >72h apart → no merge."""
        new = make_commitment(
            created_at=_NOW,
            deliverable="proposal",
        )
        existing = make_commitment(
            created_at=_NOW - timedelta(hours=73),
            deliverable="proposal",
        )

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_within_custom_time_window_merges(self):
        """Custom timeframe_hours=120 allows wider window."""
        new = make_commitment(
            created_at=_NOW,
            deliverable="proposal",
        )
        existing = make_commitment(
            created_at=_NOW - timedelta(hours=100),
            deliverable="proposal",
        )

        config = MergeConfig(timeframe_hours=120)
        candidates = find_merge_candidates(new, [existing], config=config)

        assert len(candidates) == 1

    def test_discarded_commitment_skipped(self):
        """Existing commitment with lifecycle_state='discarded' → skipped."""
        new = make_commitment(deliverable="proposal")
        existing = make_commitment(
            deliverable="proposal",
            lifecycle_state="discarded",
        )

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_same_id_skipped(self):
        """New commitment cannot merge with itself."""
        commit = make_commitment(id="same-id")

        candidates = find_merge_candidates(commit, [commit])

        assert candidates == []

    def test_different_commitment_type_no_merge(self):
        """Same actor + same deliverable but different type → no merge."""
        new = make_commitment(
            commitment_type="send",
            deliverable="proposal",
        )
        existing = make_commitment(
            commitment_type="review",
            deliverable="proposal",
        )

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_picks_highest_confidence_when_multiple(self):
        """Multiple merge candidates → returned sorted by confidence (highest first)."""
        new = make_commitment(
            created_at=_NOW,
            deliverable="proposal",
        )
        low = make_commitment(
            id="low",
            deliverable="proposal",
            confidence_commitment=Decimal("0.60"),
            created_at=_PAST_1H,
        )
        high = make_commitment(
            id="high",
            deliverable="proposal",
            confidence_commitment=Decimal("0.90"),
            created_at=_PAST_2H,
        )

        candidates = find_merge_candidates(new, [low, high])

        assert len(candidates) == 2
        assert candidates[0].id == "high"  # highest confidence first

    def test_actor_match_case_insensitive(self):
        """Actor matching is case-insensitive."""
        new = make_commitment(resolved_owner="ALICE", deliverable="proposal")
        existing = make_commitment(resolved_owner="alice", deliverable="proposal")

        candidates = find_merge_candidates(new, [existing])

        assert len(candidates) == 1

    def test_recipient_mismatch_no_merge(self):
        """Same actor + same deliverable but different target → no merge."""
        new = make_commitment(
            deliverable="proposal",
            target_entity="Charlie",
        )
        existing = make_commitment(
            deliverable="proposal",
            target_entity="Dana",
        )

        candidates = find_merge_candidates(new, [existing])

        assert candidates == []

    def test_both_no_recipient_still_merges(self):
        """Same actor + deliverable, both with no target_entity → can merge."""
        new = make_commitment(deliverable="proposal", target_entity=None)
        existing = make_commitment(deliverable="proposal", target_entity=None)

        candidates = find_merge_candidates(new, [existing])

        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# TestExecuteMerge
# ---------------------------------------------------------------------------

class TestExecuteMerge:
    """Unit tests for execute_merge()."""

    def test_duplicate_marked_discarded_with_merge_reason(self):
        """Duplicate commitment gets lifecycle_state='discarded' + discard reason encoding."""
        canonical = make_commitment(id="canonical-1", confidence_commitment=Decimal("0.90"))
        duplicate = make_commitment(id="duplicate-1", confidence_commitment=Decimal("0.70"))

        db = MagicMock()
        # Simulate signals query returning one signal for the duplicate
        mock_signal = types.SimpleNamespace(
            id="sig-1",
            commitment_id="duplicate-1",
            source_item_id="item-1",
            user_id="user-001",
            signal_role="origin",
            confidence=Decimal("0.70"),
            interpretation_note="original",
        )
        db.execute.return_value.scalars.return_value.all.return_value = [mock_signal]
        added = []
        db.add.side_effect = lambda obj: added.append(obj)

        execute_merge(canonical, duplicate, db)

        assert duplicate.lifecycle_state == "discarded"
        assert "merged::" in duplicate.discard_reason
        assert canonical.id in duplicate.discard_reason

    def test_signals_relinked_to_canonical(self):
        """Signals from duplicate are re-linked to canonical via new CommitmentSignal rows."""
        canonical = make_commitment(id="canonical-1")
        duplicate = make_commitment(id="duplicate-1")

        mock_signal = types.SimpleNamespace(
            id="sig-1",
            commitment_id="duplicate-1",
            source_item_id="item-1",
            user_id="user-001",
            signal_role="origin",
            confidence=Decimal("0.70"),
            interpretation_note="original",
        )
        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = [mock_signal]
        added = []
        db.add.side_effect = lambda obj: added.append(obj)

        execute_merge(canonical, duplicate, db)

        # A new CommitmentSignal should be added linking to canonical
        signal_adds = [o for o in added if type(o).__name__ == "CommitmentSignal"]
        assert len(signal_adds) == 1
        assert signal_adds[0].commitment_id == "canonical-1"
        assert signal_adds[0].source_item_id == "item-1"

    def test_context_tags_merged(self):
        """Context tags from duplicate are merged into canonical."""
        canonical = make_commitment(id="canonical-1", context_tags=["meeting"])
        duplicate = make_commitment(id="duplicate-1", context_tags=["email"])

        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        db.add.side_effect = lambda obj: None

        execute_merge(canonical, duplicate, db)

        assert "meeting" in canonical.context_tags
        assert "email" in canonical.context_tags

    def test_no_signals_still_marks_discarded(self):
        """Duplicate with no signals still gets marked as discarded."""
        canonical = make_commitment(id="canonical-1")
        duplicate = make_commitment(id="duplicate-1")

        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        db.add.side_effect = lambda obj: None

        execute_merge(canonical, duplicate, db)

        assert duplicate.lifecycle_state == "discarded"
        assert "merged::" in duplicate.discard_reason
