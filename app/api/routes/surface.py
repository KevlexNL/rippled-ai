"""Surfacing API routes — Phase 06.

Queries use surfaced_as + priority_score DESC ordering (Phase 06).
Legacy is_surfaced / priority_class filters removed.

Endpoints:
    GET /surface/main            → commitments with surfaced_as = 'main'
    GET /surface/shortlist       → commitments with surfaced_as = 'shortlist'
    GET /surface/clarifications  → commitments with surfaced_as = 'clarifications'
    GET /surface/internal        → unsurfaced active commitments (debug/admin)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment
from app.models.schemas import CommitmentRead

router = APIRouter(prefix="/surface", tags=["surfacing"])

_SURFACED_STATES = ("active", "needs_clarification", "proposed")


def _to_schema(row: Commitment) -> CommitmentRead:
    return CommitmentRead.model_validate(row)


@router.get("/main", response_model=list[CommitmentRead])
async def surface_main(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """Return commitments routed to the Main surface, ordered by priority."""
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.surfaced_as == "main",
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
        )
        .order_by(Commitment.priority_score.desc().nullslast(), Commitment.created_at.desc())
        .limit(10)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/shortlist", response_model=list[CommitmentRead])
async def surface_shortlist(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """Return commitments routed to the Shortlist surface, ordered by priority."""
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.surfaced_as == "shortlist",
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
        )
        .order_by(Commitment.priority_score.desc().nullslast(), Commitment.created_at.desc())
        .limit(10)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/clarifications", response_model=list[CommitmentRead])
async def surface_clarifications(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """Return commitments routed to the Clarifications surface, ordered by priority."""
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.surfaced_as == "clarifications",
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
        )
        .order_by(Commitment.priority_score.desc().nullslast(), Commitment.state_changed_at.asc())
        .limit(10)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/internal", response_model=list[CommitmentRead])
async def surface_internal(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """Return unsurfaced active commitments (debug/admin view).

    These are commitments in active states that have not been assigned a
    surface destination. Useful for debugging the surfacing pipeline.
    """
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.surfaced_as.is_(None),
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
        )
        .order_by(Commitment.priority_score.desc().nullslast(), Commitment.created_at.desc())
        .limit(20)
    )
    return [_to_schema(row) for row in result.scalars()]
