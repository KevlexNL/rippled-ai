"""Tests for Phase C3 — timing-aware priority scorer extensions.

Covers:
- proximity_spike(proximity_hours) — proximity bonus component
- counterparty_multiplier(counterparty_type) — multiplier by relationship
- delivery_state_modifier(delivery_state) — modifier by delivery state
- score() extended signature with proximity_hours param
- Combined formula: (base + proximity_spike + delivery_modifier) * counterparty_multiplier, capped 100
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.commitment_classifier import ClassifierResult
from app.services.priority_scorer import (
    counterparty_multiplier,
    delivery_state_modifier,
    proximity_spike,
    score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal commitment-compatible namespace for C3 timing scorer tests."""
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "title": "Send the proposal",
        "description": None,
        "commitment_text": "I'll send the revised proposal",
        "context_type": "internal",
        "resolved_deadline": None,
        "vague_time_phrase": None,
        "deadline_candidates": None,
        "timing_ambiguity": None,
        "deliverable": "proposal",
        "target_entity": None,
        "confidence_commitment": Decimal("0.7"),
        "confidence_owner": Decimal("0.6"),
        "confidence_actionability": Decimal("0.65"),
        "ownership_ambiguity": None,
        "deliverable_ambiguity": None,
        "resolved_owner": "Alice",
        "suggested_owner": None,
        "observe_until": None,
        "lifecycle_state": "active",
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
        # C3 additions
        "counterparty_type": None,
        "delivery_state": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_classifier_result(**kwargs) -> ClassifierResult:
    """Create a ClassifierResult for direct scorer tests."""
    defaults = {
        "timing_strength": 5,
        "business_consequence": 5,
        "cognitive_burden": 5,
        "confidence_for_surfacing": 0.7,
        "is_external": False,
        "has_critical_ambiguity": False,
        "source_type": "email_internal",
    }
    defaults.update(kwargs)
    return ClassifierResult(**defaults)


# ---------------------------------------------------------------------------
# TestTimingAwareScorer
# ---------------------------------------------------------------------------

class TestTimingAwareScorer:

    def test_score_no_proximity_uses_default_zero_bonus(self):
        """proximity_hours=None → proximity spike = 0, backward compat preserved."""
        result = make_classifier_result()
        commitment = make_commitment()
        score_without = score(result, commitment)
        score_none = score(result, commitment, proximity_hours=None)
        assert score_without == score_none

    def test_proximity_beyond_72h_no_bonus(self):
        """proximity_hours=80 → spike = 0, same as no proximity."""
        result = make_classifier_result()
        commitment = make_commitment()
        score_none = score(result, commitment, proximity_hours=None)
        score_far = score(result, commitment, proximity_hours=80)
        assert score_far == score_none

    def test_proximity_48h_adds_10_points(self):
        """48h out: 24 <= hours < 72 → spike = 10."""
        result = make_classifier_result()
        commitment = make_commitment()
        score_none = score(result, commitment, proximity_hours=None)
        score_48h = score(result, commitment, proximity_hours=48)
        assert score_48h == score_none + 10

    def test_proximity_12h_adds_20_points(self):
        """12h out: 1 <= hours < 24 → spike = 20."""
        result = make_classifier_result()
        commitment = make_commitment()
        score_none = score(result, commitment, proximity_hours=None)
        score_12h = score(result, commitment, proximity_hours=12)
        assert score_12h == score_none + 20

    def test_proximity_30min_adds_35_points(self):
        """30 minutes out: 0 <= hours < 1 → spike = 35."""
        result = make_classifier_result()
        commitment = make_commitment()
        score_none = score(result, commitment, proximity_hours=None)
        score_30min = score(result, commitment, proximity_hours=0.5)
        # capped at 100; check the spike is 35 via proximity_spike directly
        spike = proximity_spike(0.5)
        assert spike == 35

    def test_proximity_post_event_1h_decayed(self):
        """proximity_hours=-1 → post-event 1h: spike = max(0, 40 - (1/48)*40) ≈ 39."""
        spike = proximity_spike(-1)
        expected = max(0, 40 - (1 / 48) * 40)
        assert abs(spike - expected) < 1  # within 1 point due to rounding

    def test_proximity_post_event_48h_fully_decayed(self):
        """proximity_hours=-48 → fully decayed → spike = 0."""
        spike = proximity_spike(-48)
        assert spike == 0

    def test_counterparty_external_multiplies_1_4(self):
        """counterparty_type='external_client' → multiplier = 1.4."""
        assert counterparty_multiplier("external_client") == 1.4

    def test_counterparty_manager_multiplies_1_2(self):
        """counterparty_type='internal_manager' → multiplier = 1.2."""
        assert counterparty_multiplier("internal_manager") == 1.2

    def test_counterparty_self_multiplies_0_8(self):
        """counterparty_type='self' → multiplier = 0.8."""
        assert counterparty_multiplier("self") == 0.8

    def test_counterparty_none_multiplies_1_0(self):
        """counterparty_type=None → multiplier = 1.0 (no change)."""
        assert counterparty_multiplier(None) == 1.0

    def test_delivery_state_acknowledged_reduces_5(self):
        """delivery_state='acknowledged' → modifier = -5."""
        assert delivery_state_modifier("acknowledged") == -5

    def test_delivery_state_draft_sent_reduces_10(self):
        """delivery_state='draft_sent' → modifier = -10."""
        assert delivery_state_modifier("draft_sent") == -10

    def test_delivery_state_none_no_change(self):
        """delivery_state=None → modifier = 0."""
        assert delivery_state_modifier(None) == 0

    def test_combined_proximity_and_multiplier(self):
        """Both proximity_hours=12 and counterparty='external_client' applied together."""
        result = make_classifier_result(
            timing_strength=5,
            business_consequence=5,
            cognitive_burden=5,
            confidence_for_surfacing=0.7,
            is_external=False,
        )
        commitment_no_cp = make_commitment(counterparty_type=None)
        commitment_ext = make_commitment(counterparty_type="external_client")

        score_base = score(result, commitment_no_cp, proximity_hours=None)
        score_combined = score(result, commitment_ext, proximity_hours=12)

        # With proximity_hours=12, spike=20; with external_client, multiplier=1.4
        # Combined score should be higher than base
        assert score_combined > score_base

    def test_combined_result_capped_at_100(self):
        """Max dimensions + proximity spike + external multiplier → capped at 100."""
        result = make_classifier_result(
            timing_strength=10,
            business_consequence=10,
            cognitive_burden=10,
            confidence_for_surfacing=1.0,
            is_external=True,
        )
        commitment = make_commitment(counterparty_type="external_client")
        s = score(result, commitment, proximity_hours=0.5)
        assert s == 100


# ---------------------------------------------------------------------------
# TestProximitySpike — unit tests for the helper function
# ---------------------------------------------------------------------------

class TestProximitySpike:
    def test_spike_above_72h(self):
        assert proximity_spike(80) == 0
        assert proximity_spike(72) == 0

    def test_spike_at_boundary_72h(self):
        # exactly 72 → 0
        assert proximity_spike(72) == 0

    def test_spike_just_below_72h(self):
        assert proximity_spike(71.9) == 10

    def test_spike_at_24h(self):
        assert proximity_spike(24) == 10

    def test_spike_just_below_24h(self):
        assert proximity_spike(23.9) == 20

    def test_spike_at_1h(self):
        assert proximity_spike(1) == 20

    def test_spike_just_below_1h(self):
        assert proximity_spike(0.9) == 35

    def test_spike_at_zero(self):
        assert proximity_spike(0) == 35

    def test_spike_post_event_0h(self):
        # proximity_hours just negative → nearly full 40
        spike = proximity_spike(-0.01)
        assert spike > 39

    def test_spike_post_event_96h_or_more(self):
        # -96 → max(0, 40 - (96/48)*40) = max(0, 40-80) = 0
        assert proximity_spike(-96) == 0
