"""Commitment classifier — Phase 06.

Scores a commitment on four dimensions used by the priority scorer:
    - timing_strength   (0-10)
    - business_consequence  (0-10)
    - cognitive_burden  (0-10)
    - confidence_for_surfacing  (0-1, matching codebase convention)

Also provides:
    - get_source_type(commitment) → str  helper to traverse the candidate chain
    - is_external(commitment) → bool
    - has_critical_ambiguity(commitment) → bool

All functions accept SimpleNamespace-compatible objects so they can be tested
without a real database.

Public API:
    classify(commitment) -> ClassifierResult
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Strong timing keywords — used to score timing_strength
# ---------------------------------------------------------------------------

_STRONG_TIMING_PHRASES = frozenset([
    "today", "tonight", "this morning", "this afternoon", "this evening",
    "tomorrow", "by end of day", "eod", "eow", "end of week",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    "this week", "next week",
    "before the call", "before the meeting", "before lunch",
    "in an hour", "in two hours", "in 30 minutes",
    "asap", "immediately", "right away", "now",
    "by ", "due ", "deadline",
])

_WEAK_TIMING_PHRASES = frozenset([
    "soon", "later", "at some point", "eventually", "when possible",
    "whenever", "sometime", "down the road", "in the future",
    "next time", "at some stage",
])

# ---------------------------------------------------------------------------
# Cognitive burden keywords — phrases that signal a lightweight but annoying
# follow-up the user will likely forget.
# ---------------------------------------------------------------------------

_COGNITIVE_BURDEN_PHRASES = frozenset([
    "i'll send", "ill send", "i'll reply", "i'll respond", "i'll get back",
    "i'll follow up", "i'll look into", "i'll check", "i'll handle",
    "let me", "i'll get", "i'll pass", "i'll loop", "i'll ping",
    "i'll reach out", "i'll connect", "i'll set up", "i'll schedule",
    "remind me", "don't forget", "make sure",
])

# ---------------------------------------------------------------------------
# Dataclass for classifier output
# ---------------------------------------------------------------------------


@dataclass
class ClassifierResult:
    """Output of classify(commitment).

    Attributes:
        timing_strength: 0-10, higher = more explicit/urgent timing.
        business_consequence: 0-10, higher = more consequential if missed.
        cognitive_burden: 0-10, higher = more mental overhead.
        confidence_for_surfacing: 0-1, composite surfacing confidence.
        is_external: True if external/client-facing.
        has_critical_ambiguity: True if missing critical info warranting Clarifications surface.
        source_type: best-effort source type string, defaults to 'email_internal'.
    """
    timing_strength: int
    business_consequence: int
    cognitive_burden: int
    confidence_for_surfacing: float
    is_external: bool
    has_critical_ambiguity: bool
    source_type: str


# ---------------------------------------------------------------------------
# Source type helper (Q2 decision: traverse chain, default to email_internal)
# ---------------------------------------------------------------------------

def get_source_type(commitment) -> str:
    """Traverse commitment → candidate_commitments[0] → source_item → source.

    Returns source_type string. Defaults to 'email_internal' if chain is broken.
    """
    try:
        candidate_commitments = getattr(commitment, "candidate_commitments", None)
        if not candidate_commitments:
            return "email_internal"
        cc = candidate_commitments[0]
        source_item = getattr(cc, "source_item", None)
        if source_item is None:
            return "email_internal"
        source = getattr(source_item, "source", None)
        if source is None:
            return "email_internal"
        return source.source_type or "email_internal"
    except (AttributeError, IndexError, TypeError):
        return "email_internal"


# ---------------------------------------------------------------------------
# Externality detection (Q1 to observation_window uses this too)
# ---------------------------------------------------------------------------

def is_external(commitment) -> bool:
    """Return True if the commitment is external/client-facing.

    Checks context_type first (fast path), then falls back to source_type
    heuristics.
    """
    context_type = getattr(commitment, "context_type", None)
    if context_type == "external":
        return True
    if context_type == "internal":
        return False

    # Fallback: infer from source_type
    source_type = get_source_type(commitment)
    return "external" in source_type


# ---------------------------------------------------------------------------
# Timing strength scorer (0-10)
# ---------------------------------------------------------------------------

def score_timing_strength(commitment) -> int:
    """Score timing clarity.

    - resolved_deadline present → 8
    - vague_time_phrase matches strong keywords → 5-7
    - vague_time_phrase matches weak keywords → 1-2
    - deadline_candidates non-empty → 4
    - timing_ambiguity = 'missing' → 0
    - otherwise → 3 (some implicit timing)
    """
    if getattr(commitment, "resolved_deadline", None) is not None:
        return 8

    vague_phrase = (getattr(commitment, "vague_time_phrase", None) or "").lower()
    if vague_phrase:
        for phrase in _STRONG_TIMING_PHRASES:
            if phrase in vague_phrase:
                return 7
        for phrase in _WEAK_TIMING_PHRASES:
            if phrase in vague_phrase:
                return 2
        # Vague phrase present but not matched
        return 4

    deadline_candidates = getattr(commitment, "deadline_candidates", None)
    if deadline_candidates:
        return 4

    timing_ambiguity = getattr(commitment, "timing_ambiguity", None)
    if timing_ambiguity in ("missing", "timing_missing"):
        return 0

    return 3


# ---------------------------------------------------------------------------
# Business consequence scorer (0-10)
# ---------------------------------------------------------------------------

def score_business_consequence(commitment, external: bool) -> int:
    """Score business consequence based on externality and evidence.

    External commitments start at 7; internal at 4.
    Boost for confidence_commitment ≥ 0.8, explicit deliverable, and explicit deadline.
    """
    base = 7 if external else 4

    # Confidence boost: highly confident commitment → +1
    conf = float(getattr(commitment, "confidence_commitment", None) or 0)
    if conf >= 0.8:
        base = min(10, base + 1)

    # Explicit deliverable → +1
    if getattr(commitment, "deliverable", None):
        base = min(10, base + 1)

    # Explicit deadline → +1
    if getattr(commitment, "resolved_deadline", None) is not None:
        base = min(10, base + 1)

    return base


# ---------------------------------------------------------------------------
# Cognitive burden scorer (0-10)
# ---------------------------------------------------------------------------

def score_cognitive_burden(commitment) -> int:
    """Score cognitive burden.

    Small, easy-to-forget commitments score high here even if business
    consequence is low. Based on language patterns in commitment_text and title.
    """
    text_parts = []
    for attr in ("commitment_text", "title", "description"):
        val = getattr(commitment, attr, None) or ""
        text_parts.append(val.lower())
    combined = " ".join(text_parts)

    score = 3  # neutral baseline

    # Lightweight follow-up language → high burden (easy to forget)
    matches = sum(1 for phrase in _COGNITIVE_BURDEN_PHRASES if phrase in combined)
    if matches >= 3:
        score = 8
    elif matches >= 2:
        score = 7
    elif matches >= 1:
        score = 6

    # Long deliverables or multi-part commitments → harder to track
    deliverable = getattr(commitment, "deliverable", None) or ""
    if len(deliverable) > 80:
        score = min(10, score + 1)

    # External commitments are inherently more burdensome to track
    context_type = getattr(commitment, "context_type", None)
    if context_type == "external":
        score = min(10, score + 1)

    return score


# ---------------------------------------------------------------------------
# Surfacing confidence scorer (0-1)
# ---------------------------------------------------------------------------

def score_confidence_for_surfacing(commitment) -> float:
    """Composite surfacing confidence on 0-1 scale.

    Combines:
        - confidence_commitment (weight 0.4)
        - confidence_owner (weight 0.3)
        - confidence_actionability (weight 0.3)

    Missing dimensions default to 0.5 (uncertain but not disqualifying).
    """
    def _float(val, default: float = 0.5) -> float:
        if val is None:
            return default
        return float(val)

    conf_commitment = _float(getattr(commitment, "confidence_commitment", None))
    conf_owner = _float(getattr(commitment, "confidence_owner", None))
    conf_actionability = _float(getattr(commitment, "confidence_actionability", None))

    composite = (
        conf_commitment * 0.4
        + conf_owner * 0.3
        + conf_actionability * 0.3
    )
    return round(min(1.0, max(0.0, composite)), 3)


# ---------------------------------------------------------------------------
# Critical ambiguity detection
# ---------------------------------------------------------------------------

def has_critical_ambiguity(commitment) -> bool:
    """Return True if the commitment has an ambiguity that warrants Clarifications surface.

    Critical cases per the brief:
    - unclear owner on important commitment
    - conflicting dates for external promise
    - likely real commitment with no clear deliverable
    - unresolved external follow-up with expectation attached

    This checks structured ambiguity fields on the commitment model.
    """
    ownership_ambiguity = getattr(commitment, "ownership_ambiguity", None)
    if ownership_ambiguity in ("missing", "conflicting", "owner_missing", "owner_conflicting"):
        return True

    timing_ambiguity = getattr(commitment, "timing_ambiguity", None)
    if timing_ambiguity in ("conflicting", "timing_conflicting"):
        return True

    deliverable_ambiguity = getattr(commitment, "deliverable_ambiguity", None)
    if deliverable_ambiguity in ("unclear", "deliverable_unclear"):
        return True

    # If owner is completely absent and commitment is external → critical
    external = getattr(commitment, "context_type", None) == "external"
    no_owner = (
        getattr(commitment, "resolved_owner", None) is None
        and getattr(commitment, "suggested_owner", None) is None
    )
    if external and no_owner:
        return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(commitment) -> ClassifierResult:
    """Classify a commitment and score all surfacing dimensions.

    Args:
        commitment: Any object with Commitment-compatible attributes
                    (ORM model or SimpleNamespace).

    Returns:
        ClassifierResult with all dimension scores.
    """
    external = is_external(commitment)
    source_type = get_source_type(commitment)
    timing = score_timing_strength(commitment)
    consequence = score_business_consequence(commitment, external)
    burden = score_cognitive_burden(commitment)
    confidence = score_confidence_for_surfacing(commitment)
    critical_ambiguity = has_critical_ambiguity(commitment)

    return ClassifierResult(
        timing_strength=timing,
        business_consequence=consequence,
        cognitive_burden=burden,
        confidence_for_surfacing=confidence,
        is_external=external,
        has_critical_ambiguity=critical_ambiguity,
        source_type=source_type,
    )
