"""Signal Lab API — source item listing and pipeline trace.

Endpoints:
    GET  /lab/source-items?type=email&limit=20  — list recent source items
    POST /lab/trace                              — run trace on selected items
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.db.session import get_sync_session
from app.models.orm import CommitmentCandidate, SourceItem
from app.services.trace import trace_source_item

router = APIRouter(prefix="/lab", tags=["lab"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TraceRequest(BaseModel):
    source_item_ids: list[str]


class SourceItemSummary(BaseModel):
    id: str
    source_type: str
    sender_name: str | None = None
    sender_email: str | None = None
    occurred_at: str | None = None
    content_preview: str | None = None
    status: str = "unprocessed"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/source-items", response_model=list[SourceItemSummary])
async def list_source_items(
    type: str | None = Query(None, description="Filter by source type"),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SourceItemSummary]:
    """List recent source items for the Signal Lab picker."""
    q = select(SourceItem).where(
        SourceItem.user_id == user_id,
        SourceItem.is_quoted_content.is_(False),
    )
    if type:
        q = q.where(SourceItem.source_type == type)
    q = q.order_by(SourceItem.occurred_at.desc()).limit(limit)

    result = await db.execute(q)
    items = result.scalars().all()

    summaries = []
    for item in items:
        # Check candidate status
        cand_result = await db.execute(
            select(CommitmentCandidate.id)
            .where(CommitmentCandidate.originating_item_id == item.id)
            .limit(1)
        )
        has_candidate = cand_result.scalar_one_or_none() is not None

        status = "unprocessed"
        if item.seed_processed_at:
            status = "candidate_created" if has_candidate else "processed_no_match"

        summaries.append(SourceItemSummary(
            id=str(item.id),
            source_type=item.source_type,
            sender_name=item.sender_name,
            sender_email=item.sender_email,
            occurred_at=item.occurred_at.isoformat() if item.occurred_at else None,
            content_preview=(item.content or "")[:200],
            status=status,
        ))

    return summaries


@router.post("/trace")
async def run_trace(
    body: TraceRequest,
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Run pipeline trace on selected source items.

    Uses sync session since trace service reads from DB synchronously
    (same pattern as detection/clarification services).
    """
    if len(body.source_item_ids) > 10:
        raise HTTPException(status_code=422, detail="Max 10 items per trace request")

    traces = []
    with get_sync_session() as db:
        # Verify all items belong to user
        for sid in body.source_item_ids:
            item = db.get(SourceItem, sid)
            if item is None:
                raise HTTPException(status_code=404, detail=f"Source item {sid} not found")
            if str(item.user_id) != user_id:
                raise HTTPException(status_code=403, detail="Not authorized")

        for sid in body.source_item_ids:
            trace = trace_source_item(sid, db)
            traces.append(trace)

    return traces
