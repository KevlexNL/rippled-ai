"""Surfacing sweep runner — Phase 06 + Phase C3.

Service-layer logic called by the recompute_surfacing Celery task.

Flow per commitment:
    1. [C3] DeadlineEventLinker.run() — ensure all active commitments have event links
    2. [C3] Pre-compute proximity_map: commitment_id → hours_until_delivery_event
    3. For each commitment:
        a. classify(commitment)
        b. score(classifier_result, commitment, proximity_hours)  [C3: pass proximity]
        c. route(commitment) → surface destination
        d. Update commitment fields (surfaced_as, priority_score, dimension scores)
        e. Set is_surfaced = (surfaced_as IS NOT NULL) for backward compatibility
        f. Append SurfacingAudit row if surfaced_as changed

Returns a summary dict with counts of changes made.

Public API:
    run_surfacing_sweep(db: Session) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.orm import Commitment, CommitmentEventLink, Event, SurfacingAudit
from app.services.surfacing_router import route

logger = logging.getLogger(__name__)

# Lifecycle states that are eligible for surfacing evaluation.
# in_progress and confirmed surface alongside active — user is working on / aware of these.
# completed and canceled are terminal and never surface.
_ACTIVE_STATES = ("proposed", "active", "needs_clarification", "confirmed", "in_progress")


def _build_proximity_map(db: Session, commitment_ids: list[str]) -> dict[str, float]:
    """Pre-compute hours until next delivery_at event per commitment.

    Returns: dict mapping commitment_id → hours_until_delivery_event
    Negative values indicate the event is in the past.
    """
    if not commitment_ids:
        return {}

    now = datetime.now(timezone.utc)

    rows = db.execute(
        select(
            CommitmentEventLink.commitment_id,
            func.min(Event.starts_at).label("next_starts_at"),
        )
        .join(Event, Event.id == CommitmentEventLink.event_id)
        .where(
            and_(
                CommitmentEventLink.relationship == "delivery_at",
                Event.status != "cancelled",
                CommitmentEventLink.commitment_id.in_(commitment_ids),
            )
        )
        .group_by(CommitmentEventLink.commitment_id)
    ).all()

    result: dict[str, float] = {}
    for row in rows:
        starts_at = row.next_starts_at
        if starts_at is not None:
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=timezone.utc)
            hours = (starts_at - now).total_seconds() / 3600
            result[row.commitment_id] = hours

    return result


def run_surfacing_sweep(db: Session) -> dict:
    """Recompute surfacing state for all non-terminal commitments.

    Loads all active/proposed/needs_clarification commitments, routes each one,
    updates surfacing fields, and logs changes to SurfacingAudit.

    C3 additions:
      - Calls DeadlineEventLinker.run() before scoring to ensure event links exist
      - Pre-fetches proximity map: commitment_id → hours_until_delivery_event
      - Passes proximity_hours to route() (which passes it to score())

    Args:
        db: Synchronous SQLAlchemy Session.

    Returns:
        Summary dict:
            - evaluated: total commitments evaluated
            - changed: commitments whose surfaced_as changed
            - surfaced: commitments now surfaced (surfaced_as IS NOT NULL)
            - held: commitments routed to None
    """
    from app.services.context_assigner import assign_contexts_for_user
    from app.services.event_linker import DeadlineEventLinker

    now = datetime.now(timezone.utc)

    commitments = db.execute(
        select(Commitment).where(
            Commitment.lifecycle_state.in_(_ACTIVE_STATES)
        )
    ).scalars().all()

    # Step 0: Auto-assign contexts for commitments without context_id
    user_ids = {c.user_id for c in commitments if c.user_id}
    context_assigned_total = 0
    for uid in user_ids:
        try:
            result = assign_contexts_for_user(uid, db)
            context_assigned_total += result.get("assigned", 0)
        except Exception:
            logger.exception("Context assignment failed for user %s", uid)
    if context_assigned_total:
        logger.info("run_surfacing_sweep: auto-assigned %d contexts", context_assigned_total)

    # [C3] Step 1: Run deadline event linker for all active commitments
    if commitments:
        # Fetch all non-cancelled events for the linker
        all_events = db.execute(
            select(Event).where(Event.status != "cancelled")
        ).scalars().all()

        # Fetch existing delivery_at links to skip already-linked commitments
        existing_link_ids_rows = db.execute(
            select(CommitmentEventLink.commitment_id).where(
                CommitmentEventLink.relationship == "delivery_at"
            )
        ).scalars().all()
        # Guard: only include string IDs (handles test mocks that return wrong types)
        existing_link_ids = {item for item in existing_link_ids_rows if isinstance(item, str)}

        linker = DeadlineEventLinker()
        linker.run(
            db,
            user_id=None,
            commitments=list(commitments),
            events=all_events,
            existing_link_ids=existing_link_ids,
        )

    # [C3] Step 2: Pre-compute proximity map
    commitment_ids = [c.id for c in commitments]
    proximity_map = _build_proximity_map(db, commitment_ids)

    evaluated = len(commitments)
    changed = 0
    surfaced = 0
    held = 0
    surfaced_main = 0
    surfaced_shortlist = 0

    for commitment in commitments:
        proximity_hours = proximity_map.get(commitment.id)
        routing = route(commitment, proximity_hours=proximity_hours)
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
            if new_surface == "main":
                surfaced_main += 1
            elif new_surface == "shortlist":
                surfaced_shortlist += 1
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
        "surfaced_main": surfaced_main,
        "surfaced_shortlist": surfaced_shortlist,
    }
