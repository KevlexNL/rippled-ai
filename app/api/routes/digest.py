"""Daily Digest API routes — Phase C2.

Endpoints:
    POST /digest/trigger   → manually trigger a digest (testing / admin)
    GET  /digest/log       → list recent digest log entries (last 10)
    GET  /digest/preview   → return digest content as JSON without sending
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import DigestLog
from app.services.digest import DigestAggregator, DigestFormatter, DigestDelivery

router = APIRouter(prefix="/digest", tags=["digest"])
settings = get_settings()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DigestTriggerResponse(BaseModel):
    status: str
    commitment_count: int
    message: str


class DigestLogRead(BaseModel):
    id: str
    sent_at: datetime
    commitment_count: int
    delivery_method: str
    status: str
    error_message: str | None

    class Config:
        from_attributes = True


class DigestPreviewResponse(BaseModel):
    main: list[dict[str, Any]]
    shortlist: list[dict[str, Any]]
    clarifications: list[dict[str, Any]]
    generated_at: datetime
    subject: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _commitment_to_dict(c: Any) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "deadline": c.resolved_deadline.isoformat() if c.resolved_deadline else None,
        "priority_score": float(c.priority_score) if c.priority_score is not None else None,
        "surfaced_as": c.surfaced_as,
        "lifecycle_state": c.lifecycle_state,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/trigger", response_model=DigestTriggerResponse)
async def trigger_digest(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DigestTriggerResponse:
    """Manually trigger a digest for the current user.

    Aggregates, formats, and delivers the digest. Writes a DigestLog row.
    Returns the delivery status and commitment count.
    """
    agg = DigestAggregator()
    digest = await agg.aggregate_async(db, user_id=user_id)

    if digest.is_empty:
        return DigestTriggerResponse(
            status="skipped",
            commitment_count=0,
            message="No surfaced commitments — digest skipped",
        )

    fmt = DigestFormatter()
    formatted = fmt.format(digest)

    delivery = DigestDelivery(settings=settings)
    result = delivery.send(formatted.subject, formatted.plain_text, formatted.html)

    commitment_count = len(digest.main) + len(digest.shortlist) + len(digest.clarifications)
    log_status = "sent" if result.success else "failed"

    digest_content = {
        "main": [_commitment_to_dict(c) for c in digest.main],
        "shortlist": [_commitment_to_dict(c) for c in digest.shortlist],
        "clarifications": [_commitment_to_dict(c) for c in digest.clarifications],
        "subject": formatted.subject,
    }

    from datetime import timezone as _tz
    log_row = DigestLog(
        sent_at=datetime.now(_tz.utc),
        commitment_count=commitment_count,
        delivery_method=result.method,
        status=log_status,
        error_message=result.error,
        digest_content=digest_content,
    )
    db.add(log_row)
    await db.flush()

    if result.success:
        return DigestTriggerResponse(
            status="sent",
            commitment_count=commitment_count,
            message=f"Digest sent via {result.method}",
        )
    return DigestTriggerResponse(
        status="failed",
        commitment_count=commitment_count,
        message=f"Delivery failed: {result.error}",
    )


@router.get("/log", response_model=list[DigestLogRead])
async def get_digest_log(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[DigestLogRead]:
    """Return the last 10 digest log entries (system-level, not per-user)."""
    result = await db.execute(
        select(DigestLog)
        .order_by(DigestLog.sent_at.desc())
        .limit(10)
    )
    return [DigestLogRead.model_validate(row) for row in result.scalars()]


@router.get("/preview", response_model=DigestPreviewResponse)
async def preview_digest(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DigestPreviewResponse:
    """Return digest content as JSON without sending or writing any log entry."""
    agg = DigestAggregator()
    digest = await agg.aggregate_async(db, user_id=user_id)

    subject: str | None = None
    if not digest.is_empty:
        fmt = DigestFormatter()
        formatted = fmt.format(digest)
        subject = formatted.subject

    return DigestPreviewResponse(
        main=[_commitment_to_dict(c) for c in digest.main],
        shortlist=[_commitment_to_dict(c) for c in digest.shortlist],
        clarifications=[_commitment_to_dict(c) for c in digest.clarifications],
        generated_at=digest.generated_at,
        subject=subject,
    )
