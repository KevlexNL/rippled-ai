"""Tests for Phase 05 — completion detection pipeline.

Strategy:
- Matcher: unit tests via SimpleNamespace (no DB required). Pure functions.
- Scorer: pure function unit tests.
- Updater: unit tests using MagicMock DB session.
- Detector: integration-style unit tests with mocked DB.
- AutoCloseSweep: unit tests with mocked DB.

All tests run without a real database.
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.completion.matcher import CompletionEvidence, find_matching_commitments
from app.services.completion.scorer import CompletionScore, score_evidence
from app.services.completion.updater import apply_auto_close, apply_completion_result
from app.services.completion.detector import run_auto_close_sweep, run_completion_detection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_3D = _NOW - timedelta(days=3)
_PAST_1D = _NOW - timedelta(days=1)
_PAST_2H = _NOW - timedelta(hours=2)
_FUTURE_1D = _NOW + timedelta(days=1)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    """Create a minimal Commitment-like namespace.

    Defaults represent an active commitment owned by Alice with a clear deliverable.
    """
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


def make_source_item(**kwargs) -> types.SimpleNamespace:
    """Create a minimal SourceItem-like namespace.

    Defaults represent an outbound email from Alice with a delivery confirmation.
    """
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "source_type": "email",
        "sender_name": "Alice",
        "sender_email": "alice@example.com",
        "content": "I just sent you the revised proposal as requested.",
        "content_normalized": "I just sent you the revised proposal as requested.",
        "has_attachment": True,
        "attachment_metadata": {"filename": "proposal.pdf"},
        "recipients": ["bob@example.com"],
        "thread_id": None,
        "direction": "outbound",
        "occurred_at": _PAST_1D,
        "is_quoted_content": False,
        "is_external_participant": False,
        "ingested_at": _PAST_2H,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_evidence(**kwargs) -> CompletionEvidence:
    """Create a CompletionEvidence for scorer/updater tests."""
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


def make_score(**kwargs) -> CompletionScore:
    """Create a CompletionScore for updater tests."""
    defaults = {
        "delivery_confidence": 0.85,
        "completion_confidence": 0.81,
        "evidence_strength": "strong",
        "recipient_match_confidence": 0.90,
        "artifact_match_confidence": 0.90,
        "closure_readiness_confidence": 0.88,
        "primary_pattern": "deliverable_keyword",
        "notes": ["strong evidence: deliverable keyword + attachment"],
    }
    defaults.update(kwargs)
    return CompletionScore(**defaults)


def _make_mock_db(existing_signal=None):
    """Build a MagicMock DB session.

    existing_signal: if None, signals do not exist (first write).
                     if set, simulates idempotency guard.
    """
    added_objects = []
    mock_db = MagicMock()
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_signal
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mock_db._added = added_objects
    return mock_db


# ---------------------------------------------------------------------------
# TestCompletionMatcher
# ---------------------------------------------------------------------------

class TestCompletionMatcher:
    """Unit tests for find_matching_commitments()."""

    def test_actor_deliverable_attachment_send_strong(self):
        """Actor match + deliverable keyword match + attachment → send commitment → strong evidence."""
        item = make_source_item(
            direction="outbound",
            has_attachment=True,
            content_normalized="I just sent you the revised proposal.",
        )
        commitment = make_commitment(
            commitment_type="send",
            deliverable="revised proposal",
            target_entity="bob@example.com",
            recipients=["bob@example.com"],
        )
        item.recipients = ["bob@example.com"]

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 1
        _, evidence = results[0]
        assert evidence.evidence_strength == "strong"

    def test_actor_only_no_deliverable_returns_no_match(self):
        """Actor match only, no deliverable overlap → 0 matches."""
        item = make_source_item(
            content="Hey, great meeting today.",
            content_normalized="Hey, great meeting today.",
            has_attachment=False,
            direction=None,
            recipients=[],  # no recipients → no recipient match
        )
        commitment = make_commitment(
            deliverable="quarterly report",
            commitment_text="I'll send the quarterly report",
            target_entity=None,  # no target → no recipient dimension
        )

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 0

    def test_actor_thread_continuity_no_deliverable_moderate(self):
        """Actor match + thread_id continuity, no deliverable → moderate evidence."""
        thread = "thread-xyz-123"
        item = make_source_item(
            thread_id=thread,
            content_normalized="Sent it over, check your inbox.",
        )
        commitment = make_commitment(
            deliverable="xyz document",
            commitment_text="I'll send the xyz document",
            _origin_thread_ids=[thread],
        )
        # Override content so deliverable keywords don't match
        item.content_normalized = "Sent it over, check your inbox."

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 1
        _, evidence = results[0]
        assert evidence.evidence_strength == "moderate"

    def test_quoted_content_flag_excluded(self):
        """source_item.is_quoted_content=True → excluded entirely, returns 0 matches."""
        item = make_source_item(is_quoted_content=True)
        commitment = make_commitment()

        results = find_matching_commitments(item, [commitment])

        assert results == []

    def test_email_quoted_lines_suppressed(self):
        """Delivery keywords appearing only in quoted email lines do not count."""
        # The quoted portion has the delivery keyword; the fresh content does not.
        # recipients=[] and target_entity=None removes recipient dimension to isolate suppression.
        item = make_source_item(
            content="Thanks for following up.\n\n> Original message:\n> I'll send the report by Friday.",
            content_normalized="Thanks for following up.\n\n> Original message:\n> I'll send the report by Friday.",
            is_quoted_content=False,
            has_attachment=False,
            direction="outbound",
            recipients=[],
        )
        commitment = make_commitment(
            deliverable="report",
            commitment_text="I'll send the report",
            target_entity=None,
        )

        results = find_matching_commitments(item, [commitment])

        # After suppression, "report" keyword only appears in quoted line → no deliverable match
        # No thread, no delivery keyword in fresh content → 0 matches
        assert len(results) == 0

    def test_multiple_commitments_same_actor_independent(self):
        """Multiple active commitments for same actor match independently per deliverable."""
        item = make_source_item(
            content_normalized="I just sent you the proposal document.",
        )
        commitment_a = make_commitment(
            id="commit-a",
            deliverable="proposal document",
            commitment_text="I'll send the proposal document",
            target_entity=None,
        )
        commitment_b = make_commitment(
            id="commit-b",
            deliverable="budget spreadsheet",
            commitment_text="I'll send the budget spreadsheet",
            target_entity=None,
        )

        results = find_matching_commitments(item, [commitment_a, commitment_b])

        matched_ids = [c.id for c, _ in results]
        assert "commit-a" in matched_ids
        assert "commit-b" not in matched_ids

    def test_no_owner_returns_no_match(self):
        """Commitment with no resolved_owner AND no suggested_owner → 0 matches."""
        item = make_source_item()
        commitment = make_commitment(resolved_owner=None, suggested_owner=None)

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 0

    def test_occurred_before_created_returns_no_match(self):
        """source_item.occurred_at before commitment.created_at → 0 matches."""
        item = make_source_item(occurred_at=_PAST_3D - timedelta(days=1))
        commitment = make_commitment(created_at=_PAST_3D)

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 0

    def test_observe_until_future_returns_no_match(self):
        """commitment.observe_until in the future → 0 matches (still in window)."""
        item = make_source_item()
        commitment = make_commitment(observe_until=_FUTURE_1D)

        results = find_matching_commitments(item, [commitment])

        assert len(results) == 0


# ---------------------------------------------------------------------------
# TestCompletionScorer
# ---------------------------------------------------------------------------

class TestCompletionScorer:
    """Unit tests for score_evidence()."""

    def test_strong_evidence_send_type(self):
        """Strong evidence + commitment_type=send → high delivery and completion confidence."""
        commitment = make_commitment(commitment_type="send", is_external_participant=False)
        evidence = make_evidence(evidence_strength="strong", direction="outbound", has_attachment=True)

        score = score_evidence(commitment, evidence)

        assert score.delivery_confidence >= 0.85
        assert score.completion_confidence >= 0.80

    def test_moderate_evidence_review_type_low_completion(self):
        """Moderate evidence + commitment_type=review → completion_confidence < 0.65."""
        commitment = make_commitment(commitment_type="review", is_external_participant=False)
        evidence = make_evidence(evidence_strength="moderate", has_attachment=False)

        score = score_evidence(commitment, evidence)

        assert score.completion_confidence < 0.65

    def test_weak_evidence_below_threshold(self):
        """Weak evidence → delivery_confidence < 0.65 (below transition threshold)."""
        commitment = make_commitment(commitment_type="send")
        evidence = make_evidence(evidence_strength="weak", has_attachment=False)

        score = score_evidence(commitment, evidence)

        assert score.delivery_confidence < 0.65

    def test_attachment_deliver_type_bonus(self):
        """has_attachment=True + commitment_type=deliver → +0.05 artifact bonus reflected."""
        commitment = make_commitment(commitment_type="deliver", is_external_participant=False)
        evidence_with = make_evidence(evidence_strength="moderate", has_attachment=True, direction="outbound")
        evidence_without = make_evidence(evidence_strength="moderate", has_attachment=False)

        score_with = score_evidence(commitment, evidence_with)
        score_without = score_evidence(commitment, evidence_without)

        assert score_with.delivery_confidence > score_without.delivery_confidence

    def test_external_commitment_non_outbound_penalty(self):
        """External commitment + direction != outbound → -0.15 penalty on email."""
        commitment = make_commitment(commitment_type="send", is_external_participant=True)
        evidence = make_evidence(
            evidence_strength="strong",
            source_type="email",
            direction="inbound",
            has_attachment=False,
        )

        score = score_evidence(commitment, evidence)

        # Penalty applied: 0.85 - 0.15 = 0.70
        assert score.delivery_confidence <= 0.72

    def test_no_target_entity_neutral_recipient_confidence(self):
        """No target_entity on commitment → recipient_match_confidence = 0.50 (neutral)."""
        commitment = make_commitment(target_entity=None)
        evidence = make_evidence(evidence_strength="strong")

        score = score_evidence(commitment, evidence)

        assert score.recipient_match_confidence == pytest.approx(0.50)

    def test_closure_readiness_formula(self):
        """closure_readiness = (delivery×0.5 + recipient×0.3 + artifact×0.2)."""
        commitment = make_commitment(target_entity=None)  # neutral recipient
        evidence = make_evidence(
            evidence_strength="strong",
            has_attachment=True,
        )

        score = score_evidence(commitment, evidence)

        expected = (
            score.delivery_confidence * 0.5
            + score.recipient_match_confidence * 0.3
            + score.artifact_match_confidence * 0.2
        )
        assert score.closure_readiness_confidence == pytest.approx(expected, abs=0.001)

    def test_investigate_type_strong_evidence(self):
        """commitment_type=investigate + strong evidence → completion_confidence = delivery × 0.70."""
        commitment = make_commitment(commitment_type="investigate", is_external_participant=False)
        evidence = make_evidence(evidence_strength="strong", has_attachment=False)

        score = score_evidence(commitment, evidence)

        # -0.10 for investigate: delivery = 0.85 - 0.10 = 0.75
        # completion = 0.75 * 0.70 = 0.525
        assert score.completion_confidence == pytest.approx(
            score.delivery_confidence * 0.70, abs=0.01
        )


# ---------------------------------------------------------------------------
# TestLifecycleUpdater
# ---------------------------------------------------------------------------

class TestLifecycleUpdater:
    """Unit tests for apply_completion_result()."""

    def test_qualifying_score_writes_signal_and_transition(self):
        """delivery_confidence=0.70 + evidence_strength=moderate → signal + active→delivered transition."""
        commitment = make_commitment(lifecycle_state="active")
        evidence = make_evidence(evidence_strength="moderate")
        score = make_score(
            delivery_confidence=0.70,
            evidence_strength="moderate",
            closure_readiness_confidence=0.75,
        )
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        # Signal written
        signal_types = [type(o).__name__ for o in db._added]
        assert "CommitmentSignal" in signal_types
        # Transition written
        assert "LifecycleTransition" in signal_types
        # Commitment state updated
        assert commitment.lifecycle_state == "delivered"
        # Return value is the transition
        assert result is not None

    def test_log_only_zone_writes_signal_no_transition(self):
        """delivery_confidence=0.50 (log-only zone) → CommitmentSignal written; no LifecycleTransition."""
        commitment = make_commitment(lifecycle_state="active")
        evidence = make_evidence(evidence_strength="weak")
        score = make_score(
            delivery_confidence=0.50,
            evidence_strength="weak",
            closure_readiness_confidence=0.40,
        )
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        signal_types = [type(o).__name__ for o in db._added]
        assert "CommitmentSignal" in signal_types
        assert "LifecycleTransition" not in signal_types
        assert commitment.lifecycle_state == "active"
        assert result is None

    def test_already_delivered_writes_signal_no_new_transition(self):
        """Commitment already delivered → CommitmentSignal written; NO new LifecycleTransition."""
        commitment = make_commitment(lifecycle_state="delivered")
        evidence = make_evidence(evidence_strength="moderate")
        score = make_score(delivery_confidence=0.70, evidence_strength="moderate")
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        signal_types = [type(o).__name__ for o in db._added]
        assert "CommitmentSignal" in signal_types
        assert "LifecycleTransition" not in signal_types
        assert result is None

    def test_already_closed_complete_noop(self):
        """Commitment already closed → no writes at all (complete no-op guard)."""
        commitment = make_commitment(lifecycle_state="closed")
        evidence = make_evidence(evidence_strength="strong")
        score = make_score(delivery_confidence=0.90, evidence_strength="strong")
        db = _make_mock_db()

        result = apply_completion_result(commitment, evidence, score, db)

        assert len(db._added) == 0
        assert result is None

    def test_delivered_at_set_on_active_to_delivered(self):
        """delivered_at is set when transitioning active → delivered."""
        commitment = make_commitment(lifecycle_state="active", delivered_at=None)
        evidence = make_evidence(evidence_strength="strong")
        score = make_score(delivery_confidence=0.85, evidence_strength="strong")
        db = _make_mock_db()

        apply_completion_result(commitment, evidence, score, db)

        assert commitment.delivered_at is not None
        assert commitment.lifecycle_state == "delivered"


# ---------------------------------------------------------------------------
# TestCompletionDetector
# ---------------------------------------------------------------------------

class TestCompletionDetector:
    """Integration-style unit tests for run_completion_detection()."""

    def test_source_item_matches_two_commitments(self):
        """source_item matching 2 commitments → both processed, 2 signals written."""
        source_item = make_source_item(
            content_normalized="I sent the proposal and the report.",
            direction="outbound",
            has_attachment=True,
        )
        commit_a = make_commitment(
            id="commit-a",
            deliverable="proposal",
            commitment_text="I'll send the proposal",
        )
        commit_b = make_commitment(
            id="commit-b",
            deliverable="report",
            commitment_text="I'll send the report",
        )
        source_item.recipients = ["bob@example.com"]
        commit_a.target_entity = "bob@example.com"
        commit_b.target_entity = "bob@example.com"

        added = []
        mock_db = MagicMock()
        mock_db.get.return_value = source_item
        mock_db.execute.return_value.scalars.return_value.all.return_value = [commit_a, commit_b]
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.add.side_effect = lambda obj: added.append(obj)

        result = run_completion_detection(source_item.id, mock_db)

        signal_types = [type(o).__name__ for o in added]
        assert signal_types.count("CommitmentSignal") == 2

    def test_no_matching_commitments_no_writes(self):
        """source_item matching 0 commitments → no writes, empty summary."""
        source_item = make_source_item(
            content="Hey, just checking in.",
            content_normalized="Hey, just checking in.",
            has_attachment=False,
            recipients=[],  # no recipient → no recipient match
        )
        commitment = make_commitment(
            deliverable="detailed technical report",
            target_entity=None,  # no target → no recipient dimension
        )

        mock_db = MagicMock()
        mock_db.get.return_value = source_item
        mock_db.execute.return_value.scalars.return_value.all.return_value = [commitment]
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = run_completion_detection(source_item.id, mock_db)

        mock_db.add.assert_not_called()
        assert result.get("transitions_made", 0) == 0

    def test_duplicate_sweep_idempotent(self):
        """Duplicate sweep (same source_item twice) → signal check prevents duplicate write."""
        source_item = make_source_item(
            content_normalized="I sent the proposal.",
            direction="outbound",
        )
        commitment = make_commitment(deliverable="proposal", commitment_text="I'll send the proposal")
        source_item.recipients = ["bob@example.com"]

        # Simulate: on second run, signal already exists
        added_first = []
        mock_db_first = MagicMock()
        mock_db_first.get.return_value = source_item
        mock_db_first.execute.return_value.scalars.return_value.all.return_value = [commitment]
        mock_db_first.execute.return_value.scalar_one_or_none.return_value = None  # no existing signal
        mock_db_first.add.side_effect = lambda obj: added_first.append(obj)

        run_completion_detection(source_item.id, mock_db_first)

        first_signal_count = [type(o).__name__ for o in added_first].count("CommitmentSignal")

        # Second sweep: signal already exists
        commitment2 = make_commitment(
            id=commitment.id,
            deliverable="proposal",
            commitment_text="I'll send the proposal",
            lifecycle_state=commitment.lifecycle_state,
        )
        added_second = []
        mock_db_second = MagicMock()
        mock_db_second.get.return_value = source_item
        mock_db_second.execute.return_value.scalars.return_value.all.return_value = [commitment2]
        mock_db_second.execute.return_value.scalar_one_or_none.return_value = MagicMock()  # signal exists
        mock_db_second.add.side_effect = lambda obj: added_second.append(obj)

        run_completion_detection(source_item.id, mock_db_second)

        second_signal_count = [type(o).__name__ for o in added_second].count("CommitmentSignal")

        assert first_signal_count == 1
        assert second_signal_count == 0  # idempotent: no duplicate signal


# ---------------------------------------------------------------------------
# TestAutoCloseSweep
# ---------------------------------------------------------------------------

class TestAutoCloseSweep:
    """Unit tests for run_auto_close_sweep()."""

    def _make_delivered_commitment(self, delivered_ago_hours, auto_close_hours, closure_readiness):
        return make_commitment(
            lifecycle_state="delivered",
            delivered_at=_NOW - timedelta(hours=delivered_ago_hours),
            auto_close_after_hours=auto_close_hours,
            confidence_closure=Decimal(str(closure_readiness)),
            state_changed_at=_NOW - timedelta(hours=delivered_ago_hours),
        )

    def test_eligible_commitment_transitions_to_closed(self):
        """Delivered 72h ago, 48h threshold, readiness=0.80 → transitions to closed."""
        commitment = self._make_delivered_commitment(
            delivered_ago_hours=72,
            auto_close_hours=48,
            closure_readiness=0.80,
        )

        added = []
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [commitment]
        mock_db.add.side_effect = lambda obj: added.append(obj)

        run_auto_close_sweep(mock_db)

        assert commitment.lifecycle_state == "closed"
        transition_types = [type(o).__name__ for o in added]
        assert "LifecycleTransition" in transition_types

    def test_not_old_enough_no_transition(self):
        """Delivered 12h ago, 48h threshold → no transition (not old enough)."""
        commitment = self._make_delivered_commitment(
            delivered_ago_hours=12,
            auto_close_hours=48,
            closure_readiness=0.80,
        )

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [commitment]

        run_auto_close_sweep(mock_db)

        assert commitment.lifecycle_state == "delivered"
        mock_db.add.assert_not_called()

    def test_low_closure_readiness_no_transition(self):
        """Delivered 72h ago, readiness=0.60 → no transition (confidence too low)."""
        commitment = self._make_delivered_commitment(
            delivered_ago_hours=72,
            auto_close_hours=48,
            closure_readiness=0.60,
        )

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [commitment]

        run_auto_close_sweep(mock_db)

        assert commitment.lifecycle_state == "delivered"
        mock_db.add.assert_not_called()

    def test_active_commitment_not_touched(self):
        """lifecycle_state=active → not touched by auto-close sweep."""
        commitment = make_commitment(lifecycle_state="active")

        mock_db = MagicMock()
        # Active commitments not returned by the sweep query
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        run_auto_close_sweep(mock_db)

        assert commitment.lifecycle_state == "active"
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# TestQuotedEmailSuppression
# ---------------------------------------------------------------------------

class TestQuotedEmailSuppression:
    """Dedicated tests for the quoted email suppression rule."""

    def test_is_quoted_content_flag_excluded(self):
        """source_item.is_quoted_content=True → excluded before matcher runs."""
        item = make_source_item(is_quoted_content=True)
        commitment = make_commitment()

        results = find_matching_commitments(item, [commitment])

        assert results == []

    def test_quoted_line_delivery_keyword_suppressed(self):
        """Delivery keyword only in '> ...' quoted line → does not count as evidence."""
        item = make_source_item(
            is_quoted_content=False,
            content="Thanks.\n\n> I'll send the report by Friday.",
            content_normalized="Thanks.\n\n> I'll send the report by Friday.",
            has_attachment=False,
            direction="outbound",
            recipients=[],  # no recipients → no recipient match (isolates suppression behavior)
        )
        commitment = make_commitment(
            deliverable="report",
            commitment_text="I'll send the report",
            target_entity=None,
        )

        results = find_matching_commitments(item, [commitment])

        # After suppression: "Thanks." → no delivery keyword, no deliverable keyword → 0 matches
        assert len(results) == 0

    def test_fresh_top_paragraph_counts_despite_quoted_chain(self):
        """Outbound email with quoted chain + fresh delivery confirmation → only fresh paragraph counts."""
        item = make_source_item(
            is_quoted_content=False,
            content="I've sent the report as promised.\n\n> Original:\n> Alice, can you send the report?",
            content_normalized="I've sent the report as promised.\n\n> Original:\n> Alice, can you send the report?",
            has_attachment=False,
            direction="outbound",
            recipients=["bob@example.com"],
        )
        commitment = make_commitment(
            deliverable="report",
            commitment_text="I'll send the report",
            target_entity="bob@example.com",
        )

        results = find_matching_commitments(item, [commitment])

        # Fresh line "I've sent the report as promised." matches deliverable
        assert len(results) == 1
