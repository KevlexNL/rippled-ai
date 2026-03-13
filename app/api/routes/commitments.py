from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, CommitmentAmbiguity, CommitmentSignal, LifecycleTransition
from app.models.schemas import (
    CommitmentAmbiguityCreate,
    CommitmentAmbiguityRead,
    CommitmentCreate,
    CommitmentRead,
    CommitmentSignalCreate,
    CommitmentSignalRead,
    CommitmentUpdate,
)

router = APIRouter(prefix="/commitments", tags=["commitments"])

VALID_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["active", "needs_clarification", "discarded"],
    "active": ["needs_clarification", "delivered", "closed", "discarded"],
    "needs_clarification": ["active", "discarded"],
    "delivered": ["closed", "discarded"],
    "closed": ["discarded"],
    "discarded": [],
}


def _commitment_to_schema(row: Commitment) -> CommitmentRead:
    return CommitmentRead.model_validate(row)


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
    q = q.order_by(Commitment.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [_commitment_to_schema(row) for row in result.scalars()]


@router.post("", response_model=CommitmentRead, status_code=201)
async def create_commitment(
    body: CommitmentCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentRead:
    commitment = Commitment(
        user_id=user_id,
        title=body.title,
        description=body.description,
        commitment_text=body.commitment_text,
        commitment_type=body.commitment_type.value if body.commitment_type else None,
        priority_class=body.priority_class.value if body.priority_class else None,
        context_type=body.context_type,
        owner_candidates=body.owner_candidates,
        resolved_owner=body.resolved_owner,
        suggested_owner=body.suggested_owner,
        ownership_ambiguity=body.ownership_ambiguity.value if body.ownership_ambiguity else None,
        deadline_candidates=body.deadline_candidates,
        resolved_deadline=body.resolved_deadline,
        vague_time_phrase=body.vague_time_phrase,
        suggested_due_date=body.suggested_due_date,
        timing_ambiguity=body.timing_ambiguity.value if body.timing_ambiguity else None,
        deliverable=body.deliverable,
        target_entity=body.target_entity,
        suggested_next_step=body.suggested_next_step,
        deliverable_ambiguity=body.deliverable_ambiguity.value if body.deliverable_ambiguity else None,
        confidence_commitment=body.confidence_commitment,
        confidence_actionability=body.confidence_actionability,
        commitment_explanation=body.commitment_explanation,
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
    return _commitment_to_schema(commitment)


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
# Signals
# ---------------------------------------------------------------------------

@router.get("/{commitment_id}/signals", response_model=list[CommitmentSignalRead])
async def list_signals(
    commitment_id: str,
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentSignalRead]:
    await _get_commitment_or_404(commitment_id, user_id, db)
    result = await db.execute(
        select(CommitmentSignal)
        .where(CommitmentSignal.commitment_id == commitment_id, CommitmentSignal.user_id == user_id)
        .order_by(CommitmentSignal.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_signal_to_schema(row) for row in result.scalars()]


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
