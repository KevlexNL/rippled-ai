"""Feedback adapter — Phase D4.

Computes per-user threshold adjustments from feedback history
and applies them to detection, surfacing, and completion pipelines.

Public API:
    compute_threshold_adjustments(feedback_rows) -> dict
    apply_detection_adjustment(base_confidence, profile, sender, trigger_class) -> float
    apply_surfacing_adjustment(priority_score, profile) -> int
    apply_completion_adjustment(completion_confidence, profile) -> float
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

# Delta cap: all adjustments bounded to this range
_DELTA_CAP = 0.15

# Minimum feedback events before adjustments take effect
_MIN_FEEDBACK_COUNT = 20

# Window size for ratio computation (last N items)
_WINDOW_SIZE = 50

# Priority score adjustment multiplier (delta * 100 to map 0-1 delta to 0-100 score range)
_SURFACING_SCORE_MULTIPLIER = 100


def _clamp(value: float, lo: float = -_DELTA_CAP, hi: float = _DELTA_CAP) -> float:
    return max(lo, min(hi, value))


def _neutral_result(count: int = 0) -> dict:
    return {
        "surfacing_threshold_delta": 0.0,
        "detection_confidence_delta": 0.0,
        "sender_adjustments": {},
        "pattern_adjustments": {},
        "completion_confidence_delta": 0.0,
        "last_computed_at": datetime.now(timezone.utc).isoformat(),
        "feedback_count": count,
    }


def compute_threshold_adjustments(feedback_rows: list[Any]) -> dict:
    """Compute threshold adjustments from a list of UserFeedback rows.

    Args:
        feedback_rows: List of UserFeedback ORM objects (or duck-typed mocks).

    Returns:
        Dict matching the threshold_adjustments JSONB schema.
    """
    count = len(feedback_rows)
    if count < _MIN_FEEDBACK_COUNT:
        return _neutral_result(count)

    # Use last N items for ratio computation
    recent = feedback_rows[-_WINDOW_SIZE:] if len(feedback_rows) > _WINDOW_SIZE else feedback_rows
    total = len(recent)

    # --- Dismiss rate ---
    dismiss_actions = {"dismiss", "mark_not_commitment"}
    dismiss_count = sum(1 for r in recent if r.action in dismiss_actions)
    dismiss_rate = dismiss_count / total if total > 0 else 0.0

    surfacing_delta = 0.05 if dismiss_rate > 0.30 else 0.0
    # Also nudge detection down when dismiss rate is high
    detection_delta = -0.03 if dismiss_rate > 0.30 else 0.0

    # --- Per-sender confirm rate ---
    sender_confirm: Counter[str] = Counter()
    sender_total: Counter[str] = Counter()
    for r in recent:
        sender = getattr(r, "source_type", None)  # source_type used as grouping proxy
        if sender:
            sender_total[sender] += 1
            if r.action == "confirm":
                sender_confirm[sender] += 1

    sender_adjustments: dict[str, float] = {}
    for sender, stotal in sender_total.items():
        if stotal >= 5:  # minimum per-sender sample
            confirm_rate = sender_confirm[sender] / stotal
            if confirm_rate > 0.80:
                sender_adjustments[sender] = _clamp(0.10)

    # --- Per-pattern dismiss rate ---
    pattern_dismiss: Counter[str] = Counter()
    pattern_total: Counter[str] = Counter()
    for r in recent:
        tc = getattr(r, "trigger_class", None)
        if tc:
            pattern_total[tc] += 1
            if r.action in dismiss_actions:
                pattern_dismiss[tc] += 1

    pattern_adjustments: dict[str, float] = {}
    for tc, ptotal in pattern_total.items():
        if ptotal >= 5:  # minimum per-pattern sample
            pdismiss_rate = pattern_dismiss[tc] / ptotal
            if pdismiss_rate > 0.40:
                pattern_adjustments[tc] = _clamp(-0.05)

    # --- Reopen rate ---
    completion_actions = {"mark_delivered", "confirm"}
    reopen_count = sum(1 for r in recent if r.action == "reopen")
    completion_base = sum(1 for r in recent if r.action in completion_actions)
    reopen_denominator = reopen_count + completion_base
    reopen_rate = reopen_count / reopen_denominator if reopen_denominator > 0 else 0.0

    completion_delta = -0.05 if reopen_rate > 0.20 else 0.0

    return {
        "surfacing_threshold_delta": _clamp(surfacing_delta),
        "detection_confidence_delta": _clamp(detection_delta),
        "sender_adjustments": sender_adjustments,
        "pattern_adjustments": pattern_adjustments,
        "completion_confidence_delta": _clamp(completion_delta),
        "last_computed_at": datetime.now(timezone.utc).isoformat(),
        "feedback_count": count,
    }


def _get_adjustments(profile: Any | None) -> dict | None:
    """Extract threshold_adjustments from profile, returning None if insufficient data."""
    if profile is None:
        return None
    adj = getattr(profile, "threshold_adjustments", None)
    if not isinstance(adj, dict):
        return None
    if adj.get("feedback_count", 0) < _MIN_FEEDBACK_COUNT:
        return None
    return adj


def apply_detection_adjustment(
    base_confidence: float,
    profile: Any | None,
    sender: str | None,
    trigger_class: str | None,
) -> float:
    """Apply per-user detection adjustments to base confidence.

    Args:
        base_confidence: Raw confidence from pattern matching.
        profile: UserCommitmentProfile (or None).
        sender: Sender email for sender-level adjustment.
        trigger_class: Pattern trigger class for pattern-level adjustment.

    Returns:
        Adjusted confidence, clamped to [0.0, 1.0].
    """
    adj = _get_adjustments(profile)
    if adj is None:
        return base_confidence

    delta = adj.get("detection_confidence_delta", 0.0)

    if sender:
        delta += adj.get("sender_adjustments", {}).get(sender, 0.0)

    if trigger_class:
        delta += adj.get("pattern_adjustments", {}).get(trigger_class, 0.0)

    return round(max(0.0, min(1.0, base_confidence + delta)), 4)


def apply_surfacing_adjustment(
    priority_score: int,
    profile: Any | None,
) -> int:
    """Apply per-user surfacing adjustment to priority score.

    A positive surfacing_threshold_delta means the user dismisses a lot,
    so we raise the bar by reducing the score.

    Args:
        priority_score: Raw priority score (0-100).
        profile: UserCommitmentProfile (or None).

    Returns:
        Adjusted priority score.
    """
    adj = _get_adjustments(profile)
    if adj is None:
        return priority_score

    delta = adj.get("surfacing_threshold_delta", 0.0)
    # Higher delta = user dismisses more = reduce score (raise the bar)
    adjusted = priority_score - int(delta * _SURFACING_SCORE_MULTIPLIER)
    return max(0, adjusted)


def apply_completion_adjustment(
    completion_confidence: float,
    profile: Any | None,
) -> float:
    """Apply per-user completion confidence adjustment.

    Args:
        completion_confidence: Raw completion confidence.
        profile: UserCommitmentProfile (or None).

    Returns:
        Adjusted completion confidence, clamped to [0.0, 1.0].
    """
    adj = _get_adjustments(profile)
    if adj is None:
        return completion_confidence

    delta = adj.get("completion_confidence_delta", 0.0)
    return round(max(0.0, min(1.0, completion_confidence + delta)), 4)
