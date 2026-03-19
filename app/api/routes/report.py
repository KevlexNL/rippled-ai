"""Report API routes — pipeline cost and activity summaries.

GET /api/v1/report/weekly-summary — returns weekly detection cost report.
Called by Mero cron for Telegram delivery.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.models.orm import Commitment, DetectionAudit, SourceItem

router = APIRouter(prefix="/report", tags=["report"])

_WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")


class TierBreakdown(BaseModel):
    suppressed: int
    tier_1: int
    tier_2: int
    tier_3: int


class WeeklySummaryRead(BaseModel):
    week: str
    source_items_processed: int
    by_tier: TierBreakdown
    cost_llm_usd: float
    cost_embedding_usd: float
    commitments_surfaced: int
    false_positive_rate_pct: float | None


def _week_bounds(iso_week: str) -> tuple[datetime, datetime]:
    """Return (monday 00:00 UTC, next monday 00:00 UTC) for an ISO week string."""
    from datetime import timedelta

    monday = datetime.strptime(iso_week + "-1", "%G-W%V-%u").replace(tzinfo=timezone.utc)
    next_monday = monday + timedelta(days=7)
    return monday, next_monday


@router.get("/weekly-summary", response_model=WeeklySummaryRead)
async def get_weekly_summary(
    week: str | None = Query(None, description="ISO week, e.g. 2026-W12. Defaults to current week."),
    db: AsyncSession = Depends(get_db),
) -> WeeklySummaryRead:
    """Weekly pipeline cost and activity summary."""
    # Resolve week
    if week is None:
        now = datetime.now(timezone.utc)
        iso_year, iso_week_num, _ = now.isocalendar()
        week = f"{iso_year}-W{iso_week_num:02d}"
    elif not _WEEK_RE.match(week):
        raise HTTPException(status_code=422, detail=f"Invalid week format: {week}. Expected YYYY-Wnn.")

    start, end = _week_bounds(week)

    # Tier counts + cost aggregation from detection_audit
    tier_query = select(
        func.count(case((DetectionAudit.tier_used == "suppressed", 1))).label("suppressed"),
        func.count(case((DetectionAudit.tier_used == "tier_1", 1))).label("tier_1"),
        func.count(case((DetectionAudit.tier_used == "tier_2", 1))).label("tier_2"),
        func.count(case((DetectionAudit.tier_used == "tier_3", 1))).label("tier_3"),
        func.coalesce(
            func.sum(case((DetectionAudit.tier_used == "tier_3", DetectionAudit.cost_estimate))),
            0,
        ).label("cost_llm_usd"),
        func.coalesce(
            func.sum(case((DetectionAudit.tier_used == "tier_2", DetectionAudit.cost_estimate))),
            0,
        ).label("cost_embedding_usd"),
    ).where(
        DetectionAudit.created_at >= start,
        DetectionAudit.created_at < end,
    )
    tier_result = await db.execute(tier_query)
    tier_row = tier_result.one()

    # Commitments surfaced this week
    commitments_query = select(func.count()).select_from(Commitment).where(
        Commitment.created_at >= start,
        Commitment.created_at < end,
    )
    commitments_count = (await db.execute(commitments_query)).scalar() or 0

    # Source items processed this week
    source_items_query = select(func.count()).select_from(SourceItem).where(
        SourceItem.ingested_at >= start,
        SourceItem.ingested_at < end,
    )
    source_items_count = (await db.execute(source_items_query)).scalar() or 0

    return WeeklySummaryRead(
        week=week,
        source_items_processed=source_items_count,
        by_tier=TierBreakdown(
            suppressed=tier_row.suppressed or 0,
            tier_1=tier_row.tier_1 or 0,
            tier_2=tier_row.tier_2 or 0,
            tier_3=tier_row.tier_3 or 0,
        ),
        cost_llm_usd=round(float(tier_row.cost_llm_usd or 0), 2),
        cost_embedding_usd=round(float(tier_row.cost_embedding_usd or 0), 2),
        commitments_surfaced=commitments_count,
        false_positive_rate_pct=None,  # Not yet implemented — needs signal_feedback
    )
