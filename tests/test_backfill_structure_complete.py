"""Tests for structure_complete backfill migration.

The promoter now always sets structure_complete=True (line 185 of promoter.py),
but 373 commitments created before that fix have structure_complete=False with
all entity fields null. This migration backfills them.
"""
from __future__ import annotations

import types
import uuid
from decimal import Decimal

from app.services.surfacing_router import route


def _make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal commitment namespace for router tests."""
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Send the report",
        "commitment_text": "I'll send the report to Sarah",
        "context_type": "internal",
        "resolved_deadline": None,
        "vague_time_phrase": None,
        "deadline_candidates": None,
        "timing_ambiguity": None,
        "deliverable": None,
        "target_entity": None,
        "confidence_commitment": Decimal("0.8"),
        "confidence_owner": Decimal("0.6"),
        "confidence_actionability": Decimal("0.7"),
        "ownership_ambiguity": None,
        "deliverable_ambiguity": None,
        "resolved_owner": None,
        "suggested_owner": None,
        "observe_until": None,
        "lifecycle_state": "proposed",
        "candidate_commitments": [],
        "surfaced_as": None,
        "priority_score": None,
        "timing_strength": None,
        "business_consequence": None,
        "cognitive_burden": None,
        "confidence_for_surfacing": None,
        "surfacing_reason": None,
        "is_surfaced": False,
        "surfaced_at": None,
        "counterparty_resolved": None,
        "user_relationship": None,
        "structure_complete": False,
        "speech_act": None,
        "requester_name": None,
        "beneficiary_name": None,
        "requester_resolved": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestStructureCompleteBackfill:
    """Verify that backfilling structure_complete unblocks surfacing."""

    def test_false_structure_complete_blocks_surfacing(self):
        """Baseline: structure_complete=False blocks all surfacing."""
        c = _make_commitment(structure_complete=False)
        result = route(c)
        assert result.surface is None
        assert "structure incomplete" in result.reason

    def test_backfilled_true_unblocks_surfacing(self):
        """After backfill: structure_complete=True allows surfacing through the gate."""
        c = _make_commitment(
            structure_complete=True,
            confidence_commitment=Decimal("0.9"),
            confidence_actionability=Decimal("0.8"),
        )
        result = route(c)
        # Should NOT be blocked by the structure gate
        assert "structure incomplete" not in result.reason

    def test_backfilled_commitment_reaches_main_with_high_score(self):
        """A backfilled commitment with high confidence should route to main."""
        c = _make_commitment(
            structure_complete=True,
            confidence_commitment=Decimal("0.95"),
            confidence_actionability=Decimal("0.90"),
            user_relationship="mine",
            speech_act="self_commitment",
        )
        result = route(c)
        assert result.surface in ("main", "shortlist")
        assert result.priority_score >= 30

    def test_backfilled_commitment_with_no_speech_act_surfaces(self):
        """Commitments with speech_act=None (pre-backfill data) should still surface."""
        c = _make_commitment(
            structure_complete=True,
            speech_act=None,
            confidence_commitment=Decimal("0.85"),
            confidence_actionability=Decimal("0.80"),
        )
        result = route(c)
        # speech_act=None should not trigger the no-surface gate
        assert "no-surface speech act" not in result.reason
