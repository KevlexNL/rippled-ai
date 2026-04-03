"""Completion scorer — Phase 05.

Computes multi-dimensional confidence scores for a (commitment, evidence) pair.

Confidence dimensions:
- delivery_confidence: P(delivery happened)
- completion_confidence: P(commitment fully satisfied), accounts for commitment_type
- recipient_match_confidence: P(right recipient received it)
- artifact_match_confidence: P(right deliverable was sent)
- closure_readiness_confidence: composite score used by auto-close sweep

Public API:
    score_evidence(commitment, evidence) -> CompletionScore
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.completion.matcher import CompletionEvidence


# ---------------------------------------------------------------------------
# Constants — base delivery confidence by evidence strength
# ---------------------------------------------------------------------------

_BASE_DELIVERY = {
    "strong": 0.85,
    "moderate": 0.65,
    "weak": 0.40,
}

# Commitment types that benefit from the attachment bonus (+0.05)
_DELIVER_TYPES = {"send", "deliver", "introduce"}

# Commitment types with a delivery-score penalty (-0.10)
_REVIEW_TYPES = {"review", "investigate"}

# Commitment types that require artifact signal (penalty without attachment)
_CREATE_TYPES = {"create"}

# Commitment types that benefit from thread continuity (+0.05)
_REPLY_TYPES = {"follow_up", "update"}

# Commitment types that benefit from outbound direction (+0.05)
_OUTBOUND_TYPES = {"send", "deliver", "introduce", "follow_up", "update"}

# Completion confidence multipliers by commitment_type
_COMPLETION_MULTIPLIERS = {
    "send": 0.95,
    "share": 0.95,
    "introduce": 0.95,
    "review": 0.70,
    "check": 0.70,
    "investigate": 0.70,
    "create": 0.70,
    "follow_up": 0.80,
    "update": 0.80,
    "coordinate": 0.80,
}
_DEFAULT_COMPLETION_MULTIPLIER = 0.75


# ---------------------------------------------------------------------------
# CompletionScore dataclass
# ---------------------------------------------------------------------------

@dataclass
class CompletionScore:
    """Multi-dimensional confidence output from the scorer.

    Produced internally by score_evidence(); never deserialized from JSON.
    """

    delivery_confidence: float           # P(delivery happened)
    completion_confidence: float         # P(commitment fully satisfied)
    evidence_strength: str               # "strong" | "moderate" | "weak" (passed through)
    recipient_match_confidence: float    # P(right recipient got it)
    artifact_match_confidence: float     # P(right deliverable was sent)
    closure_readiness_confidence: float  # P(safe to auto-close later)
    primary_pattern: str | None          # pattern that most contributed
    notes: list                          # human-readable evidence notes


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_delivery_confidence(commitment: Any, evidence: CompletionEvidence) -> float:
    """Compute delivery_confidence from base + type-specific adjustments.

    Type-specific adjustments (Phase E3 — Gap 10.2):
    - send/deliver/introduce: +0.05 attachment bonus, +0.05 outbound bonus
    - reply/follow_up/update: +0.05 thread continuity bonus, +0.05 outbound bonus
    - review/investigate: -0.10 penalty (delivery signal ≠ done)
    - create: -0.10 penalty without artifact, no penalty with attachment
    - coordinate/schedule: standard (no additional adjustment)
    """
    base = _BASE_DELIVERY.get(evidence.evidence_strength, 0.40)
    adjustment = 0.0

    commitment_type = (commitment.commitment_type or "").lower()

    # +0.05 for attachment on deliver-class commitments
    if evidence.has_attachment and commitment_type in _DELIVER_TYPES:
        adjustment += 0.05

    # +0.05 for outbound direction on delivery/reply types
    if evidence.direction == "outbound" and commitment_type in _OUTBOUND_TYPES:
        adjustment += 0.05

    # +0.05 for thread continuity on reply/follow_up types
    if "thread_continuity" in evidence.matched_patterns and commitment_type in _REPLY_TYPES:
        adjustment += 0.05

    # -0.10 for review/investigate types (delivery signal ≠ done)
    if commitment_type in _REVIEW_TYPES:
        adjustment -= 0.10

    # -0.10 for create types without artifact signal (requires proof of artifact)
    if commitment_type in _CREATE_TYPES and not evidence.has_attachment:
        adjustment -= 0.10

    # -0.15 for external email commitment where direction is not outbound
    if (
        evidence.source_type == "email"
        and getattr(commitment, "is_external_participant", False)
        and evidence.direction != "outbound"
    ):
        adjustment -= 0.15

    score = base + adjustment

    # Cross-channel bonus (Phase E3 — Gap 10.1):
    # If evidence comes from a different source channel than the commitment's origin,
    # apply a 1.10x multiplier. Cross-channel corroboration is a confidence signal.
    origin_source = getattr(commitment, "_origin_source_type", None)
    if origin_source and evidence.source_type and origin_source != evidence.source_type:
        score *= 1.10
        _cross_channel = True
    else:
        _cross_channel = False

    # Store cross-channel flag for notes (accessed via closure in caller)
    commitment._cross_channel_bonus = _cross_channel

    return round(max(0.0, min(1.0, score)), 4)


def _compute_completion_confidence(delivery_confidence: float, commitment_type: str) -> float:
    """Compute completion_confidence = delivery_confidence × type multiplier."""
    multiplier = _COMPLETION_MULTIPLIERS.get(
        (commitment_type or "").lower(), _DEFAULT_COMPLETION_MULTIPLIER
    )
    return round(delivery_confidence * multiplier, 4)


def _compute_recipient_match_confidence(
    evidence: CompletionEvidence,
    commitment: Any,
) -> float:
    """Compute P(right recipient received it)."""
    target = (commitment.target_entity or "").lower().strip()

    if not target:
        return 0.50  # neutral — no target entity to verify against

    recipients = evidence.recipients or []
    if not recipients:
        return 0.50  # neutral — no recipient field on source_item

    for r in recipients:
        if isinstance(r, str):
            r_lower = r.lower()
            if target == r_lower or target in r_lower or r_lower in target:
                return 0.90  # exact match
            # Fuzzy partial match (e.g., name in email address)
            if any(part in r_lower for part in target.split() if len(part) > 2):
                return 0.65

    return 0.30  # known target, no match found


def _compute_artifact_match_confidence(
    evidence: CompletionEvidence,
    commitment: Any,
) -> float:
    """Compute P(right deliverable was sent)."""
    deliverable = (commitment.deliverable or "").lower().strip()

    if not deliverable:
        return 0.50  # neutral — no deliverable to verify

    has_deliverable_keyword = "deliverable_keyword" in evidence.matched_patterns

    if has_deliverable_keyword and evidence.has_attachment:
        return 0.90
    if has_deliverable_keyword:
        return 0.70
    if evidence.matched_patterns:
        return 0.40  # pattern-only match (no keyword match)

    return 0.30


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_evidence(
    commitment: Any,
    evidence: CompletionEvidence,
    user_profile: Any | None = None,
) -> CompletionScore:
    """Compute multi-dimensional confidence scores for a commitment/evidence pair.

    Args:
        commitment: Duck-typed Commitment ORM object or compatible namespace.
        evidence: CompletionEvidence produced by the matcher.

    Returns:
        CompletionScore with all confidence dimensions populated.
    """
    commitment_type = (commitment.commitment_type or "").lower()

    delivery = _compute_delivery_confidence(commitment, evidence)
    completion = _compute_completion_confidence(delivery, commitment_type)

    # [D4] Apply per-user completion confidence adjustment
    if user_profile is not None:
        from app.services.feedback_adapter import apply_completion_adjustment
        completion = apply_completion_adjustment(completion, user_profile)

    recipient = _compute_recipient_match_confidence(evidence, commitment)
    artifact = _compute_artifact_match_confidence(evidence, commitment)

    # closure_readiness = delivery×0.5 + recipient×0.3 + artifact×0.2
    closure_readiness = round(delivery * 0.5 + recipient * 0.3 + artifact * 0.2, 4)

    primary_pattern = evidence.matched_patterns[0] if evidence.matched_patterns else None

    notes: list[str] = [
        f"evidence_strength={evidence.evidence_strength}",
        f"delivery_confidence={delivery:.2f}",
        f"commitment_type={commitment_type}",
    ]
    if evidence.has_attachment:
        notes.append("has_attachment=true")
    if evidence.direction:
        notes.append(f"direction={evidence.direction}")
    if getattr(commitment, "_cross_channel_bonus", False):
        origin = getattr(commitment, "_origin_source_type", "unknown")
        notes.append(f"cross_channel_bonus=1.10x (origin={origin}, evidence={evidence.source_type})")

    return CompletionScore(
        delivery_confidence=delivery,
        completion_confidence=completion,
        evidence_strength=evidence.evidence_strength,
        recipient_match_confidence=recipient,
        artifact_match_confidence=artifact,
        closure_readiness_confidence=closure_readiness,
        primary_pattern=primary_pattern,
        notes=notes,
    )
