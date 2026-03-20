"""Admin review API routes — WO-RIPPLED-ADMIN-PANEL.

Signal review and outcome review endpoints for Tier 2 human feedback.
All endpoints require X-User-ID header with admin access.

Endpoint overview:
  GET    /admin/review/signals              — unreviewed detection_audit rows
  POST   /admin/review/signals/{id}         — submit signal feedback
  GET    /admin/review/outcomes             — surfaced commitments without feedback
  POST   /admin/review/outcomes/{id}        — submit outcome feedback
  GET    /admin/review/stats                — review queue stats
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.admin_review_auth import verify_admin_reviewer
from app.db.deps import get_db
from app.models.orm import (
    Commitment,
    DetectionAudit,
    OutcomeFeedback,
    SignalFeedback,
    SourceItem,
)

router = APIRouter(prefix="/admin/review", dependencies=[Depends(verify_admin_reviewer)])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignalFeedbackCreate(BaseModel):
    extraction_correct: bool
    rating: int
    missed_commitments: str | None = None
    false_positives: str | None = None
    notes: str | None = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating must be between 1 and 5")
        return v


class OutcomeFeedbackCreate(BaseModel):
    was_useful: bool
    usefulness_rating: int
    was_timely: bool | None = None
    notes: str | None = None

    @field_validator("usefulness_rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("usefulness_rating must be between 1 and 5")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decimal_to_json(val: Any) -> Any:
    """Convert Decimal to float for JSON serialization."""
    from decimal import Decimal
    if isinstance(val, Decimal):
        return float(val)
    return val


def _row_to_dict(row: Any, keys: list[str]) -> dict:
    """Convert a SQLAlchemy Row to a dict with given keys."""
    return {k: _decimal_to_json(getattr(row, k, None)) for k in keys}


# ---------------------------------------------------------------------------
# GET /admin/review/signals
# ---------------------------------------------------------------------------

@router.get("/signals")
async def list_unreviewed_signals(
    limit: int = Query(default=20, le=100),
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return unreviewed detection_audit rows (no signal_feedback) joined with source_items."""
    # Subquery: detection_audit IDs that already have feedback
    reviewed_ids = select(SignalFeedback.detection_audit_id).where(
        SignalFeedback.detection_audit_id.isnot(None)
    ).scalar_subquery()

    stmt = (
        select(
            DetectionAudit.id.label("detection_audit_id"),
            DetectionAudit.source_item_id,
            SourceItem.content,
            SourceItem.sender_name,
            SourceItem.sender_email,
            SourceItem.occurred_at,
            DetectionAudit.parsed_result,
            DetectionAudit.prompt_version,
            DetectionAudit.model,
        )
        .join(SourceItem, DetectionAudit.source_item_id == SourceItem.id)
        .where(DetectionAudit.id.notin_(reviewed_ids))
        .order_by(DetectionAudit.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        content = row.content or ""
        items.append({
            "detection_audit_id": row.detection_audit_id,
            "source_item_id": row.source_item_id,
            "content": content[:400],
            "full_content": content,
            "sender_name": row.sender_name,
            "sender_email": row.sender_email,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            "parsed_result": row.parsed_result,
            "prompt_version": row.prompt_version,
            "model": row.model,
        })
    return items


# ---------------------------------------------------------------------------
# POST /admin/review/signals/{detection_audit_id}
# ---------------------------------------------------------------------------

@router.post("/signals/{detection_audit_id}")
async def submit_signal_feedback(
    detection_audit_id: str,
    body: SignalFeedbackCreate,
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a signal_feedback row for the given detection_audit."""
    # Verify detection_audit exists and get source_item_id + user_id
    audit_result = await db.execute(
        select(DetectionAudit.source_item_id, DetectionAudit.user_id).where(
            DetectionAudit.id == detection_audit_id
        )
    )
    audit_row = audit_result.one_or_none()
    if not audit_row:
        raise HTTPException(status_code=404, detail="Detection audit not found")

    fb = SignalFeedback(
        user_id=audit_row.user_id,
        detection_audit_id=detection_audit_id,
        source_item_id=audit_row.source_item_id,
        reviewer_user_id=x_user_id,
        extraction_correct=body.extraction_correct,
        rating=body.rating,
        missed_commitments=body.missed_commitments,
        false_positives=body.false_positives,
        notes=body.notes,
    )
    db.add(fb)
    await db.flush()

    return {
        "id": fb.id,
        "detection_audit_id": detection_audit_id,
        "extraction_correct": fb.extraction_correct,
        "rating": fb.rating,
        "reviewed_at": fb.reviewed_at.isoformat() if fb.reviewed_at else None,
    }


# ---------------------------------------------------------------------------
# GET /admin/review/outcomes
# ---------------------------------------------------------------------------

@router.get("/outcomes")
async def list_unreviewed_outcomes(
    limit: int = Query(default=20, le=100),
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return surfaced commitments (main|shortlist) without outcome feedback."""
    reviewed_ids = select(OutcomeFeedback.commitment_id).scalar_subquery()

    stmt = (
        select(Commitment)
        .where(
            and_(
                Commitment.surfaced_as.in_(["main", "shortlist"]),
                Commitment.id.notin_(reviewed_ids),
            )
        )
        .order_by(Commitment.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = []
    for c in rows:
        items.append({
            "commitment_id": c.id,
            "title": c.title,
            "commitment_text": c.commitment_text,
            "lifecycle_state": c.lifecycle_state,
            "source_context": c.context_type,
        })
    return items


# ---------------------------------------------------------------------------
# POST /admin/review/outcomes/{commitment_id}
# ---------------------------------------------------------------------------

@router.post("/outcomes/{commitment_id}")
async def submit_outcome_feedback(
    commitment_id: str,
    body: OutcomeFeedbackCreate,
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an outcome_feedback row for the given commitment."""
    # Verify commitment exists
    commit_result = await db.execute(
        select(Commitment.id, Commitment.user_id).where(Commitment.id == commitment_id)
    )
    commit_row = commit_result.one_or_none()
    if not commit_row:
        raise HTTPException(status_code=404, detail="Commitment not found")

    fb = OutcomeFeedback(
        user_id=commit_row.user_id,
        commitment_id=commitment_id,
        reviewer_user_id=x_user_id,
        was_useful=body.was_useful,
        usefulness_rating=body.usefulness_rating,
        was_timely=body.was_timely,
        notes=body.notes,
    )
    db.add(fb)
    await db.flush()

    return {
        "id": fb.id,
        "commitment_id": commitment_id,
        "was_useful": fb.was_useful,
        "usefulness_rating": fb.usefulness_rating,
        "reviewed_at": fb.reviewed_at.isoformat() if fb.reviewed_at else None,
    }


# ---------------------------------------------------------------------------
# GET /admin/review/stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def review_stats(
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return review queue stats."""
    # Unreviewed signals count
    reviewed_signal_ids = select(SignalFeedback.detection_audit_id).where(
        SignalFeedback.detection_audit_id.isnot(None)
    ).scalar_subquery()
    unreviewed_signals_result = await db.execute(
        select(func.count()).select_from(DetectionAudit).where(
            DetectionAudit.id.notin_(reviewed_signal_ids)
        )
    )
    unreviewed_signals = unreviewed_signals_result.scalar() or 0

    # Unreviewed outcomes count
    reviewed_outcome_ids = select(OutcomeFeedback.commitment_id).scalar_subquery()
    unreviewed_outcomes_result = await db.execute(
        select(func.count()).select_from(Commitment).where(
            and_(
                Commitment.surfaced_as.in_(["main", "shortlist"]),
                Commitment.id.notin_(reviewed_outcome_ids),
            )
        )
    )
    unreviewed_outcomes = unreviewed_outcomes_result.scalar() or 0

    # Total feedback counts
    total_signal_result = await db.execute(select(func.count()).select_from(SignalFeedback))
    total_signal_feedback = total_signal_result.scalar() or 0

    total_outcome_result = await db.execute(select(func.count()).select_from(OutcomeFeedback))
    total_outcome_feedback = total_outcome_result.scalar() or 0

    # Last review date (most recent of either feedback type)
    last_signal = await db.execute(
        select(func.max(SignalFeedback.reviewed_at))
    )
    last_outcome = await db.execute(
        select(func.max(OutcomeFeedback.reviewed_at))
    )
    last_s = last_signal.scalar()
    last_o = last_outcome.scalar()

    last_review_date = None
    if last_s and last_o:
        last_review_date = max(last_s, last_o).isoformat()
    elif last_s:
        last_review_date = last_s.isoformat()
    elif last_o:
        last_review_date = last_o.isoformat()

    return {
        "unreviewed_signals": unreviewed_signals,
        "unreviewed_outcomes": unreviewed_outcomes,
        "last_review_date": last_review_date,
        "total_signal_feedback": total_signal_feedback,
        "total_outcome_feedback": total_outcome_feedback,
    }


# ---------------------------------------------------------------------------
# GET /admin/review/audit-sample — last N detection_audit rows for a prompt version
# ---------------------------------------------------------------------------

@router.get("/audit-sample")
async def audit_sample(
    prompt_version: str = Query(..., description="Prompt version to filter by"),
    limit: int = Query(default=3, le=20),
    x_user_id: str = Depends(verify_admin_reviewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return the last N detection_audit rows for a given prompt_version."""
    stmt = (
        select(
            DetectionAudit.id.label("detection_audit_id"),
            DetectionAudit.source_item_id,
            DetectionAudit.parsed_result,
            DetectionAudit.prompt_version,
            DetectionAudit.model,
            DetectionAudit.created_at,
            SourceItem.content,
            SourceItem.sender_name,
        )
        .join(SourceItem, DetectionAudit.source_item_id == SourceItem.id)
        .where(DetectionAudit.prompt_version == prompt_version)
        .order_by(DetectionAudit.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "detection_audit_id": row.detection_audit_id,
            "source_item_id": row.source_item_id,
            "content": (row.content or "")[:300],
            "sender_name": row.sender_name,
            "parsed_result": row.parsed_result,
            "prompt_version": row.prompt_version,
            "model": row.model,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
