"""Stats API route — Phase C6.

GET /api/v1/stats — returns activity counts for the current user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, Source, SourceItem

router = APIRouter(prefix="/stats", tags=["stats"])


class StatsRead(BaseModel):
    meetings_analyzed: int
    meetings_logged: int  # alias for frontend compatibility
    messages_processed: int
    emails_captured: int
    commitments_detected: int
    sources_connected: int
    people_identified: int


@router.get("", response_model=StatsRead)
async def get_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> StatsRead:
    """Get activity stats for the current user."""
    # Count source_items by source_type in a single query
    items_result = await db.execute(
        select(
            func.count(case((SourceItem.source_type == "meeting", 1))).label("meetings"),
            func.count(case((SourceItem.source_type == "slack", 1))).label("slack"),
            func.count(case((SourceItem.source_type == "email", 1))).label("email"),
        ).where(SourceItem.user_id == user_id)
    )
    items_row = items_result.one()

    # Count commitments (any lifecycle_state)
    commitments_result = await db.execute(
        select(func.count()).where(Commitment.user_id == user_id)
    )
    commitments_count = commitments_result.scalar() or 0

    # Count active sources
    sources_result = await db.execute(
        select(func.count()).where(
            Source.user_id == user_id,
            Source.is_active == True,  # noqa: E712
        )
    )
    sources_count = sources_result.scalar() or 0

    # Count distinct people (unique sender_name or sender_email across source_items)
    people_result = await db.execute(
        select(func.count(func.distinct(SourceItem.sender_email))).where(
            SourceItem.user_id == user_id,
            SourceItem.sender_email.isnot(None),
        )
    )
    people_count = people_result.scalar() or 0

    meetings_count = items_row.meetings or 0
    return StatsRead(
        meetings_analyzed=meetings_count,
        meetings_logged=meetings_count,
        messages_processed=items_row.slack or 0,
        emails_captured=items_row.email or 0,
        commitments_detected=commitments_count,
        sources_connected=sources_count,
        people_identified=people_count,
    )
