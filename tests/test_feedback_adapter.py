"""Unit tests for Phase D4 — feedback_adapter.py.

TDD RED phase: these tests define the service contract.
~12 tests covering compute_threshold_adjustments and apply_* functions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.feedback_adapter import (
    apply_completion_adjustment,
    apply_detection_adjustment,
    apply_surfacing_adjustment,
    compute_threshold_adjustments,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ACTIONS = [
    "dismiss", "confirm", "correct_owner", "correct_deadline",
    "correct_description", "mark_not_commitment", "mark_delivered", "reopen",
]


def _make_feedback_rows(actions: list[str], source_types: list[str] | None = None, trigger_classes: list[str] | None = None) -> list[MagicMock]:
    """Build mock UserFeedback rows for testing."""
    rows = []
    for i, action in enumerate(actions):
        row = MagicMock()
        row.action = action
        row.source_type = (source_types[i] if source_types else "email")
        row.trigger_class = (trigger_classes[i] if trigger_classes else "explicit_self_commitment")
        row.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
        # Denormalized sender for sender-level adjustments
        row.old_value = None
        row.new_value = None
        rows.append(row)
    return rows


def _make_profile(threshold_adjustments: dict | None = None, feedback_count: int = 0) -> MagicMock:
    """Build a mock UserCommitmentProfile with threshold_adjustments."""
    profile = MagicMock()
    if threshold_adjustments is None:
        profile.threshold_adjustments = None
    else:
        profile.threshold_adjustments = threshold_adjustments
    return profile


# ---------------------------------------------------------------------------
# compute_threshold_adjustments tests
# ---------------------------------------------------------------------------


class TestComputeThresholdAdjustments:
    def test_basic_mixed_feedback(self):
        """Mixed feedback produces non-zero adjustments."""
        # 25 dismiss + 25 confirm = 50 total, dismiss_rate = 50% > 30%
        actions = ["dismiss"] * 25 + ["confirm"] * 25
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert "surfacing_threshold_delta" in result
        assert "detection_confidence_delta" in result
        assert "completion_confidence_delta" in result
        assert "sender_adjustments" in result
        assert "pattern_adjustments" in result
        assert "last_computed_at" in result
        assert result["feedback_count"] == 50

    def test_high_dismiss_rate_raises_surfacing_threshold(self):
        """Dismiss rate > 30% -> surfacing_threshold_delta += 0.05."""
        # 20 dismiss + 10 confirm = 30 total, dismiss_rate = 20/30 = 66%
        actions = ["dismiss"] * 20 + ["confirm"] * 10
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert result["surfacing_threshold_delta"] >= 0.05

    def test_low_dismiss_rate_zero_surfacing_delta(self):
        """Dismiss rate < 30% -> surfacing_threshold_delta = 0.0."""
        # 5 dismiss + 25 confirm = 30 total, dismiss_rate = 16%
        actions = ["dismiss"] * 5 + ["confirm"] * 25
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert result["surfacing_threshold_delta"] == 0.0

    def test_high_pattern_dismiss_rate_reduces_pattern(self):
        """Pattern dismiss rate > 40% -> pattern_adjustments[class] = -0.05."""
        # 25 dismiss on same trigger_class + 5 confirm on same class
        actions = ["dismiss"] * 25 + ["confirm"] * 5
        trigger_classes = ["follow_up"] * 30
        rows = _make_feedback_rows(actions, trigger_classes=trigger_classes)
        result = compute_threshold_adjustments(rows)

        assert "follow_up" in result["pattern_adjustments"]
        assert result["pattern_adjustments"]["follow_up"] <= -0.05

    def test_high_reopen_rate_reduces_completion_confidence(self):
        """Reopen rate > 20% -> completion_confidence_delta = -0.05."""
        # 10 mark_delivered + 8 reopen + 2 confirm = 20 total
        # reopen_rate = 8 / (8 + 10 + 2) = 8/20 = 40% > 20%
        actions = ["mark_delivered"] * 10 + ["reopen"] * 8 + ["confirm"] * 2
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert result["completion_confidence_delta"] <= -0.05

    def test_cap_enforcement_max(self):
        """Deltas bounded to +/- 0.15."""
        # Extreme case: all dismiss + mark_not_commitment
        actions = ["dismiss"] * 25 + ["mark_not_commitment"] * 25
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert result["surfacing_threshold_delta"] <= 0.15
        assert result["detection_confidence_delta"] >= -0.15
        for val in result["pattern_adjustments"].values():
            assert -0.15 <= val <= 0.15

    def test_minimum_20_events_guard(self):
        """Returns all zeros when feedback_count < 20."""
        actions = ["dismiss"] * 10 + ["confirm"] * 5
        rows = _make_feedback_rows(actions)
        result = compute_threshold_adjustments(rows)

        assert result["surfacing_threshold_delta"] == 0.0
        assert result["detection_confidence_delta"] == 0.0
        assert result["completion_confidence_delta"] == 0.0
        assert result["sender_adjustments"] == {}
        assert result["pattern_adjustments"] == {}

    def test_empty_feedback_returns_zeros(self):
        """Empty feedback list returns neutral adjustments."""
        result = compute_threshold_adjustments([])

        assert result["surfacing_threshold_delta"] == 0.0
        assert result["detection_confidence_delta"] == 0.0
        assert result["completion_confidence_delta"] == 0.0
        assert result["feedback_count"] == 0


# ---------------------------------------------------------------------------
# apply_* function tests
# ---------------------------------------------------------------------------


class TestApplyDetectionAdjustment:
    def test_applies_delta_and_sender_and_pattern(self):
        """Applies detection_confidence_delta + sender + pattern correctly."""
        profile = _make_profile(threshold_adjustments={
            "detection_confidence_delta": -0.03,
            "sender_adjustments": {"alice@example.com": 0.10},
            "pattern_adjustments": {"explicit_self_commitment": 0.02},
            "feedback_count": 25,
        })
        result = apply_detection_adjustment(
            0.70, profile, "alice@example.com", "explicit_self_commitment",
        )
        # 0.70 + (-0.03) + 0.10 + 0.02 = 0.79
        assert abs(result - 0.79) < 0.001

    def test_no_profile_returns_base(self):
        """None profile returns base confidence unchanged."""
        result = apply_detection_adjustment(0.70, None, "alice@example.com", "foo")
        assert result == 0.70

    def test_low_feedback_count_returns_base(self):
        """Profile with feedback_count < 20 returns base unchanged."""
        profile = _make_profile(threshold_adjustments={
            "detection_confidence_delta": -0.10,
            "sender_adjustments": {},
            "pattern_adjustments": {},
            "feedback_count": 5,
        })
        result = apply_detection_adjustment(0.70, profile, "x@y.com", "foo")
        assert result == 0.70


class TestApplySurfacingAdjustment:
    def test_adjusts_priority_score(self):
        """Adjusts priority score based on surfacing_threshold_delta."""
        profile = _make_profile(threshold_adjustments={
            "surfacing_threshold_delta": 0.05,
            "feedback_count": 25,
        })
        # surfacing_threshold_delta > 0 means user dismisses a lot -> raise bar -> reduce score
        result = apply_surfacing_adjustment(75, profile)
        assert result < 75

    def test_no_profile_returns_base(self):
        """None profile returns base score unchanged."""
        result = apply_surfacing_adjustment(75, None)
        assert result == 75


class TestApplyCompletionAdjustment:
    def test_applies_completion_delta(self):
        """Applies completion_confidence_delta."""
        profile = _make_profile(threshold_adjustments={
            "completion_confidence_delta": -0.05,
            "feedback_count": 25,
        })
        result = apply_completion_adjustment(0.80, profile)
        assert abs(result - 0.75) < 0.001

    def test_no_profile_returns_base(self):
        """None profile returns base confidence unchanged."""
        result = apply_completion_adjustment(0.80, None)
        assert result == 0.80
