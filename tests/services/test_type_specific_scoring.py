"""Tests for Phase E3 — type-specific completion scoring (Gap 10.2).

Tests that different commitment types get differentiated scoring paths,
not just a multiplier. Each type has evidence characteristics that should
boost or penalize differently.

Strategy: pure function unit tests via SimpleNamespace (no DB).
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.completion.matcher import CompletionEvidence, find_matching_commitments
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
# Type A: send/deliver — attachment + outbound direction should boost
# ---------------------------------------------------------------------------

class TestSendTypeScoring:
    """Send/deliver type: delivery signal is strong with attachment."""

    def test_send_with_attachment_outbound_gets_full_bonus(self):
        """send + outbound + attachment → higher delivery than without attachment."""
        commitment = make_commitment(commitment_type="send")
        with_att = make_evidence(
            evidence_strength="strong",
            has_attachment=True,
            direction="outbound",
        )
        without_att = make_evidence(
            evidence_strength="strong",
            has_attachment=False,
            direction="outbound",
        )

        score_with = score_evidence(commitment, with_att)
        score_without = score_evidence(commitment, without_att)

        assert score_with.delivery_confidence > score_without.delivery_confidence

    def test_send_outbound_bonus(self):
        """send + outbound direction → bonus vs no direction."""
        commitment = make_commitment(commitment_type="send")
        outbound = make_evidence(
            evidence_strength="moderate",
            has_attachment=False,
            direction="outbound",
        )
        no_dir = make_evidence(
            evidence_strength="moderate",
            has_attachment=False,
            direction=None,
        )

        score_out = score_evidence(commitment, outbound)
        score_none = score_evidence(commitment, no_dir)

        assert score_out.delivery_confidence > score_none.delivery_confidence


# ---------------------------------------------------------------------------
# Type B: reply/follow_up — same-thread evidence should boost
# ---------------------------------------------------------------------------

class TestReplyTypeScoring:
    """Reply/follow_up type: thread continuity boosts scoring."""

    def test_follow_up_with_thread_gets_bonus(self):
        """follow_up + thread_continuity pattern → higher delivery than without."""
        commitment = make_commitment(commitment_type="follow_up")
        with_thread = make_evidence(
            evidence_strength="moderate",
            matched_patterns=["deliverable_keyword", "thread_continuity"],
        )
        without_thread = make_evidence(
            evidence_strength="moderate",
            matched_patterns=["deliverable_keyword"],
        )

        score_with = score_evidence(commitment, with_thread)
        score_without = score_evidence(commitment, without_thread)

        assert score_with.delivery_confidence > score_without.delivery_confidence


# ---------------------------------------------------------------------------
# Type C: review/investigate — harder to prove, higher bar
# ---------------------------------------------------------------------------

class TestReviewTypeScoring:
    """Review/investigate type: lower confidence unless explicit signals."""

    def test_review_strong_evidence_still_lower_than_send(self):
        """review + strong evidence → delivery < send + strong evidence."""
        review = make_commitment(commitment_type="review")
        send = make_commitment(commitment_type="send")
        evidence = make_evidence(evidence_strength="strong", has_attachment=False)

        review_score = score_evidence(review, evidence)
        send_score = score_evidence(send, evidence)

        assert review_score.delivery_confidence < send_score.delivery_confidence

    def test_review_completion_multiplier_applied(self):
        """review → completion_confidence = delivery × 0.70."""
        commitment = make_commitment(commitment_type="review")
        evidence = make_evidence(evidence_strength="strong", has_attachment=False)

        score = score_evidence(commitment, evidence)

        expected = score.delivery_confidence * 0.70
        assert score.completion_confidence == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Type D: create — requires artifact signal, hardest to prove
# ---------------------------------------------------------------------------

class TestCreateTypeScoring:
    """Create type: hardest to prove — requires artifact signal."""

    def test_create_without_artifact_gets_penalty(self):
        """create + no artifact signal → penalty applied to delivery."""
        commitment = make_commitment(commitment_type="create")
        no_artifact = make_evidence(
            evidence_strength="moderate",
            has_attachment=False,
            matched_patterns=["deliverable_keyword"],
        )

        score = score_evidence(commitment, no_artifact)

        # create without artifact: should have a penalty
        # baseline moderate = 0.65, create penalty = -0.10
        assert score.delivery_confidence <= 0.60

    def test_create_with_artifact_no_penalty(self):
        """create + attachment → no penalty (artifact requirement satisfied)."""
        commitment = make_commitment(commitment_type="create")
        with_artifact = make_evidence(
            evidence_strength="strong",
            has_attachment=True,
            matched_patterns=["deliverable_keyword"],
        )

        score = score_evidence(commitment, with_artifact)

        # create with artifact: no penalty, base strong = 0.85
        assert score.delivery_confidence >= 0.80

    def test_create_completion_multiplier(self):
        """create → uses lower completion multiplier."""
        commitment = make_commitment(commitment_type="create")
        evidence = make_evidence(evidence_strength="strong", has_attachment=True)

        score = score_evidence(commitment, evidence)

        # create should use a low multiplier like review
        assert score.completion_confidence < score.delivery_confidence


# ---------------------------------------------------------------------------
# Type E: coordinate/schedule — meeting/calendar signals boost
# ---------------------------------------------------------------------------

class TestCoordinateTypeScoring:
    """Coordinate/schedule type: benefits from scheduling keywords."""

    def test_coordinate_completion_multiplier(self):
        """coordinate → completion_confidence = delivery × 0.80."""
        commitment = make_commitment(commitment_type="coordinate")
        evidence = make_evidence(evidence_strength="strong", has_attachment=False)

        score = score_evidence(commitment, evidence)

        expected = score.delivery_confidence * 0.80
        assert score.completion_confidence == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Type-aware evidence strength in matcher
# ---------------------------------------------------------------------------

class TestTypeAwareEvidenceStrength:
    """Evidence strength should account for commitment type."""

    def test_create_type_without_artifact_weakened(self):
        """create commitment + moderate evidence + no artifact → evidence downgraded to weak."""
        item = types.SimpleNamespace(
            id=str(uuid.uuid4()),
            user_id="user-001",
            source_type="email",
            sender_name="Alice",
            sender_email="alice@example.com",
            content="I created the presentation deck.",
            content_normalized="I created the presentation deck.",
            has_attachment=False,
            attachment_metadata=None,
            recipients=["bob@example.com"],
            thread_id=None,
            direction="outbound",
            occurred_at=_PAST_1D,
            is_quoted_content=False,
            is_external_participant=False,
        )
        commitment = make_commitment(
            commitment_type="create",
            deliverable="presentation deck",
            commitment_text="I'll create the presentation deck",
            target_entity="bob@example.com",
        )

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 1
        _, evidence = results[0]
        # For create type, without attachment, evidence should be downgraded
        assert evidence.evidence_strength == "weak"
