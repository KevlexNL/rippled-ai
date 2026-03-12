from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, CommitmentAmbiguity
from app.models.schemas import CommitmentRead

router = APIRouter(prefix="/surface", tags=["surfacing"])

_SURFACED_STATES = ("active", "needs_clarification")


def _to_schema(row: Commitment) -> CommitmentRead:
    return CommitmentRead.model_validate(row)


@router.get("/main", response_model=list[CommitmentRead])
async def surface_main(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.priority_class == "big_promise",
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
            Commitment.is_surfaced.is_(True),
            (Commitment.observe_until.is_(None)) | (Commitment.observe_until <= now),
        )
        .order_by(Commitment.resolved_deadline.asc().nullslast(), Commitment.created_at.desc())
        .limit(5)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/shortlist", response_model=list[CommitmentRead])
async def surface_shortlist(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.priority_class == "small_commitment",
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
            Commitment.is_surfaced.is_(True),
            (Commitment.observe_until.is_(None)) | (Commitment.observe_until <= now),
        )
        .order_by(
            Commitment.resolved_deadline.asc().nullslast(),
            Commitment.confidence_actionability.desc(),
        )
        .limit(5)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/clarifications", response_model=list[CommitmentRead])
async def surface_clarifications(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    unresolved_ambiguity = exists().where(
        CommitmentAmbiguity.commitment_id == Commitment.id,
        CommitmentAmbiguity.is_resolved.is_(False),
    )
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.lifecycle_state == "needs_clarification",
            Commitment.is_surfaced.is_(True),
            unresolved_ambiguity,
        )
        .order_by(Commitment.state_changed_at.asc())
        .limit(5)
    )
    return [_to_schema(row) for row in result.scalars()]
