"""Cross-source merge detector — Phase E3 (Gap 4.1).

Detects when a newly created commitment is a duplicate of an existing active
commitment (same real-world obligation captured from multiple sources).

Merge strategy:
- Keep highest-confidence commitment as canonical
- Re-link signals from duplicate to canonical
- Mark duplicate as discarded with reason "merged::{canonical_id}"

Public API:
    find_merge_candidates(new_commitment, existing_commitments, config?) -> list[Commitment]
    execute_merge(canonical, duplicate, db) -> None
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import CommitmentSignal

# ---------------------------------------------------------------------------
# Stopwords for deliverable comparison (same set as completion matcher)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of",
        "and", "or", "but", "we", "i", "my", "your", "this", "that", "with",
        "by", "as", "be", "will", "ll", "have", "has", "had", "do", "did",
        "not", "no", "so", "if", "up", "out", "its",
    }
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MergeConfig:
    """Configurable thresholds for merge detection."""

    timeframe_hours: float = 72
    """Maximum hours between creation times to consider a merge."""

    min_deliverable_overlap: float = 0.50
    """Minimum fraction of significant words that must overlap."""


_DEFAULT_CONFIG = MergeConfig()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_significant_words(text: str) -> set[str]:
    """Extract significant words (2+ chars, not stopwords) from text."""
    if not text:
        return set()
    words = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _actor_matches(a: Any, b: Any) -> bool:
    """Return True if both commitments share the same actor (case-insensitive)."""
    owners_a = [
        (a.resolved_owner or "").lower().strip(),
        (a.suggested_owner or "").lower().strip(),
    ]
    owners_b = [
        (b.resolved_owner or "").lower().strip(),
        (b.suggested_owner or "").lower().strip(),
    ]
    owners_a = {o for o in owners_a if o}
    owners_b = {o for o in owners_b if o}

    if not owners_a or not owners_b:
        return False

    return bool(owners_a & owners_b)


def _deliverable_overlaps(a: Any, b: Any, min_overlap: float) -> bool:
    """Return True if deliverable text has sufficient word overlap."""
    text_a = a.deliverable or a.commitment_text or ""
    text_b = b.deliverable or b.commitment_text or ""

    words_a = _extract_significant_words(text_a)
    words_b = _extract_significant_words(text_b)

    if not words_a or not words_b:
        return False

    # Use the smaller set as denominator for overlap ratio
    smaller = min(len(words_a), len(words_b))
    overlap = len(words_a & words_b)

    return (overlap / smaller) >= min_overlap


def _recipient_compatible(a: Any, b: Any) -> bool:
    """Return True if recipients are compatible (same or both absent)."""
    target_a = (a.target_entity or "").lower().strip()
    target_b = (b.target_entity or "").lower().strip()

    # Both absent → compatible
    if not target_a and not target_b:
        return True

    # One absent, other present → compatible (absent is less specific)
    if not target_a or not target_b:
        return True

    # Both present → must overlap
    return target_a in target_b or target_b in target_a


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_merge_candidates(
    new_commitment: Any,
    existing_commitments: list[Any],
    config: MergeConfig | None = None,
) -> list[Any]:
    """Find existing commitments that are likely duplicates of the new one.

    Args:
        new_commitment: The newly created commitment to check.
        existing_commitments: Active commitments for the same user.
        config: Optional thresholds. Defaults to conservative settings.

    Returns:
        List of matching commitments, sorted by confidence (highest first).
        Empty list if no merge candidates found.
    """
    cfg = config or _DEFAULT_CONFIG
    max_delta = timedelta(hours=cfg.timeframe_hours)

    candidates = []

    for existing in existing_commitments:
        # Skip self
        if existing.id == new_commitment.id:
            continue

        # Skip already-discarded commitments
        if getattr(existing, "lifecycle_state", "") == "discarded":
            continue

        # Time proximity check
        delta = abs(new_commitment.created_at - existing.created_at)
        if delta > max_delta:
            continue

        # Commitment type must match (if both have one)
        new_type = (new_commitment.commitment_type or "").lower()
        existing_type = (existing.commitment_type or "").lower()
        if new_type and existing_type and new_type != existing_type:
            continue

        # Actor must match
        if not _actor_matches(new_commitment, existing):
            continue

        # Recipient must be compatible
        if not _recipient_compatible(new_commitment, existing):
            continue

        # Deliverable overlap threshold
        if not _deliverable_overlaps(new_commitment, existing, cfg.min_deliverable_overlap):
            continue

        candidates.append(existing)

    # Sort by confidence descending (highest first = best merge target)
    candidates.sort(
        key=lambda c: float(c.confidence_commitment or 0),
        reverse=True,
    )

    return candidates


def execute_merge(
    canonical: Any,
    duplicate: Any,
    db: Session,
) -> None:
    """Merge a duplicate commitment into the canonical one.

    - Re-links signals from duplicate to canonical
    - Merges context_tags
    - Marks duplicate as discarded with reason "merged::{canonical_id}"

    Does NOT flush — caller owns the transaction.

    Args:
        canonical: The commitment to keep (highest confidence).
        duplicate: The commitment to discard.
        db: SQLAlchemy session.
    """
    # Re-link signals from duplicate to canonical
    signals = db.execute(
        select(CommitmentSignal).where(
            CommitmentSignal.commitment_id == duplicate.id,
        )
    ).scalars().all()

    for signal in signals:
        new_signal = CommitmentSignal(
            commitment_id=canonical.id,
            source_item_id=signal.source_item_id,
            user_id=signal.user_id,
            signal_role=signal.signal_role,
            confidence=signal.confidence,
            interpretation_note=f"Merged from commitment {duplicate.id}",
        )
        db.add(new_signal)

    # Merge context tags
    canonical_tags = set(canonical.context_tags or [])
    duplicate_tags = set(duplicate.context_tags or [])
    merged_tags = canonical_tags | duplicate_tags
    if merged_tags:
        canonical.context_tags = sorted(merged_tags)

    # Mark duplicate as discarded
    duplicate.lifecycle_state = "discarded"
    duplicate.discard_reason = f"merged::{canonical.id}"
