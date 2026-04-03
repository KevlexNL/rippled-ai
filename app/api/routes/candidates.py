import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import CommitmentCandidate
from app.models.schemas import CommitmentCandidateRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _to_schema(row: CommitmentCandidate) -> CommitmentCandidateRead:
    return CommitmentCandidateRead.model_validate(row)


@router.get("", response_model=list[CommitmentCandidateRead])
async def list_candidates(
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentCandidateRead]:
    result = await db.execute(
        select(CommitmentCandidate)
        .where(CommitmentCandidate.user_id == user_id)
        .order_by(CommitmentCandidate.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/{candidate_id}", response_model=CommitmentCandidateRead)
async def get_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentCandidateRead:
    result = await db.execute(
        select(CommitmentCandidate).where(
            CommitmentCandidate.id == candidate_id,
            CommitmentCandidate.user_id == user_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _to_schema(candidate)


@router.post("/{candidate_id}/reanalyze", response_model=CommitmentCandidateRead)
async def reanalyze_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommitmentCandidateRead:
    """Flag a candidate for re-analysis.

    Sets flag_reanalysis=true so the next reanalysis sweep picks it up.
    Candidates that are already promoted or discarded cannot be re-analyzed.
    """
    result = await db.execute(
        select(CommitmentCandidate).where(
            CommitmentCandidate.id == candidate_id,
            CommitmentCandidate.user_id == user_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.was_promoted or candidate.was_discarded:
        raise HTTPException(
            status_code=409,
            detail="Cannot re-analyze a candidate that is already promoted or discarded",
        )
    candidate.flag_reanalysis = True
    await db.commit()
    await db.refresh(candidate)
    logger.info("Candidate %s flagged for re-analysis by user %s", candidate_id, user_id)
    return _to_schema(candidate)
