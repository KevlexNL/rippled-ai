"""Surfacing sweep runner — Phase 06.

Service-layer logic called by the recompute_surfacing Celery task.

Flow per commitment:
    1. classify(commitment)
    2. score(classifier_result, commitment)
    3. route(commitment) → surface destination
    4. Update commitment fields (surfaced_as, priority_score, dimension scores)
    5. Set is_surfaced = (surfaced_as IS NOT NULL) for backward compatibility
    6. Append SurfacingAudit row if surfaced_as changed

Returns a summary dict with counts of changes made.

Public API:
    run_surfacing_sweep(db: Session) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Commitment, SurfacingAudit
from app.services.surfacing_router import route

logger = logging.getLogger(__name__)

# Lifecycle states that are eligible for surfacing evaluation
_ACTIVE_STATES = ("proposed", "active", "needs_clarification")


def run_surfacing_sweep(db: Session) -> dict:
    """Recompute surfacing state for all non-terminal commitments.

    Loads all active/proposed/needs_clarification commitments, routes each one,
    updates surfacing fields, and logs changes to SurfacingAudit.

    Args:
        db: Synchronous SQLAlchemy Session.

    Returns:
        Summary dict:
            - evaluated: total commitments evaluated
            - changed: commitments whose surfaced_as changed
            - surfaced: commitments now surfaced (surfaced_as IS NOT NULL)
            - held: commitments routed to None
    """
    now = datetime.now(timezone.utc)

    commitments = db.execute(
        select(Commitment).where(
            Commitment.lifecycle_state.in_(_ACTIVE_STATES)
        )
    ).scalars().all()

    evaluated = len(commitments)
    changed = 0
    surfaced = 0
    held = 0

    for commitment in commitments:
        routing = route(commitment)
        new_surface = routing.surface
        old_surface = commitment.surfaced_as

        # Update dimension scores on commitment
        classifier = routing.classifier
        commitment.timing_strength = classifier.timing_strength
        commitment.business_consequence = classifier.business_consequence
        commitment.cognitive_burden = classifier.cognitive_burden
        commitment.confidence_for_surfacing = Decimal(str(round(classifier.confidence_for_surfacing, 3)))
        commitment.priority_score = Decimal(str(routing.priority_score))
        commitment.surfacing_reason = routing.reason[:255] if routing.reason else None

        # Only write audit + update surfaced_as if destination changed
        if new_surface != old_surface:
            commitment.surfaced_as = new_surface
            # Q1: backward-compat — keep is_surfaced in sync
            commitment.is_surfaced = new_surface is not None
            if new_surface is not None and commitment.surfaced_at is None:
                commitment.surfaced_at = now

            audit = SurfacingAudit(
                commitment_id=commitment.id,
                old_surfaced_as=old_surface,
                new_surfaced_as=new_surface,
                priority_score=Decimal(str(routing.priority_score)),
                reason=routing.reason[:255] if routing.reason else None,
            )
            db.add(audit)
            changed += 1

        if new_surface is not None:
            surfaced += 1
        else:
            held += 1

    if evaluated:
        db.flush()

    logger.info(
        "run_surfacing_sweep: evaluated=%d changed=%d surfaced=%d held=%d",
        evaluated, changed, surfaced, held,
    )

    return {
        "evaluated": evaluated,
        "changed": changed,
        "surfaced": surfaced,
        "held": held,
    }
