"""Surfacing router — Phase 06.

Determines which surface a commitment belongs on (or None if it should be
held internally), given classifier + scorer outputs.

Routing logic:
    1. If in observation window and NOT early-surface exception → None (hold)
    2. If has_critical_ambiguity AND above clarification threshold → 'clarifications'
    3. If priority_score ≥ 60 → 'main'
    4. If priority_score ≥ 35 → 'shortlist'
    5. Otherwise → None (held internally, not surfaced)

These thresholds match the interpretation plan and can be tuned per the brief's
"future extension: user-configurable surfacing sensitivity" note.

Public API:
    route(commitment) -> RoutingResult
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.commitment_classifier import classify, ClassifierResult
from app.services.observation_window import is_observable, should_surface_early
from app.services.priority_scorer import score


SurfaceDestination = Literal["main", "shortlist", "clarifications"] | None


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_MAIN_THRESHOLD = 60
_SHORTLIST_THRESHOLD = 30
# Minimum score to trigger the clarifications surface (don't route near-zero
# confidence junk to clarifications)
_CLARIFICATION_MIN_SCORE = 25


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RoutingResult:
    """Result of route(commitment).

    Attributes:
        surface: 'main', 'shortlist', 'clarifications', or None.
        priority_score: Integer 0-100 computed score.
        classifier: ClassifierResult with dimension scores.
        reason: Human-readable routing explanation.
    """
    surface: SurfaceDestination
    priority_score: int
    classifier: ClassifierResult
    reason: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route(commitment, proximity_hours: float | None = None) -> RoutingResult:
    """Route a commitment to a surface destination.

    Args:
        commitment: Any object with Commitment-compatible attributes.

    Returns:
        RoutingResult with surface destination, score, and reason.
    """
    classifier_result = classify(commitment)
    priority = score(classifier_result, commitment, proximity_hours=proximity_hours)

    # --- Step 0: Structure completeness gate ---
    structure_complete = getattr(commitment, "structure_complete", True)
    if not structure_complete:
        return RoutingResult(
            surface=None,
            priority_score=priority,
            classifier=classifier_result,
            reason="structure incomplete — held for triage",
        )

    # --- Step 0b: Speech act gate ---
    # Certain speech acts should never be surfaced — they are handled by
    # other subsystems (completion service, lifecycle handler) or represent
    # non-actionable content.
    speech_act = getattr(commitment, "speech_act", None)
    _NO_SURFACE_SPEECH_ACTS = {
        "status_update", "informational", "completion",
        "cancellation", "decline",
    }
    if speech_act in _NO_SURFACE_SPEECH_ACTS:
        return RoutingResult(
            surface=None,
            priority_score=priority,
            classifier=classifier_result,
            reason=f"no-surface speech act: {speech_act}",
        )

    # --- Step 0c: Watching relationship gate ---
    # Override: if the user is the requester (requester_resolved is set),
    # treat as 'mine' — they asked for something and are waiting on delivery.
    user_relationship = getattr(commitment, "user_relationship", None)
    requester_resolved = getattr(commitment, "requester_resolved", None)
    if requester_resolved:
        # User is the requester — treat as 'mine' regardless of user_relationship
        user_relationship = "mine"

    if user_relationship == "watching":
        return RoutingResult(
            surface=None,
            priority_score=priority,
            classifier=classifier_result,
            reason="watching relationship — not surfaced by default",
        )

    # --- Step 1: Observation window gate ---
    in_window = is_observable(commitment)
    early_ok = should_surface_early(commitment)

    if in_window and not early_ok:
        return RoutingResult(
            surface=None,
            priority_score=priority,
            classifier=classifier_result,
            reason="still in observation window",
        )

    # --- Step 2: Critical ambiguity → Clarifications ---
    if classifier_result.has_critical_ambiguity and priority >= _CLARIFICATION_MIN_SCORE:
        return RoutingResult(
            surface="clarifications",
            priority_score=priority,
            classifier=classifier_result,
            reason="critical ambiguity requires clarification",
        )

    # --- Step 3: Main threshold ---
    if priority >= _MAIN_THRESHOLD:
        return RoutingResult(
            surface="main",
            priority_score=priority,
            classifier=classifier_result,
            reason=f"high priority score {priority} ≥ {_MAIN_THRESHOLD}",
        )

    # --- Step 4: Shortlist threshold ---
    if priority >= _SHORTLIST_THRESHOLD:
        return RoutingResult(
            surface="shortlist",
            priority_score=priority,
            classifier=classifier_result,
            reason=f"medium priority score {priority} ≥ {_SHORTLIST_THRESHOLD}",
        )

    # --- Step 5: Hold internally ---
    return RoutingResult(
        surface=None,
        priority_score=priority,
        classifier=classifier_result,
        reason=f"score {priority} below shortlist threshold {_SHORTLIST_THRESHOLD}",
    )
