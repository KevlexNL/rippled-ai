"""Clarifications API routes — Phase C5."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Clarification, Commitment, LifecycleTransition

router = APIRouter(prefix="/clarifications", tags=["clarifications"])


class ClarificationRead(BaseModel):
    id: str
    commitment_id: str
    suggested_clarification_prompt: str | None
    suggested_values: dict
    resolved_at: str | None
    issue_types: list | None = None

    class Config:
        from_attributes = True


class ClarificationRespondRead(BaseModel):
    id: str
    resolved_at: str


class ClarificationRespondBody(BaseModel):
    answer: str


@router.get("", response_model=list[ClarificationRead])
async def list_clarifications(
    commitment_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[ClarificationRead]:
    """Get open (unresolved) clarifications for a commitment."""
    # Verify commitment belongs to user
    commitment_result = await db.execute(
        select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.user_id == user_id,
        )
    )
    if not commitment_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Commitment not found")

    result = await db.execute(
        select(Clarification)
        .where(
            Clarification.commitment_id == commitment_id,
            Clarification.resolved_at.is_(None),
        )
        .order_by(Clarification.created_at.asc())
    )
    clarifications = result.scalars().all()
    return [
        ClarificationRead(
            id=c.id,
            commitment_id=c.commitment_id,
            suggested_clarification_prompt=c.suggested_clarification_prompt,
            suggested_values=c.suggested_values,
            resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
            issue_types=c.issue_types,
        )
        for c in clarifications
    ]


@router.post("/{clarification_id}/respond", response_model=ClarificationRespondRead)
async def respond_to_clarification(
    clarification_id: str,
    body: ClarificationRespondBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ClarificationRespondRead:
    """Respond to a clarification, transitioning commitment to active."""
    # Fetch clarification
    result = await db.execute(
        select(Clarification).where(Clarification.id == clarification_id)
    )
    clarification = result.scalar_one_or_none()
    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found")

    if clarification.resolved_at is not None:
        raise HTTPException(status_code=409, detail="Clarification already resolved")

    # Fetch commitment (and verify ownership)
    commitment_result = await db.execute(
        select(Commitment).where(
            Commitment.id == clarification.commitment_id,
            Commitment.user_id == user_id,
        )
    )
    commitment = commitment_result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    now = datetime.now(timezone.utc)

    # Mark clarification resolved
    clarification.resolved_at = now
    clarification.updated_at = now

    # Transition commitment to active (if in needs_clarification)
    if commitment.lifecycle_state == "needs_clarification":
        old_state = commitment.lifecycle_state
        commitment.lifecycle_state = "active"
        commitment.state_changed_at = now
        commitment.updated_at = now

        transition = LifecycleTransition(
            commitment_id=commitment.id,
            user_id=user_id,
            from_state=old_state,
            to_state="active",
            trigger_reason="clarification_answered",
        )
        db.add(transition)

    await db.flush()

    return ClarificationRespondRead(
        id=clarification.id,
        resolved_at=clarification.resolved_at.isoformat(),
    )
