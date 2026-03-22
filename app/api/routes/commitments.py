from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, CommitmentAmbiguity, CommitmentEventLink, CommitmentSignal, Event, LifecycleTransition, SourceItem, SurfacingAudit
from app.models.schemas import (
    CommitmentAmbiguityCreate,
    CommitmentAmbiguityRead,
    CommitmentCreate,
    CommitmentRead,
    CommitmentSignalCreate,
    CommitmentSignalEnrichedRead,
    CommitmentSignalRead,
    CommitmentUpdate,
    LinkedEventRead,
)

router = APIRouter(prefix="/commitments", tags=["commitments"])

VALID_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["active", "confirmed", "dormant", "needs_clarification", "discarded"],
    "active": ["confirmed", "dormant", "needs_clarification", "delivered", "closed", "discarded"],
    "confirmed": ["dormant", "delivered", "closed", "discarded"],
    "dormant": ["active", "confirmed", "discarded"],
    "needs_clarification": ["active", "confirmed", "dormant", "discarded"],
    "delivered": ["closed", "discarded"],
    "closed": ["discarded"],
    "discarded": [],
}


def _commitment_to_schema(row: Commitment, origin_source: SourceItem | None = None) -> CommitmentRead:
    schema = CommitmentRead.model_validate(row)
    schema.linked_events = []
    if origin_source:
        schema.source_sender_name = origin_source.sender_name
        schema.source_sender_email = origin_source.sender_email
        schema.source_occurred_at = origin_source.occurred_at
    return schema


async def _fetch_origin_source_map(
    commitment_ids: list[str], db: AsyncSession
) -> dict[str, SourceItem]:
    """Batch-fetch the origin source item for a list of commitment IDs."""
    if not commitment_ids:
        return {}
    result = await db.execute(
        select(CommitmentSignal.commitment_id, SourceItem)
        .join(SourceItem, SourceItem.id == CommitmentSignal.source_item_id)
        .where(
            CommitmentSignal.commitment_id.in_(commitment_ids),
            CommitmentSignal.signal_role == "origin",
        )
        .order_by(CommitmentSignal.created_at.asc())
    )
    source_map: dict[str, SourceItem] = {}
    for commitment_id, source_item in result:
        if commitment_id not in source_map:
            source_map[commitment_id] = source_item
    return source_map


async def _build_commitment_with_events(row: Commitment, db: AsyncSession) -> CommitmentRead:
    """Build CommitmentRead with linked_events and origin source for single-commitment endpoints."""
    result = await db.execute(
        select(CommitmentEventLink, Event)
        .join(Event, Event.id == CommitmentEventLink.event_id)
        .where(
            CommitmentEventLink.commitment_id == row.id,
            CommitmentEventLink.relationship == "delivery_at",
            Event.status != "cancelled",
        )
        .order_by(Event.starts_at.asc())
    )
    pairs = list(result)
    source_map = await _fetch_origin_source_map([row.id], db)
    origin_source = source_map.get(row.id)
    schema = CommitmentRead.model_validate(row)
    schema.linked_events = [
        LinkedEventRead(
            event_id=event.id,
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            relationship=link.relationship,
        )
        for link, event in pairs
    ]
    if origin_source:
        schema.source_sender_name = origin_source.sender_name
        schema.source_sender_email = origin_source.sender_email
        schema.source_occurred_at = origin_source.occurred_at
    return schema


def _signal_to_schema(row: CommitmentSignal) -> CommitmentSignalRead:
    return CommitmentSignalRead.model_validate(row)


def _ambiguity_to_schema(row: CommitmentAmbiguity) -> CommitmentAmbiguityRead:
    return CommitmentAmbiguityRead.model_validate(row)


async def _get_commitment_or_404(commitment_id: str, user_id: str, db: AsyncSession) -> Commitment:
    result = await db.execute(
        select(Commitment).where(Commitment.id == commitment_id, Commitment.user_id == user_id)
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return commitment


# ---------------------------------------------------------------------------
# Commitments
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CommitmentRead])
async def list_commitments(
    lifecycle_state: str | None = Query(None),
    priority_class: str | None = Query(None),
    relationship: str | None = Query(None, description="Filter: mine, contributing, watching, or mine+contributing"),
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    q = select(Commitment).where(Commitment.user_id == user_id)
    if lifecycle_state:
        q = q.where(Commitment.lifecycle_state == lifecycle_state)
    if priority_class:
        q = q.where(Commitment.priority_class == priority_class)
    if relationship:
        allowed = [r.strip() for r in relationship.split("+")]
        q = q.where(Commitment.user_relationship.in_(allowed))
    q = q.order_by(Commitment.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    rows = list(result.scalars())
    source_map = await _fetch_origin_source_map([r.id for r in rows], db)
    return [_commitment_to_schema(row, source_map.get(row.id)) for row in rows]


@router.post("", response_model=CommitmentRead, status_code=201)
async def create_commitment(
    body: CommitmentCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    commitment = Commitment(
        user_id=user_id,
        title=body.title,
        context_id=body.context_id,
        description=body.description,
        commitment_text=body.commitment_text,
        commitment_type=body.commitment_type,
        priority_class=body.priority_class,
        context_type=body.context_type,
        owner_candidates=body.owner_candidates,
        resolved_owner=body.resolved_owner,
        suggested_owner=body.suggested_owner,
        ownership_ambiguity=body.ownership_ambiguity,
        deadline_candidates=body.deadline_candidates,
        resolved_deadline=body.resolved_deadline,
        vague_time_phrase=body.vague_time_phrase,
        suggested_due_date=body.suggested_due_date,
        timing_ambiguity=body.timing_ambiguity,
        deliverable=body.deliverable,
        target_entity=body.target_entity,
        suggested_next_step=body.suggested_next_step,
        deliverable_ambiguity=body.deliverable_ambiguity,
        confidence_commitment=body.confidence_commitment,
        confidence_actionability=body.confidence_actionability,
        commitment_explanation=body.commitment_explanation,
        counterparty_name=body.counterparty_name,
        counterparty_resolved=body.counterparty_resolved,
        requester_name=body.requester_name,
        requester_email=body.requester_email,
        beneficiary_name=body.beneficiary_name,
        beneficiary_email=body.beneficiary_email,
        user_relationship=body.user_relationship,
        structure_complete=body.structure_complete,
        observe_until=body.observe_until,
        observation_window_hours=body.observation_window_hours,
        lifecycle_state="proposed",
    )
    db.add(commitment)
    await db.flush()
    await db.refresh(commitment)
    return _commitment_to_schema(commitment)


@router.get("/{commitment_id}", response_model=CommitmentRead)
async def get_commitment(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    commitment = await _get_commitment_or_404(commitment_id, user_id, db)
    return await _build_commitment_with_events(commitment, db)


@router.patch("/{commitment_id}", response_model=CommitmentRead)
async def update_commitment(
    commitment_id: str,
    body: CommitmentUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    commitment = await _get_commitment_or_404(commitment_id, user_id, db)

    # Enforce lifecycle transition
    if body.lifecycle_state is not None:
        new_state = body.lifecycle_state
        current_state = commitment.lifecycle_state
        allowed = VALID_TRANSITIONS.get(current_state, [])
        if new_state not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition: {current_state} → {new_state}. Allowed: {allowed}",
            )
        old_state = commitment.lifecycle_state
        commitment.lifecycle_state = new_state
        commitment.state_changed_at = datetime.now(timezone.utc)

        transition = LifecycleTransition(
            commitment_id=commitment_id,
            user_id=user_id,
            from_state=old_state,
            to_state=new_state,
            trigger_reason="human_update",
        )
        db.add(transition)

    if body.context_id is not None:
        commitment.context_id = body.context_id
    if body.title is not None:
        commitment.title = body.title
    if body.description is not None:
        commitment.description = body.description
    if body.resolved_owner is not None:
        commitment.resolved_owner = body.resolved_owner
    if body.resolved_deadline is not None:
        commitment.resolved_deadline = body.resolved_deadline
    if body.deliverable is not None:
        commitment.deliverable = body.deliverable
    if body.confidence_actionability is not None:
        commitment.confidence_actionability = body.confidence_actionability
    if body.is_surfaced is not None:
        commitment.is_surfaced = body.is_surfaced
        if body.is_surfaced and not commitment.surfaced_at:
            commitment.surfaced_at = datetime.now(timezone.utc)

    commitment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(commitment)
    return _commitment_to_schema(commitment)


@router.delete("/{commitment_id}", status_code=204)
async def delete_commitment(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    commitment = await _get_commitment_or_404(commitment_id, user_id, db)

    current_state = commitment.lifecycle_state
    allowed = VALID_TRANSITIONS.get(current_state, [])
    if "discarded" not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot discard commitment in state: {current_state}",
        )

    old_state = commitment.lifecycle_state
    commitment.lifecycle_state = "discarded"
    commitment.state_changed_at = datetime.now(timezone.utc)
    commitment.updated_at = datetime.now(timezone.utc)

    transition = LifecycleTransition(
        commitment_id=commitment_id,
        user_id=user_id,
        from_state=old_state,
        to_state="discarded",
        trigger_reason="human_delete",
    )
    db.add(transition)


# ---------------------------------------------------------------------------
# Skip
# ---------------------------------------------------------------------------


class SkipBody(BaseModel):
    reason: str | None = None


@router.post("/{commitment_id}/skip", response_model=CommitmentRead)
async def skip_commitment(
    commitment_id: str,
    body: SkipBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    """Skip a commitment — removes from review queue without changing lifecycle_state."""
    commitment = await _get_commitment_or_404(commitment_id, user_id, db)

    commitment.skipped_at = datetime.now(timezone.utc)
    commitment.skip_reason = body.reason
    commitment.updated_at = datetime.now(timezone.utc)

    # Log to surfacing_audit
    audit = SurfacingAudit(
        commitment_id=commitment_id,
        old_surfaced_as=commitment.surfaced_as,
        new_surfaced_as=commitment.surfaced_as,  # unchanged
        priority_score=commitment.priority_score,
        reason="skipped",
        user_id=user_id,
    )
    db.add(audit)

    await db.flush()
    await db.refresh(commitment)
    return _commitment_to_schema(commitment)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@router.get("/{commitment_id}/signals", response_model=list[CommitmentSignalEnrichedRead])
async def list_signals(
    commitment_id: str,
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentSignalEnrichedRead]:
    await _get_commitment_or_404(commitment_id, user_id, db)
    result = await db.execute(
        select(CommitmentSignal, SourceItem)
        .join(SourceItem, SourceItem.id == CommitmentSignal.source_item_id)
        .where(CommitmentSignal.commitment_id == commitment_id, CommitmentSignal.user_id == user_id)
        .order_by(CommitmentSignal.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    out: list[CommitmentSignalEnrichedRead] = []
    for signal, source_item in result:
        enriched = CommitmentSignalEnrichedRead.model_validate(signal)
        enriched.source = source_item.source_type
        enriched.text = source_item.content
        out.append(enriched)
    return out


@router.post("/{commitment_id}/signals", response_model=CommitmentSignalRead, status_code=201)
async def create_signal(
    commitment_id: str,
    body: CommitmentSignalCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentSignalRead:
    await _get_commitment_or_404(commitment_id, user_id, db)
    signal = CommitmentSignal(
        commitment_id=commitment_id,
        source_item_id=body.source_item_id,
        user_id=user_id,
        signal_role=body.signal_role,
        confidence=body.confidence,
        interpretation_note=body.interpretation_note,
    )
    db.add(signal)
    await db.flush()
    await db.refresh(signal)
    return _signal_to_schema(signal)


# ---------------------------------------------------------------------------
# Ambiguities
# ---------------------------------------------------------------------------

@router.get("/{commitment_id}/ambiguities", response_model=list[CommitmentAmbiguityRead])
async def list_ambiguities(
    commitment_id: str,
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentAmbiguityRead]:
    await _get_commitment_or_404(commitment_id, user_id, db)
    result = await db.execute(
        select(CommitmentAmbiguity)
        .where(CommitmentAmbiguity.commitment_id == commitment_id, CommitmentAmbiguity.user_id == user_id)
        .order_by(CommitmentAmbiguity.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_ambiguity_to_schema(row) for row in result.scalars()]


@router.post("/{commitment_id}/ambiguities", response_model=CommitmentAmbiguityRead, status_code=201)
async def create_ambiguity(
    commitment_id: str,
    body: CommitmentAmbiguityCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentAmbiguityRead:
    await _get_commitment_or_404(commitment_id, user_id, db)
    ambiguity = CommitmentAmbiguity(
        commitment_id=commitment_id,
        user_id=user_id,
        ambiguity_type=body.ambiguity_type,
        description=body.description,
    )
    db.add(ambiguity)
    await db.flush()
    await db.refresh(ambiguity)
    return _ambiguity_to_schema(ambiguity)


class AmbiguityPatch(BaseModel):
    is_resolved: bool
    resolved_by_item_id: str | None = None


# ---------------------------------------------------------------------------
# [C3] Delivery state models
# ---------------------------------------------------------------------------

_VALID_DELIVERY_STATES = frozenset({
    "draft_sent", "acknowledged", "rescheduled", "partial",
    "delivered", "closed_no_delivery",
})


class DeliveryStatePatch(BaseModel):
    state: str
    note: str | None = None


class CommitmentEventLinkRead(BaseModel):
    id: str
    commitment_id: str
    event_id: str
    relationship: str
    confidence: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class CommitmentEventLinkCreate(BaseModel):
    event_id: str
    relationship: str = "delivery_at"


@router.patch("/{commitment_id}/ambiguities/{ambiguity_id}", response_model=CommitmentAmbiguityRead)
async def patch_ambiguity(
    commitment_id: str,
    ambiguity_id: str,
    body: AmbiguityPatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentAmbiguityRead:
    await _get_commitment_or_404(commitment_id, user_id, db)
    result = await db.execute(
        select(CommitmentAmbiguity).where(
            CommitmentAmbiguity.id == ambiguity_id,
            CommitmentAmbiguity.commitment_id == commitment_id,
            CommitmentAmbiguity.user_id == user_id,
        )
    )
    ambiguity = result.scalar_one_or_none()
    if not ambiguity:
        raise HTTPException(status_code=404, detail="Ambiguity not found")

    ambiguity.is_resolved = body.is_resolved
    if body.resolved_by_item_id is not None:
        ambiguity.resolved_by_item_id = body.resolved_by_item_id
    if body.is_resolved and not ambiguity.resolved_at:
        ambiguity.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(ambiguity)
    return _ambiguity_to_schema(ambiguity)


# ---------------------------------------------------------------------------
# [C3] Delivery State
# ---------------------------------------------------------------------------


@router.patch("/{commitment_id}/delivery-state", response_model=CommitmentRead)
async def patch_delivery_state(
    commitment_id: str,
    body: DeliveryStatePatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    """Update the delivery state of a commitment.

    Special state 'pending': marks post_event_reviewed=True without changing delivery_state.
    State 'delivered': also sets lifecycle_state='delivered' atomically.
    """
    _PENDING_STATE = "pending"

    commitment = await _get_commitment_or_404(commitment_id, user_id, db)

    if body.state == _PENDING_STATE:
        # Special: just mark post_event_reviewed=true, don't change delivery_state
        commitment.post_event_reviewed = True
        commitment.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(commitment)
        return _commitment_to_schema(commitment)

    if body.state not in _VALID_DELIVERY_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid delivery state: {body.state!r}. Must be one of {sorted(_VALID_DELIVERY_STATES)}",
        )

    commitment.delivery_state = body.state
    commitment.updated_at = datetime.now(timezone.utc)

    # When delivered, also sync lifecycle_state atomically
    if body.state == "delivered":
        old_state = commitment.lifecycle_state
        allowed = VALID_TRANSITIONS.get(old_state, [])
        if "delivered" in allowed:
            commitment.lifecycle_state = "delivered"
            commitment.state_changed_at = datetime.now(timezone.utc)
            transition = LifecycleTransition(
                commitment_id=commitment_id,
                user_id=user_id,
                from_state=old_state,
                to_state="delivered",
                trigger_reason="delivery_state_update",
            )
            db.add(transition)

    await db.flush()
    await db.refresh(commitment)
    return _commitment_to_schema(commitment)


# ---------------------------------------------------------------------------
# [C3] Commitment ↔ Event links
# ---------------------------------------------------------------------------


@router.get("/{commitment_id}/events", response_model=list[CommitmentEventLinkRead])
async def list_commitment_events(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentEventLinkRead]:
    """List all event links for a commitment."""
    await _get_commitment_or_404(commitment_id, user_id, db)
    result = await db.execute(
        select(CommitmentEventLink)
        .where(CommitmentEventLink.commitment_id == commitment_id)
        .order_by(CommitmentEventLink.created_at.desc())
    )
    links = result.scalars().all()
    return [CommitmentEventLinkRead.model_validate(link) for link in links]


@router.post("/{commitment_id}/events", response_model=CommitmentEventLinkRead, status_code=201)
async def create_commitment_event_link(
    commitment_id: str,
    body: CommitmentEventLinkCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentEventLinkRead:
    """Manually link a commitment to an event."""
    import uuid as _uuid
    from decimal import Decimal

    await _get_commitment_or_404(commitment_id, user_id, db)

    # Verify event exists
    event_result = await db.execute(select(Event).where(Event.id == body.event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    link = CommitmentEventLink(
        id=str(_uuid.uuid4()),
        commitment_id=commitment_id,
        event_id=body.event_id,
        relationship=body.relationship,
        confidence=Decimal("1.000"),
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return CommitmentEventLinkRead.model_validate(link)
