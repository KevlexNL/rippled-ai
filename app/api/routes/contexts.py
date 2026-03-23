import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, CommitmentContext
from app.models.schemas import (
    CommitmentContextCreate,
    CommitmentContextRead,
    CommitmentRead,
)
from app.services.context_assigner import match_commitment_to_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contexts", tags=["contexts"])


def _context_to_schema(row: CommitmentContext, count: int) -> CommitmentContextRead:
    schema = CommitmentContextRead.model_validate(row)
    schema.commitment_count = count
    return schema


@router.get("", response_model=list[CommitmentContextRead])
async def list_contexts(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentContextRead]:
    """List all contexts for the current user with commitment counts."""
    # Subquery for commitment count per context
    count_subq = (
        select(
            Commitment.context_id,
            func.count(Commitment.id).label("cnt"),
        )
        .where(Commitment.user_id == user_id, Commitment.context_id.isnot(None))
        .group_by(Commitment.context_id)
        .subquery()
    )

    result = await db.execute(
        select(CommitmentContext, func.coalesce(count_subq.c.cnt, 0).label("commitment_count"))
        .outerjoin(count_subq, CommitmentContext.id == count_subq.c.context_id)
        .where(CommitmentContext.user_id == user_id)
        .order_by(CommitmentContext.name)
    )
    rows = result.all()
    return [_context_to_schema(ctx, cnt) for ctx, cnt in rows]


@router.get("/{context_id}/commitments", response_model=list[CommitmentRead])
async def list_context_commitments(
    context_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """List all commitments belonging to a context."""
    # Verify context exists and belongs to user
    ctx_result = await db.execute(
        select(CommitmentContext).where(
            CommitmentContext.id == context_id,
            CommitmentContext.user_id == user_id,
        )
    )
    if not ctx_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Context not found")

    result = await db.execute(
        select(Commitment)
        .where(Commitment.context_id == context_id, Commitment.user_id == user_id)
        .order_by(Commitment.created_at.desc())
    )
    commitments = result.scalars().all()
    return [CommitmentRead.model_validate(c) for c in commitments]


@router.post("", response_model=CommitmentContextRead, status_code=201)
async def create_context(
    body: CommitmentContextCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentContextRead:
    """Create a new context (internal/admin use)."""
    context = CommitmentContext(
        user_id=user_id,
        name=body.name,
        summary=body.summary,
    )
    db.add(context)
    await db.flush()
    await db.refresh(context)
    return _context_to_schema(context, 0)


class AutoAssignResult(BaseModel):
    total: int
    assigned: int
    skipped: int


@router.post("/auto-assign", response_model=AutoAssignResult)
async def bulk_auto_assign(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AutoAssignResult:
    """Bulk auto-assign contexts to unassigned commitments for the current user."""
    # Load all contexts for user
    ctx_result = await db.execute(
        select(CommitmentContext).where(CommitmentContext.user_id == user_id)
    )
    contexts = ctx_result.scalars().all()

    if not contexts:
        return AutoAssignResult(total=0, assigned=0, skipped=0)

    # Load commitments without context_id
    commit_result = await db.execute(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.context_id.is_(None),
        )
    )
    commitments = commit_result.scalars().all()

    assigned = 0
    skipped = 0

    for commitment in commitments:
        match = match_commitment_to_context(commitment, contexts)
        if match:
            commitment.context_id = match.id
            assigned += 1
        else:
            skipped += 1

    if assigned:
        await db.flush()

    logger.info(
        "bulk_auto_assign: user=%s total=%d assigned=%d skipped=%d",
        user_id, len(commitments), assigned, skipped,
    )

    return AutoAssignResult(
        total=len(commitments),
        assigned=assigned,
        skipped=skipped,
    )
