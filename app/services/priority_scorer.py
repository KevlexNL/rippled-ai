"""Priority scorer — Phase 06.

Combines ClassifierResult dimensions into a 0-100 priority score.

Score formula (total max = 100):
    - Externality:          +25 if external
    - Timing:               0-20 (timing_strength 0-10 → scaled ×2)
    - Business consequence: 0-20 (business_consequence 0-10 → scaled ×2)
    - Cognitive burden:     0-15 (cognitive_burden 0-10 → scaled ×1.5)
    - Confidence:           0-15 (confidence_for_surfacing 0-1 → scaled ×15,
                                   asymmetric suppression for low values < 0.3)
    - Staleness bonus:      0-10 (commitment past observation window without resolution)

Note: confidence_for_surfacing is stored on 0-1 scale (codebase convention).
All other dimensions are already on 0-10 scale. Scaling is applied internally
here, so callers never need to convert.

Public API:
    score(classifier_result, commitment) -> int   (0-100)
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


def score(classifier_result: "ClassifierResult", commitment) -> int:
    """Compute a 0-100 priority score from the classifier dimensions.

    Args:
        classifier_result: Output of commitment_classifier.classify(commitment).
        commitment: The commitment object (needed for staleness calculation).

    Returns:
        Integer 0-100 priority score (higher = more urgent to surface).
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

    return min(100, max(0, round(total)))
