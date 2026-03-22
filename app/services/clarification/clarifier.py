"""Clarification orchestrator — Phase 04.

Ties together the analyzer, promoter, and suggestion generator.

Public API:
    run_clarification(candidate_id: str, db: Session) -> dict
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.orm import Clarification, CommitmentCandidate, LifecycleTransition, SourceItem, User
from app.services.clarification.analyzer import AnalysisResult, analyze_candidate
from app.services.clarification.promoter import promote_candidate
from app.services.clarification.suggestions import generate_suggestions
from app.services.event_linker import CounterpartyExtractor
from app.services.identity.owner_resolver import resolve_party_sync
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def run_clarification(candidate_id: str, db: Session) -> dict:
    """Analyze and optionally promote a CommitmentCandidate.

    Flow:
    1. Load candidate; raise ValueError if not found.
    2. If already promoted or discarded → return skipped.
    3. Analyze candidate for ambiguity issues.
    4. If observation window is open AND no critical issues → defer.
    5. Promote candidate to Commitment.
    5a. Flush commitment immediately — ensures FK constraints are satisfied
        before Clarification / LifecycleTransition rows are inserted.
    5b. Enrich counterparty (C3).
    6. Generate suggested values.
    7. Create Clarification row.
    8. Create LifecycleTransition record.
    9. Flush (caller commits).

    Args:
        candidate_id: UUID string of the CommitmentCandidate to process.
        db: Synchronous SQLAlchemy Session.

    Returns:
        Dict with 'status' key: 'clarified' | 'deferred' | 'skipped'.

    Raises:
        ValueError: If the candidate is not found.
    """
    candidate: CommitmentCandidate | None = db.get(CommitmentCandidate, candidate_id)
    if candidate is None:
        raise ValueError(f"CommitmentCandidate {candidate_id!r} not found")

    # Step 2 — already processed
    if candidate.was_promoted or candidate.was_discarded:
        logger.info(
            "Candidate %s already processed (promoted=%s, discarded=%s) — skipping",
            candidate_id, candidate.was_promoted, candidate.was_discarded,
        )
        return {"status": "skipped", "reason": "already processed"}

    # Step 3 — analyze
    analysis: AnalysisResult = analyze_candidate(candidate)
    logger.debug(
        "Candidate %s analyzed: issues=%s severity=%s obs=%s rec=%s",
        candidate_id,
        [i.value for i in analysis.issue_types],
        analysis.issue_severity,
        analysis.observation_window_status,
        analysis.surface_recommendation,
    )

    # Step 4 — defer if window is open and no critical issues
    # High-confidence candidates (>= 0.75) skip the observation window
    from decimal import Decimal as D
    from app.services.clarification.analyzer import _is_critical
    critical_issues = [i for i in analysis.issue_types if _is_critical(i)]
    high_confidence = (candidate.confidence_score or D("0")) >= D("0.75")

    if analysis.observation_window_status == "open" and not critical_issues and not high_confidence:
        logger.info("Candidate %s deferred — observation window open, no critical issues", candidate_id)
        return {"status": "deferred", "candidate_id": str(candidate_id)}

    # Step 5 — promote
    commitment = promote_candidate(candidate, db, analysis)
    logger.info("Candidate %s promoted to commitment %s", candidate_id, commitment.id)

    # Step 5a — apply requester/beneficiary from model detection
    entities = candidate.linked_entities or {}
    if entities.get("requester"):
        commitment.requester_name = entities["requester"]
        # Resolve requester against identity profiles
        resolved = resolve_party_sync(entities["requester"], candidate.user_id, db)
        if resolved:
            commitment.requester_resolved = resolved
    if entities.get("beneficiary"):
        commitment.beneficiary_name = entities["beneficiary"]
        resolved = resolve_party_sync(entities["beneficiary"], candidate.user_id, db)
        if resolved:
            commitment.beneficiary_resolved = resolved

    # If requester resolved to the logged-in user, override relationship to 'mine'
    if getattr(commitment, "requester_resolved", None) == candidate.user_id:
        commitment.user_relationship = "mine"

    # Step 5b — flush commitment NOW so FK constraints on Clarification /
    # LifecycleTransition are satisfied when those rows are inserted.
    # Without this flush, SQLAlchemy may emit the child INSERTs before the
    # parent Commitment INSERT, causing IntegrityError → infinite retry loop.
    db.flush()

    # Step 5c — [C3] enrich counterparty before flush
    try:
        settings = get_settings()
        source_item = None
        if candidate.originating_item_id:
            source_item = db.get(SourceItem, candidate.originating_item_id)
        user = db.get(User, candidate.user_id)
        user_email = user.email if user else ""
        extractor = CounterpartyExtractor(settings=settings, user_email=user_email)
        extractor.extract(commitment, source_item, user_email=user_email)
    except Exception as exc:
        logger.warning("CounterpartyExtractor failed (non-fatal): %s", exc)

    # Step 6 — generate suggestions
    suggested_values = generate_suggestions(candidate, analysis.issue_types)

    # Step 7 — create Clarification row
    clarification = Clarification(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=candidate.user_id,
        issue_types=[i.value for i in analysis.issue_types],
        issue_severity=analysis.issue_severity,
        why_this_matters=analysis.why_this_matters,
        observation_window_status=analysis.observation_window_status,
        suggested_values=suggested_values,
        supporting_evidence=[],
        surface_recommendation=analysis.surface_recommendation,
    )
    db.add(clarification)

    # Step 8 — create LifecycleTransition
    transition = LifecycleTransition(
        id=str(uuid.uuid4()),
        commitment_id=commitment.id,
        user_id=candidate.user_id,
        from_state=None,
        to_state=commitment.lifecycle_state,
        trigger_reason="phase04_clarification",
    )
    db.add(transition)

    # Step 9 — flush (caller commits)
    db.flush()

    return {
        "status": "clarified",
        "commitment_id": str(commitment.id),
        "surface_recommendation": analysis.surface_recommendation,
    }
