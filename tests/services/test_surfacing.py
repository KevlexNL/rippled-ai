"""Tests for Phase 06 — surfacing pipeline.

Covers:
- priority_scorer: score() with all dimensions
- observation_window: is_observable(), should_surface_early()
- surfacing_router: route() routing decisions
- surfacing_runner: run_surfacing_sweep() batch task logic
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.commitment_classifier import ClassifierResult
from app.services.observation_window import (
    default_window_hours,
    is_observable,
    should_surface_early,
)
from app.services.priority_scorer import score
from app.services.surfacing_router import RoutingResult, route
from app.services.surfacing_runner import run_surfacing_sweep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_PAST_3D = _NOW - timedelta(days=3)
_PAST_2H = _NOW - timedelta(hours=2)
_FUTURE_1D = _NOW + timedelta(days=1)
_FUTURE_2H = _NOW + timedelta(hours=2)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    """Minimal commitment-compatible namespace for surfacing tests."""
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
        "speech_act": None,
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
# TestPriorityScorer
# ---------------------------------------------------------------------------

class TestPriorityScorer:
    def test_external_bonus_adds_25(self):
        internal = make_classifier_result(is_external=False)
        external = make_classifier_result(is_external=True)
        commitment = make_commitment()
        diff = score(external, commitment) - score(internal, commitment)
        assert diff == 25

    def test_zero_dimensions_produces_low_score(self):
        result = make_classifier_result(
            timing_strength=0,
            business_consequence=0,
            cognitive_burden=0,
            confidence_for_surfacing=0.0,
            is_external=False,
        )
        commitment = make_commitment(observe_until=None)
        assert score(result, commitment) == 0

    def test_max_dimensions_produces_high_score(self):
        result = make_classifier_result(
            timing_strength=10,
            business_consequence=10,
            cognitive_burden=10,
            confidence_for_surfacing=1.0,
            is_external=True,
        )
        commitment = make_commitment()
        s = score(result, commitment)
        assert s >= 90

    def test_score_bounded_0_100(self):
        result = make_classifier_result(
            timing_strength=10,
            business_consequence=10,
            cognitive_burden=10,
            confidence_for_surfacing=1.0,
            is_external=True,
        )
        commitment = make_commitment(observe_until=_PAST_3D)  # staleness bonus
        s = score(result, commitment)
        assert 0 <= s <= 100

    def test_low_confidence_suppression_below_threshold(self):
        """confidence_for_surfacing < 0.3 triggers 50% penalty."""
        normal = make_classifier_result(confidence_for_surfacing=0.3)
        suppressed = make_classifier_result(confidence_for_surfacing=0.15)
        commitment = make_commitment()
        assert score(suppressed, commitment) < score(normal, commitment)

    def test_staleness_bonus_increases_score(self):
        result = make_classifier_result()
        fresh = make_commitment(observe_until=None, lifecycle_state="active")
        stale = make_commitment(observe_until=_PAST_3D, lifecycle_state="active")
        assert score(result, stale) > score(result, fresh)

    def test_staleness_bonus_not_applied_if_window_open(self):
        result = make_classifier_result()
        in_window = make_commitment(observe_until=_FUTURE_1D, lifecycle_state="active")
        no_window = make_commitment(observe_until=None, lifecycle_state="active")
        # In-window commitment should NOT get staleness bonus
        assert score(result, in_window) == score(result, no_window)

    def test_timing_dimension_scales_correctly(self):
        """timing_strength 10 → contributes 20 points."""
        result_max = make_classifier_result(timing_strength=10, is_external=False,
                                            business_consequence=0, cognitive_burden=0,
                                            confidence_for_surfacing=0.0)
        result_zero = make_classifier_result(timing_strength=0, is_external=False,
                                              business_consequence=0, cognitive_burden=0,
                                              confidence_for_surfacing=0.0)
        commitment = make_commitment()
        assert score(result_max, commitment) - score(result_zero, commitment) == 20

    def test_consequence_dimension_scales_correctly(self):
        """business_consequence 10 → contributes 20 points."""
        result_max = make_classifier_result(business_consequence=10, timing_strength=0,
                                            is_external=False, cognitive_burden=0,
                                            confidence_for_surfacing=0.0)
        result_zero = make_classifier_result(business_consequence=0, timing_strength=0,
                                              is_external=False, cognitive_burden=0,
                                              confidence_for_surfacing=0.0)
        commitment = make_commitment()
        assert score(result_max, commitment) - score(result_zero, commitment) == 20


# ---------------------------------------------------------------------------
# TestObservationWindow
# ---------------------------------------------------------------------------

class TestObservationWindow:
    def test_no_observe_until_not_observable(self):
        commitment = make_commitment(observe_until=None)
        assert is_observable(commitment) is False

    def test_future_observe_until_is_observable(self):
        commitment = make_commitment(observe_until=_FUTURE_1D)
        assert is_observable(commitment) is True

    def test_past_observe_until_not_observable(self):
        commitment = make_commitment(observe_until=_PAST_2H)
        assert is_observable(commitment) is False

    def test_naive_datetime_handled(self):
        """Naive datetimes in tests should not raise errors."""
        naive_past = datetime.utcnow() - timedelta(hours=5)
        commitment = make_commitment(observe_until=naive_past)
        # Should not raise; past naive datetime → not observable
        assert is_observable(commitment) is False

    def test_should_surface_early_requires_all_three(self):
        """Early surface requires: external + resolved_deadline + high confidence."""
        # All three present
        commitment = make_commitment(
            observe_until=_FUTURE_1D,
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.80"),
        )
        assert should_surface_early(commitment) is True

    def test_should_surface_early_not_if_internal(self):
        commitment = make_commitment(
            observe_until=_FUTURE_1D,
            context_type="internal",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.90"),
        )
        assert should_surface_early(commitment) is False

    def test_should_surface_early_not_if_no_deadline(self):
        commitment = make_commitment(
            observe_until=_FUTURE_1D,
            context_type="external",
            resolved_deadline=None,
            confidence_commitment=Decimal("0.90"),
        )
        assert should_surface_early(commitment) is False

    def test_should_surface_early_not_if_low_confidence(self):
        commitment = make_commitment(
            observe_until=_FUTURE_1D,
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.60"),  # below 0.75
        )
        assert should_surface_early(commitment) is False

    def test_should_not_surface_early_if_already_past_window(self):
        """should_surface_early only applies during the window."""
        commitment = make_commitment(
            observe_until=_PAST_2H,  # window already passed
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.90"),
        )
        assert should_surface_early(commitment) is False

    def test_default_window_slack_internal(self):
        hours = default_window_hours("slack", external=False)
        assert 2.0 <= hours <= 4.0  # ~2 working hours

    def test_default_window_email_external_larger_than_internal(self):
        internal = default_window_hours("email", external=False)
        external = default_window_hours("email", external=True)
        assert external > internal

    def test_default_window_unknown_source_returns_fallback(self):
        hours = default_window_hours("unknown_source", external=False)
        assert hours > 0


# ---------------------------------------------------------------------------
# TestSurfacingRouter
# ---------------------------------------------------------------------------

class TestSurfacingRouter:
    def test_in_window_returns_none(self):
        commitment = make_commitment(observe_until=_FUTURE_1D)
        result = route(commitment)
        assert result.surface is None
        assert "observation window" in result.reason

    def test_high_score_external_routes_to_main(self):
        commitment = make_commitment(
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            vague_time_phrase="by Friday",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface == "main"

    def test_medium_score_internal_routes_to_shortlist(self):
        commitment = make_commitment(
            context_type="internal",
            confidence_commitment=Decimal("0.65"),
            confidence_owner=Decimal("0.60"),
            confidence_actionability=Decimal("0.60"),
            vague_time_phrase="by Friday",
            deliverable="brief update",
            observe_until=None,
        )
        result = route(commitment)
        # Medium-score internal → shortlist or None depending on total
        assert result.surface in ("shortlist", None)

    def test_promoted_internal_commitment_surfaces(self):
        """A typical promoted Tier 2 commitment should surface on shortlist.

        This simulates the most common case: internal commitment detected by
        pattern matching, with confidence_commitment=0.60, actionability=0.60,
        no explicit timing, but with a deliverable and cognitive burden phrases.
        """
        commitment = make_commitment(
            context_type="internal",
            confidence_commitment=Decimal("0.60"),
            confidence_owner=None,
            confidence_actionability=Decimal("0.60"),
            timing_ambiguity=None,
            deliverable="revised proposal",
            commitment_text="I'll send the revised proposal",
            structure_complete=True,
            speech_act="self_commitment",
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is not None, (
            f"Expected promoted commitment to surface, got None "
            f"(score={result.priority_score}, reason={result.reason})"
        )

    def test_critical_ambiguity_routes_to_clarifications(self):
        commitment = make_commitment(
            ownership_ambiguity="missing",
            context_type="external",
            confidence_commitment=Decimal("0.8"),
            confidence_actionability=Decimal("0.8"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface == "clarifications"

    def test_low_score_routes_to_none(self):
        commitment = make_commitment(
            context_type="internal",
            confidence_commitment=Decimal("0.1"),
            confidence_owner=Decimal("0.1"),
            confidence_actionability=Decimal("0.1"),
            timing_ambiguity="missing",
            deliverable=None,
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None

    def test_returns_routing_result_dataclass(self):
        commitment = make_commitment()
        result = route(commitment)
        assert isinstance(result, RoutingResult)
        assert 0 <= result.priority_score <= 100
        assert isinstance(result.reason, str)

    def test_early_surface_bypasses_window(self):
        """External + deadline + high confidence → surface even if in window."""
        commitment = make_commitment(
            observe_until=_FUTURE_1D,  # in window
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.85"),
            confidence_owner=Decimal("0.80"),
            confidence_actionability=Decimal("0.80"),
            vague_time_phrase="by tomorrow",
        )
        result = route(commitment)
        # Should NOT be held by the window
        assert result.surface != "observation_window_hold"
        # With these scores, should route somewhere meaningful
        assert result.surface in ("main", "shortlist", "clarifications")

    def test_critical_ambiguity_below_min_score_stays_none(self):
        """Critical ambiguity but extremely low score → not routed to clarifications."""
        commitment = make_commitment(
            ownership_ambiguity="missing",
            context_type="internal",
            confidence_commitment=Decimal("0.05"),
            confidence_owner=Decimal("0.05"),
            confidence_actionability=Decimal("0.05"),
            timing_ambiguity="missing",
            deliverable=None,
            observe_until=None,
        )
        result = route(commitment)
        # Score will be near 0 → below _CLARIFICATION_MIN_SCORE
        assert result.surface is None


# ---------------------------------------------------------------------------
# TestSurfacingRunner
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TestSurfacingRouter — speech_act routing (WO-RIPPLED-SPEECH-ACT-CLASSIFICATION)
# ---------------------------------------------------------------------------

class TestSurfacingRouterSpeechAct:
    """Speech act classification affects surfacing routing decisions."""

    def test_request_without_acceptance_routes_to_none(self):
        """request speech_act → watching relationship → not surfaced."""
        commitment = make_commitment(
            speech_act="request",
            user_relationship="watching",
            context_type="internal",
            confidence_commitment=Decimal("0.8"),
            confidence_actionability=Decimal("0.8"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None
        assert "watching" in result.reason

    def test_self_commitment_surfaces_normally(self):
        """self_commitment with high scores should surface to main."""
        commitment = make_commitment(
            speech_act="self_commitment",
            user_relationship="mine",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface == "main"

    def test_status_update_not_surfaced(self):
        """status_update speech_act → never surfaced, regardless of score."""
        commitment = make_commitment(
            speech_act="status_update",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None
        assert "status_update" in result.reason or "no-surface speech act" in result.reason

    def test_informational_not_surfaced(self):
        """informational speech_act → never surfaced."""
        commitment = make_commitment(
            speech_act="informational",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_actionability=Decimal("0.9"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None

    def test_cancellation_not_surfaced(self):
        """cancellation speech_act → not surfaced (lifecycle handler manages it)."""
        commitment = make_commitment(
            speech_act="cancellation",
            context_type="internal",
            confidence_commitment=Decimal("0.8"),
            confidence_actionability=Decimal("0.8"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None

    def test_completion_not_surfaced(self):
        """completion speech_act → not surfaced (completion service manages it)."""
        commitment = make_commitment(
            speech_act="completion",
            context_type="internal",
            confidence_commitment=Decimal("0.8"),
            confidence_actionability=Decimal("0.8"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None

    def test_decline_not_surfaced(self):
        """decline speech_act → not surfaced."""
        commitment = make_commitment(
            speech_act="decline",
            context_type="internal",
            confidence_commitment=Decimal("0.8"),
            confidence_actionability=Decimal("0.8"),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface is None

    def test_acceptance_surfaces_normally(self):
        """acceptance speech_act should surface like a self_commitment."""
        commitment = make_commitment(
            speech_act="acceptance",
            user_relationship="mine",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface in ("main", "shortlist")

    def test_reassignment_surfaces_normally(self):
        """reassignment speech_act should surface normally."""
        commitment = make_commitment(
            speech_act="reassignment",
            user_relationship="mine",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface in ("main", "shortlist")

    def test_none_speech_act_surfaces_normally(self):
        """None speech_act (backward compat) should surface normally."""
        commitment = make_commitment(
            speech_act=None,
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
            observe_until=None,
        )
        result = route(commitment)
        assert result.surface == "main"


class TestSurfacingRunner:
    def _make_mock_db(self, commitments: list) -> MagicMock:
        added = []
        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = commitments
        db.add.side_effect = lambda obj: added.append(obj)
        db._added = added
        return db

    def test_empty_commitments_returns_zero_counts(self):
        db = self._make_mock_db([])
        result = run_surfacing_sweep(db)
        assert result["evaluated"] == 0
        assert result["changed"] == 0

    def test_single_commitment_evaluated(self):
        commitment = make_commitment(
            context_type="internal",
            confidence_commitment=Decimal("0.7"),
        )
        db = self._make_mock_db([commitment])
        result = run_surfacing_sweep(db)
        assert result["evaluated"] == 1
        # priority_score should have been set
        assert commitment.priority_score is not None

    def test_changed_surfaced_as_creates_audit_entry(self):
        """Commitment whose surfaced_as changes → SurfacingAudit appended."""
        commitment = make_commitment(
            surfaced_as=None,
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
        )
        db = self._make_mock_db([commitment])
        run_surfacing_sweep(db)

        added_types = [type(obj).__name__ for obj in db._added]
        # Should have written at least one SurfacingAudit
        assert "SurfacingAudit" in added_types

    def test_unchanged_surfaced_as_no_audit(self):
        """Commitment already on 'main' that stays 'main' → no new audit row."""
        commitment = make_commitment(
            surfaced_as="main",
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
        )
        db = self._make_mock_db([commitment])
        run_surfacing_sweep(db)

        added_types = [type(obj).__name__ for obj in db._added]
        assert "SurfacingAudit" not in added_types

    def test_is_surfaced_set_true_when_surfaced(self):
        """Q1: is_surfaced = (surfaced_as IS NOT NULL) after sweep."""
        commitment = make_commitment(
            surfaced_as=None,
            is_surfaced=False,
            context_type="external",
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.85"),
            confidence_actionability=Decimal("0.85"),
            resolved_deadline=datetime.now(timezone.utc),
        )
        db = self._make_mock_db([commitment])
        run_surfacing_sweep(db)

        if commitment.surfaced_as is not None:
            assert commitment.is_surfaced is True
        else:
            assert commitment.is_surfaced is False

    def test_multiple_commitments_all_evaluated(self):
        commitments = [
            make_commitment(id=f"commit-{i}", context_type="internal")
            for i in range(5)
        ]
        db = self._make_mock_db(commitments)
        result = run_surfacing_sweep(db)
        assert result["evaluated"] == 5

    def test_db_flush_called_after_changes(self):
        """flush() should be called when there are evaluated commitments."""
        commitment = make_commitment()
        db = self._make_mock_db([commitment])
        run_surfacing_sweep(db)
        db.flush.assert_called_once()
