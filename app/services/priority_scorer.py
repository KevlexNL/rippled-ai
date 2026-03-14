"""Priority scorer — Phase 06 + Phase C3.

Combines ClassifierResult dimensions into a 0-100 priority score.

Score formula (total max = 100):
    - Externality:          +25 if external
    - Timing:               0-20 (timing_strength 0-10 → scaled ×2)
    - Business consequence: 0-20 (business_consequence 0-10 → scaled ×2)
    - Cognitive burden:     0-15 (cognitive_burden 0-10 → scaled ×1.5)
    - Confidence:           0-15 (confidence_for_surfacing 0-1 → scaled ×15,
                                   asymmetric suppression for low values < 0.3)
    - Staleness bonus:      0-10 (commitment past observation window without resolution)
    - [C3] Proximity spike: 0-40 (delivery event approaching; decays post-event)
    - [C3] Counterparty:    ×0.8-1.4 multiplier by relationship type
    - [C3] Delivery state:  -5 to -10 modifier when partial delivery evidence exists

C3 formula: (base_score + proximity_spike + delivery_state_modifier) * counterparty_multiplier
    capped at 100.

Note: confidence_for_surfacing is stored on 0-1 scale (codebase convention).
All other dimensions are already on 0-10 scale. Scaling is applied internally
here, so callers never need to convert.

Public API:
    score(classifier_result, commitment, proximity_hours=None) -> int   (0-100)
    proximity_spike(proximity_hours) -> float
    counterparty_multiplier(counterparty_type) -> float
    delivery_state_modifier(delivery_state) -> float
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.commitment_classifier import ClassifierResult


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

_EXTERNALITY_BONUS = 25       # flat if external
_TIMING_MAX = 20              # timing_strength 0-10 → 0-20
_CONSEQUENCE_MAX = 20         # business_consequence 0-10 → 0-20
_BURDEN_MAX = 15              # cognitive_burden 0-10 → 0-15
_CONFIDENCE_MAX = 15          # confidence_for_surfacing 0-1 → 0-15
_STALENESS_MAX = 10           # staleness bonus for unresolved past window
_CONFIDENCE_SUPPRESSION_THRESHOLD = 0.3  # below this, penalty applies

# C3 — counterparty multipliers
_COUNTERPARTY_MULTIPLIERS: dict[str, float] = {
    "external_client": 1.4,
    "internal_manager": 1.2,
    "internal_peer": 1.0,
    "self": 0.8,
}

# C3 — delivery state modifiers
_DELIVERY_STATE_MODIFIERS: dict[str, float] = {
    "acknowledged": -5,
    "draft_sent": -10,
    "rescheduled": -5,
    "partial": -8,
}


def _staleness_bonus(commitment) -> float:
    """Calculate staleness bonus (0-10).

    If the commitment has an observe_until in the past and is still active/proposed,
    award a bonus proportional to how far past the window it is (capped at 7 days).
    """
    observe_until = getattr(commitment, "observe_until", None)
    lifecycle_state = getattr(commitment, "lifecycle_state", None)

    # Only award staleness bonus for unresolved commitments
    if lifecycle_state not in ("active", "proposed", "needs_clarification", None):
        return 0.0

    if observe_until is None:
        return 0.0

    now = datetime.now(timezone.utc)

    # observe_until may be naive (no tzinfo) in tests — handle both
    if observe_until.tzinfo is None:
        from datetime import timezone as _tz
        observe_until = observe_until.replace(tzinfo=_tz.utc)

    if observe_until > now:
        return 0.0

    hours_past = (now - observe_until).total_seconds() / 3600
    # Cap at 168 hours (7 days) → full bonus
    fraction = min(hours_past / 168.0, 1.0)
    return fraction * _STALENESS_MAX


def proximity_spike(proximity_hours: float | None) -> float:
    """Calculate proximity spike bonus (0-40) based on hours until delivery event.

    proximity_hours >= 72:   0 (no spike)
    24 <= hours < 72:        10
    1 <= hours < 24:         20
    0 <= hours < 1:          35
    hours < 0 (post-event):  40 decaying to 0 over 48h after event end
    """
    if proximity_hours is None:
        return 0.0
    if proximity_hours >= 72:
        return 0.0
    if proximity_hours >= 24:
        return 10.0
    if proximity_hours >= 1:
        return 20.0
    if proximity_hours >= 0:
        return 35.0
    # post-event: decay over 48h
    abs_hours = abs(proximity_hours)
    return max(0.0, 40.0 - (abs_hours / 48.0) * 40.0)


def counterparty_multiplier(counterparty_type: str | None) -> float:
    """Return score multiplier based on counterparty type (1.0 if unknown/None)."""
    return _COUNTERPARTY_MULTIPLIERS.get(counterparty_type or "", 1.0)


def delivery_state_modifier(delivery_state: str | None) -> float:
    """Return score modifier based on delivery state (0 if None or unknown)."""
    return _DELIVERY_STATE_MODIFIERS.get(delivery_state or "", 0.0)


def score(
    classifier_result: "ClassifierResult",
    commitment,
    proximity_hours: float | None = None,
) -> int:
    """Compute a 0-100 priority score from the classifier dimensions.

    Args:
        classifier_result: Output of commitment_classifier.classify(commitment).
        commitment: The commitment object (needed for staleness + C3 fields).
        proximity_hours: Hours until next delivery_at event (None = no proximity).

    Returns:
        Integer 0-100 priority score (higher = more urgent to surface).

    C3 formula: (base_score + proximity_spike + delivery_state_modifier) * counterparty_multiplier
    """
    total = 0.0

    # 1. Externality
    if classifier_result.is_external:
        total += _EXTERNALITY_BONUS

    # 2. Timing (0-10 → 0-20)
    total += (classifier_result.timing_strength / 10.0) * _TIMING_MAX

    # 3. Business consequence (0-10 → 0-20)
    total += (classifier_result.business_consequence / 10.0) * _CONSEQUENCE_MAX

    # 4. Cognitive burden (0-10 → 0-15)
    total += (classifier_result.cognitive_burden / 10.0) * _BURDEN_MAX

    # 5. Confidence (0-1 → 0-15, with asymmetric suppression)
    conf = classifier_result.confidence_for_surfacing
    if conf < _CONFIDENCE_SUPPRESSION_THRESHOLD:
        # Low confidence: apply 50% penalty to prevent weak signals from surfacing
        conf_contribution = (conf / _CONFIDENCE_SUPPRESSION_THRESHOLD) * (_CONFIDENCE_MAX * 0.5)
    else:
        conf_contribution = conf * _CONFIDENCE_MAX
    total += conf_contribution

    # 6. Staleness bonus (0-10)
    total += _staleness_bonus(commitment)

    # [C3] 7. Proximity spike (0-40)
    total += proximity_spike(proximity_hours)

    # [C3] 8. Delivery state modifier (-10 to 0)
    ds = getattr(commitment, "delivery_state", None)
    total += delivery_state_modifier(ds)

    # [C3] 9. Counterparty multiplier (0.8-1.4)
    ct = getattr(commitment, "counterparty_type", None)
    total *= counterparty_multiplier(ct)

    return min(100, max(0, round(total)))
