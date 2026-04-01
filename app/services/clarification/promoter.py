"""Commitment promoter — Phase 04.

Promotes a CommitmentCandidate to a full Commitment, creating the join
record and per-issue CommitmentAmbiguity rows.

Public API:
    promote_candidate(candidate, db, analysis) -> Commitment
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import AmbiguityType
from app.models.orm import (
    CandidateCommitment,
    Commitment,
    CommitmentAmbiguity,
    CommitmentSignal,
)
from app.services.clarification.analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Fragment gate — minimum text length for promotion
# ---------------------------------------------------------------------------

MIN_CANDIDATE_TEXT_LENGTH = 10
"""Candidates with raw_text shorter than this (after stripping) are discarded."""


# ---------------------------------------------------------------------------
# Title derivation
# ---------------------------------------------------------------------------

_TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:I'll\s+|I will\s+|We'll\s+|We will\s+|I'm going to\s+)",
    re.IGNORECASE,
)


def _derive_title(raw_text: str) -> str:
    """Normalize raw_text to an action phrase for use as commitment title.

    Strips first-person prefixes and capitalizes. Falls back to raw_text[:200].
    """
    text = (raw_text or "").strip()
    if not text:
        return "Untitled commitment"

    stripped = _TITLE_PREFIX_PATTERN.sub("", text)
    if stripped and stripped != text:
        # Capitalize first char
        title = stripped[0].upper() + stripped[1:]
    else:
        title = text

    return title[:200]


# ---------------------------------------------------------------------------
# Context type derivation
# ---------------------------------------------------------------------------

def _derive_context_type(candidate: Any) -> str:
    ctx = candidate.context_window or {}
    if ctx.get("has_external_recipient"):
        return "external"
    return "internal"


# ---------------------------------------------------------------------------
# Ambiguity field derivation
# ---------------------------------------------------------------------------

_OWNERSHIP_ISSUES = {AmbiguityType.owner_missing, AmbiguityType.owner_vague_collective}
_TIMING_ISSUES = {
    AmbiguityType.timing_missing,
    AmbiguityType.timing_vague,
    AmbiguityType.timing_conflicting,
}
_DELIVERABLE_ISSUES = {AmbiguityType.deliverable_unclear, AmbiguityType.target_unclear}




# ---------------------------------------------------------------------------
# Context tags derivation
# ---------------------------------------------------------------------------

_SOURCE_TYPE_TAG_MAP: dict[str, list[str]] = {
    "slack": ["slack"],
    "email": ["email"],
    "meeting": ["meeting"],
}


def _derive_context_tags(candidate: Any) -> list[str] | None:
    """Derive context_tags from the candidate's signal source type."""
    source_type = getattr(candidate, "source_type", None)
    if not source_type:
        return None
    return _SOURCE_TYPE_TAG_MAP.get(str(source_type).lower())

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def promote_candidate(
    candidate: Any,
    db: Session,
    analysis: AnalysisResult,
) -> Commitment:
    """Promote a CommitmentCandidate to a Commitment.

    Creates the Commitment, CandidateCommitment join record, and one
    CommitmentAmbiguity row per issue type. Marks candidate.was_promoted = True.

    Does NOT flush — caller owns the transaction.

    Args:
        candidate: CommitmentCandidate ORM object.
        db: Synchronous SQLAlchemy Session.
        analysis: AnalysisResult from analyze_candidate().

    Returns:
        The newly created Commitment (not yet flushed).

    Raises:
        ValueError: If candidate is already promoted or discarded.
    """
    # Fragment gate: reject candidates with raw_text too short to be a real commitment
    stripped_text = (candidate.raw_text or "").strip()
    if len(stripped_text) < MIN_CANDIDATE_TEXT_LENGTH:
        candidate.was_discarded = True
        raise ValueError(
            f"Candidate {candidate.id!r} raw_text too short "
            f"({len(stripped_text)} chars < {MIN_CANDIDATE_TEXT_LENGTH})"
        )

    if candidate.was_promoted:
        raise ValueError(
            f"Candidate {candidate.id!r} is already promoted"
        )
    if candidate.was_discarded:
        raise ValueError(
            f"Candidate {candidate.id!r} is already discarded"
        )

    issue_types = analysis.issue_types
    context_type = _derive_context_type(candidate)

    # Derive title from raw_text
    title = _derive_title(candidate.raw_text or "")

    # Ambiguity flags
    ownership_ambiguity = any(i in _OWNERSHIP_ISSUES for i in issue_types)
    timing_ambiguity = any(i in _TIMING_ISSUES for i in issue_types)
    deliverable_ambiguity = any(i in _DELIVERABLE_ISSUES for i in issue_types)


    # Lifecycle state
    lifecycle_state = "needs_clarification" if issue_types else "proposed"

    commitment_id = str(uuid.uuid4())

    commitment = Commitment(
        id=commitment_id,
        user_id=candidate.user_id,
        title=title,
        commitment_text=candidate.raw_text,
        context_type=context_type,
        ownership_ambiguity="missing" if ownership_ambiguity else None,
        timing_ambiguity="missing" if timing_ambiguity else None,
        deliverable_ambiguity="unclear" if deliverable_ambiguity else None,
        suggested_owner=None,
        suggested_due_date=None,  # Phase 04 does not parse date strings to datetime
        suggested_next_step=None,
        confidence_commitment=candidate.confidence_score,
        confidence_actionability=candidate.confidence_score,
        observe_until=candidate.observe_until,
        lifecycle_state=lifecycle_state,
        structure_complete=True,
        context_tags=_derive_context_tags(candidate),
    )
    db.add(commitment)
    # Flush commitment first so FK constraints on CandidateCommitment and
    # CommitmentAmbiguity are satisfied — SQLAlchemy cannot infer insert
    # order from raw UUID FK columns without ORM relationships.
    db.flush()

    # CandidateCommitment join
    join_record = CandidateCommitment(
        id=str(uuid.uuid4()),
        candidate_id=candidate.id,
        commitment_id=commitment_id,
    )
    db.add(join_record)

    # Origin signal — link commitment back to its source item
    if candidate.originating_item_id:
        signal = CommitmentSignal(
            commitment_id=commitment_id,
            source_item_id=candidate.originating_item_id,
            user_id=candidate.user_id,
            signal_role="origin",
            confidence=candidate.confidence_score,
            interpretation_note=f"Promoted from candidate {candidate.id}",
        )
        db.add(signal)

    # CommitmentAmbiguity per issue type
    for issue in issue_types:
        ambiguity = CommitmentAmbiguity(
            id=str(uuid.uuid4()),
            commitment_id=commitment_id,
            user_id=candidate.user_id,
            ambiguity_type=issue.value,
        )
        db.add(ambiguity)

    # Mark candidate as promoted
    candidate.was_promoted = True

    return commitment
