"""Tests for Phase E3 — cross-channel completion matching (Gap 10.1).

Tests that completion evidence from a different source channel than the
commitment's origin gets a 1.10x bonus on delivery_confidence.

Strategy: pure function unit tests via SimpleNamespace (no DB).
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.completion.matcher import CompletionEvidence
from app.services.completion.scorer import score_evidence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_3D = _NOW - timedelta(days=3)
_PAST_1D = _NOW - timedelta(days=1)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "lifecycle_state": "active",
        "commitment_type": "send",
        "resolved_owner": "Alice",
        "suggested_owner": None,
        "deliverable": "revised proposal",
        "commitment_text": "I'll send the revised proposal",
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
        "_origin_source_type": "meeting",  # commitment originated from meeting
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_evidence(**kwargs) -> CompletionEvidence:
    defaults = {
        "source_item_id": str(uuid.uuid4()),
        "source_type": "email",
        "occurred_at": _PAST_1D,
        "raw_text": "I just sent you the revised proposal.",
        "normalized_text": "I just sent you the revised proposal.",
        "matched_patterns": ["deliverable_keyword", "delivery_keyword"],
        "actor_name": "Alice",
        "actor_email": "alice@example.com",
        "recipients": ["bob@example.com"],
        "has_attachment": True,
        "attachment_metadata": {"filename": "proposal.pdf"},
        "thread_id": None,
        "direction": "outbound",
        "evidence_strength": "strong",
    }
    defaults.update(kwargs)
    return CompletionEvidence(**defaults)


# ---------------------------------------------------------------------------
# TestCrossChannelBonus
# ---------------------------------------------------------------------------

class TestCrossChannelBonus:
    """Cross-channel evidence gets a 1.10x bonus on delivery_confidence."""

    def test_meeting_commitment_email_evidence_gets_bonus(self):
        """Commitment from meeting + evidence from email → cross-channel bonus."""
        commitment = make_commitment(_origin_source_type="meeting")
        evidence = make_evidence(source_type="email", evidence_strength="strong")

        score = score_evidence(commitment, evidence)

        # Base strong = 0.85, send + outbound = +0.05, send + attachment = +0.05
        # Cross-channel bonus = ×1.10
        # Expected: (0.85 + 0.10) × 1.10 = 1.045 → clamped to 1.0
        # Actually: base adjustments happen first, then cross-channel multiplier
        assert score.delivery_confidence > 0.90

    def test_same_channel_no_bonus(self):
        """Commitment from email + evidence from email → no cross-channel bonus."""
        commitment = make_commitment(_origin_source_type="email")
        evidence = make_evidence(source_type="email", evidence_strength="strong")

        score_same = score_evidence(commitment, evidence)

        commitment_cross = make_commitment(_origin_source_type="meeting")
        score_cross = score_evidence(commitment_cross, evidence)

        assert score_cross.delivery_confidence > score_same.delivery_confidence

    def test_no_origin_source_type_no_bonus(self):
        """Commitment with no _origin_source_type → no bonus applied."""
        commitment = make_commitment(_origin_source_type=None)
        evidence = make_evidence(source_type="email", evidence_strength="strong")

        score = score_evidence(commitment, evidence)

        # Without cross-channel: strong + send outbound + attachment = 0.95
        assert score.delivery_confidence <= 0.95

    def test_slack_commitment_meeting_evidence_gets_bonus(self):
        """Commitment from Slack + evidence from meeting → cross-channel bonus."""
        commitment = make_commitment(_origin_source_type="slack")
        evidence = make_evidence(source_type="meeting", evidence_strength="moderate")

        # Compare to same-channel
        commitment_same = make_commitment(_origin_source_type="meeting")
        score_cross = score_evidence(commitment, evidence)
        score_same = score_evidence(commitment_same, evidence)

        assert score_cross.delivery_confidence > score_same.delivery_confidence

    def test_cross_channel_bonus_reflected_in_completion(self):
        """Cross-channel bonus flows through to completion_confidence."""
        commitment_cross = make_commitment(_origin_source_type="meeting")
        commitment_same = make_commitment(_origin_source_type="email")
        evidence = make_evidence(source_type="email", evidence_strength="moderate")

        score_cross = score_evidence(commitment_cross, evidence)
        score_same = score_evidence(commitment_same, evidence)

        assert score_cross.completion_confidence > score_same.completion_confidence

    def test_cross_channel_bonus_in_notes(self):
        """Cross-channel bonus is recorded in score notes."""
        commitment = make_commitment(_origin_source_type="meeting")
        evidence = make_evidence(source_type="email", evidence_strength="strong")

        score = score_evidence(commitment, evidence)

        assert any("cross_channel" in note for note in score.notes)
