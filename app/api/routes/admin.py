"""Admin API routes — Phase C4.

All endpoints require X-Admin-Key header (see app/api/deps/admin_auth.py).
Pipeline trigger endpoints run synchronous services via run_in_threadpool.

Endpoint overview:
  GET    /admin/health
  GET    /admin/commitments
  GET    /admin/commitments/{id}
  PATCH  /admin/commitments/{id}/state
  GET    /admin/candidates
  GET    /admin/candidates/{id}
  GET    /admin/surfacing-audit
  GET    /admin/events
  GET    /admin/events/{id}
  GET    /admin/digests
  GET    /admin/digests/{id}
  POST   /admin/pipeline/run-detection
  POST   /admin/pipeline/run-surfacing
  POST   /admin/pipeline/run-linker
  POST   /admin/pipeline/run-nudge
  POST   /admin/pipeline/run-digest-preview
  POST   /admin/pipeline/run-post-event-resolver
  POST   /admin/test/seed-commitment
  DELETE /admin/test/cleanup
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps.admin_auth import verify_admin_key
from app.db.deps import get_db
from app.db.session import get_sync_session
from app.models.orm import (
    CandidateCommitment,
    Commitment,
    CommitmentCandidate,
    CommitmentEventLink,
    DigestLog,
    Event,
    LifecycleTransition,
    Source,
    SourceItem,
    SurfacingAudit,
    User,
)
from app.services.detection import run_detection
from app.services.digest import DigestAggregator, DigestFormatter, DigestDelivery  # noqa: F401
from app.services.event_linker import DeadlineEventLinker
from app.services.nudge import NudgeService
from app.services.post_event_resolver import PostEventResolver
from app.services.surfacing_runner import run_surfacing_sweep


router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(verify_admin_key)],
    tags=["admin"],
)


# ===========================================================================
# Health
# ===========================================================================

@router.get("/health")
async def admin_health(db: AsyncSession = Depends(get_db)):
    """System health overview: task proxies, entity counts, error rate."""
    now = datetime.now(timezone.utc)

    # Entity counts
    async def _count(model):
        result = await db.execute(select(func.count()).select_from(model))
        return result.scalar_one_or_none() or 0

    commit_count = await _count(Commitment)
    candidate_count = await _count(CommitmentCandidate)
    event_count = await _count(Event)
    source_count = await _count(Source)

    digest_result = await db.execute(
        select(func.count()).select_from(DigestLog).where(DigestLog.status == "sent")
    )
    digests_sent = digest_result.scalar_one_or_none() or 0

    surfaced_main_result = await db.execute(
        select(func.count()).select_from(Commitment).where(Commitment.surfaced_as == "main")
    )
    surfaced_main = surfaced_main_result.scalar_one_or_none() or 0

    surfaced_shortlist_result = await db.execute(
        select(func.count()).select_from(Commitment).where(Commitment.surfaced_as == "shortlist")
    )
    surfaced_shortlist = surfaced_shortlist_result.scalar_one_or_none() or 0

    # Error candidates in last 24h
    window = now - timedelta(hours=24)
    error_result = await db.execute(
        select(func.count()).select_from(CommitmentCandidate).where(
            and_(
                CommitmentCandidate.model_classification == "error",
                CommitmentCandidate.created_at >= window,
            )
        )
    )
    error_count_24h = error_result.scalar_one_or_none() or 0

    # Task health: DB proxies for last activity
    async def _max_ts(stmt):
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    tasks = [
        {
            "name": "surfacing-sweep",
            "last_run_at": await _max_ts(select(func.max(SurfacingAudit.created_at))),
        },
        {
            "name": "daily-digest",
            "last_run_at": await _max_ts(select(func.max(DigestLog.sent_at))),
        },
        {
            "name": "google-calendar-sync",
            "last_run_at": await _max_ts(
                select(func.max(Event.updated_at)).where(Event.event_type == "explicit")
            ),
        },
        {
            "name": "pre-event-nudge",
            "last_run_at": await _max_ts(
                select(func.max(SurfacingAudit.created_at)).where(
                    SurfacingAudit.reason.like("nudge:%")
                )
            ),
        },
        {
            "name": "post-event-resolution",
            "last_run_at": await _max_ts(
                select(func.max(SurfacingAudit.created_at)).where(
                    SurfacingAudit.reason.like("post-event:%")
                )
            ),
        },
        {
            "name": "model-detection-sweep",
            "last_run_at": await _max_ts(
                select(func.max(CommitmentCandidate.model_called_at))
            ),
        },
        {
            "name": "clarification-sweep",
            "last_run_at": await _max_ts(
                select(func.max(CommitmentCandidate.updated_at)).where(
                    CommitmentCandidate.was_promoted.is_(True)
                )
            ),
        },
        {
            "name": "completion-sweep",
            "last_run_at": await _max_ts(
                select(func.max(LifecycleTransition.created_at)).where(
                    LifecycleTransition.trigger_reason == "auto_close"
                )
            ),
        },
    ]

    def _status(ts):
        if ts is None:
            return "unknown"
        if not hasattr(ts, 'tzinfo'):  # not a datetime (e.g. mock returning 0)
            return "unknown"
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (now - ts).total_seconds() / 3600
        if age_hours > 24:
            return "stale"
        return "ok"

    task_rows = [
        {
            "name": t["name"],
            "last_run_at": t["last_run_at"].isoformat() if t["last_run_at"] else None,
            "status": _status(t["last_run_at"]),
        }
        for t in tasks
    ]

    return {
        "tasks": task_rows,
        "counts": {
            "commitments": commit_count,
            "candidates": candidate_count,
            "events": event_count,
            "sources": source_count,
            "digests_sent": digests_sent,
            "surfaced_main": surfaced_main,
            "surfaced_shortlist": surfaced_shortlist,
        },
        "error_count_24h": error_count_24h,
    }


# ===========================================================================
# Commitments
# ===========================================================================

@router.get("/commitments")
async def list_commitments(
    lifecycle_state: str | None = None,
    surfaced_as: str | None = None,
    delivery_state: str | None = None,
    counterparty_type: str | None = None,
    source_type: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: str = "priority_score",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List commitments with optional filters."""
    if limit > 200:
        limit = 200

    stmt = select(Commitment)
    if lifecycle_state:
        stmt = stmt.where(Commitment.lifecycle_state == lifecycle_state)
    if surfaced_as:
        stmt = stmt.where(Commitment.surfaced_as == surfaced_as)
    if delivery_state:
        stmt = stmt.where(Commitment.delivery_state == delivery_state)
    if counterparty_type:
        stmt = stmt.where(Commitment.counterparty_type == counterparty_type)
    if created_after:
        stmt = stmt.where(Commitment.created_at >= created_after)
    if created_before:
        stmt = stmt.where(Commitment.created_at <= created_before)

    if sort == "created_at":
        stmt = stmt.order_by(desc(Commitment.created_at))
    elif sort == "resolved_deadline":
        stmt = stmt.order_by(asc(Commitment.resolved_deadline))
    else:
        stmt = stmt.order_by(desc(Commitment.priority_score))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [_commitment_row(c) for c in items],
        "total": total,
    }


@router.get("/commitments/{commitment_id}")
async def get_commitment(commitment_id: str, db: AsyncSession = Depends(get_db)):
    """Full commitment detail with linked events, transitions, audit, source snippet, candidate."""
    commitment = await db.get(Commitment, commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    # Linked events
    link_result = await db.execute(
        select(CommitmentEventLink, Event)
        .join(Event, Event.id == CommitmentEventLink.event_id)
        .where(CommitmentEventLink.commitment_id == commitment_id)
    )
    linked_events = [
        {
            "link_id": link.id,
            "event_id": event.id,
            "relationship": link.relationship,
            "confidence": float(link.confidence) if link.confidence is not None else None,
            "event_title": event.title,
            "event_starts_at": event.starts_at.isoformat() if event.starts_at else None,
            "event_status": event.status,
        }
        for link, event in link_result.all()
    ]

    # Lifecycle transitions
    trans_result = await db.execute(
        select(LifecycleTransition)
        .where(LifecycleTransition.commitment_id == commitment_id)
        .order_by(asc(LifecycleTransition.created_at))
    )
    transitions = [
        {
            "id": t.id,
            "from_state": t.from_state,
            "to_state": t.to_state,
            "trigger_reason": t.trigger_reason,
            "created_at": t.created_at.isoformat(),
        }
        for t in trans_result.scalars().all()
    ]

    # Surfacing audit
    audit_result = await db.execute(
        select(SurfacingAudit)
        .where(SurfacingAudit.commitment_id == commitment_id)
        .order_by(desc(SurfacingAudit.created_at))
        .limit(20)
    )
    audit_rows = [
        {
            "id": a.id,
            "old_surfaced_as": a.old_surfaced_as,
            "new_surfaced_as": a.new_surfaced_as,
            "priority_score": float(a.priority_score) if a.priority_score is not None else None,
            "reason": a.reason,
            "created_at": a.created_at.isoformat(),
        }
        for a in audit_result.scalars().all()
    ]

    # Source snippet via CandidateCommitment -> CommitmentCandidate -> SourceItem
    source_snippet = None
    candidate_info = None
    cc_result = await db.execute(
        select(CandidateCommitment)
        .where(CandidateCommitment.commitment_id == commitment_id)
        .limit(1)
    )
    cc = cc_result.scalars().first()
    if cc is not None:
        candidate = await db.get(CommitmentCandidate, cc.candidate_id)
        if candidate is not None:
            candidate_info = {
                "id": candidate.id,
                "trigger_class": candidate.trigger_class,
                "model_classification": candidate.model_classification,
                "model_confidence": float(candidate.model_confidence) if candidate.model_confidence is not None else None,
                "model_explanation": candidate.model_explanation,
                "detection_method": candidate.detection_method,
            }
            if candidate.originating_item_id:
                source_item = await db.get(SourceItem, candidate.originating_item_id)
                if source_item and source_item.content:
                    source_snippet = source_item.content[:500]

    return {
        "commitment": _commitment_to_dict(commitment),
        "linked_events": linked_events,
        "lifecycle_transitions": transitions,
        "surfacing_audit": audit_rows,
        "source_snippet": source_snippet,
        "candidate": candidate_info,
    }


class StateOverrideRequest(BaseModel):
    lifecycle_state: str | None = None
    delivery_state: str | None = None
    reason: str


@router.patch("/commitments/{commitment_id}/state")
async def override_commitment_state(
    commitment_id: str,
    body: StateOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """Override commitment state — bypasses lifecycle validation. Writes audit trail."""
    commitment = await db.get(Commitment, commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    old_surfaced_as = commitment.surfaced_as
    old_lifecycle = commitment.lifecycle_state

    if body.lifecycle_state is not None:
        commitment.lifecycle_state = body.lifecycle_state
    if body.delivery_state is not None:
        commitment.delivery_state = body.delivery_state

    # Write SurfacingAudit row for audit trail
    audit = SurfacingAudit(
        commitment_id=commitment_id,
        old_surfaced_as=old_surfaced_as,
        new_surfaced_as=commitment.surfaced_as,
        priority_score=commitment.priority_score,
        reason=f"admin-override: {body.reason}"[:255],
    )
    db.add(audit)

    # Write LifecycleTransition if lifecycle_state changed
    if body.lifecycle_state is not None:
        transition = LifecycleTransition(
            commitment_id=commitment_id,
            user_id=commitment.user_id,
            from_state=old_lifecycle,
            to_state=body.lifecycle_state,
            trigger_reason=f"admin-override: {body.reason}",
        )
        db.add(transition)

    await db.flush()
    return _commitment_row(commitment)


# ===========================================================================
# Candidates
# ===========================================================================

@router.get("/candidates")
async def list_candidates(
    trigger_class: str | None = None,
    model_classification: str | None = None,
    created_after: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List commitment candidates with optional filters."""
    if limit > 200:
        limit = 200

    stmt = select(CommitmentCandidate)
    if trigger_class:
        stmt = stmt.where(CommitmentCandidate.trigger_class == trigger_class)
    if model_classification:
        stmt = stmt.where(CommitmentCandidate.model_classification == model_classification)
    if created_after:
        stmt = stmt.where(CommitmentCandidate.created_at >= created_after)

    stmt = stmt.order_by(desc(CommitmentCandidate.created_at))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [_candidate_row(c) for c in items],
        "total": total,
    }


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Full candidate detail including context_window JSONB."""
    candidate = await db.get(CommitmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _candidate_to_dict(candidate)


# ===========================================================================
# Surfacing Audit
# ===========================================================================

@router.get("/surfacing-audit")
async def list_surfacing_audit(
    commitment_id: str | None = None,
    created_after: datetime | None = None,
    old_surfaced_as: str | None = None,
    new_surfaced_as: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List surfacing audit log with optional filters."""
    if limit > 200:
        limit = 200

    stmt = (
        select(SurfacingAudit, Commitment.title)
        .join(Commitment, Commitment.id == SurfacingAudit.commitment_id)
    )
    if commitment_id:
        stmt = stmt.where(SurfacingAudit.commitment_id == commitment_id)
    if created_after:
        stmt = stmt.where(SurfacingAudit.created_at >= created_after)
    if old_surfaced_as:
        stmt = stmt.where(SurfacingAudit.old_surfaced_as == old_surfaced_as)
    if new_surfaced_as:
        stmt = stmt.where(SurfacingAudit.new_surfaced_as == new_surfaced_as)

    stmt = stmt.order_by(desc(SurfacingAudit.created_at))

    # Count using a simpler approach
    count_base = select(func.count()).select_from(SurfacingAudit)
    if commitment_id:
        count_base = count_base.where(SurfacingAudit.commitment_id == commitment_id)
    if created_after:
        count_base = count_base.where(SurfacingAudit.created_at >= created_after)
    if old_surfaced_as:
        count_base = count_base.where(SurfacingAudit.old_surfaced_as == old_surfaced_as)
    if new_surfaced_as:
        count_base = count_base.where(SurfacingAudit.new_surfaced_as == new_surfaced_as)
    total_result = await db.execute(count_base)
    total = total_result.scalar_one_or_none() or 0

    result = await db.execute(stmt.limit(limit).offset(offset))
    rows = result.all()

    return {
        "items": [
            {
                "id": audit.id,
                "commitment_id": audit.commitment_id,
                "commitment_title_snippet": (title or "")[:80],
                "old_surfaced_as": audit.old_surfaced_as,
                "new_surfaced_as": audit.new_surfaced_as,
                "priority_score": float(audit.priority_score) if audit.priority_score is not None else None,
                "reason": audit.reason,
                "created_at": audit.created_at.isoformat(),
            }
            for audit, title in rows
        ],
        "total": total,
    }


# ===========================================================================
# Events
# ===========================================================================

@router.get("/events")
async def list_events(
    event_type: str | None = None,
    status: str | None = None,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List events with optional filters."""
    if limit > 200:
        limit = 200

    stmt = select(
        Event,
        select(func.count()).select_from(CommitmentEventLink).where(
            CommitmentEventLink.event_id == Event.id
        ).scalar_subquery().label("linked_count"),
    )
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    if status:
        stmt = stmt.where(Event.status == status)
    if starts_after:
        stmt = stmt.where(Event.starts_at >= starts_after)
    if starts_before:
        stmt = stmt.where(Event.starts_at <= starts_before)

    stmt = stmt.order_by(desc(Event.starts_at))

    count_stmt = select(func.count()).select_from(Event)
    if event_type:
        count_stmt = count_stmt.where(Event.event_type == event_type)
    if status:
        count_stmt = count_stmt.where(Event.status == status)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    result = await db.execute(stmt.limit(limit).offset(offset))
    rows = result.all()

    return {
        "items": [
            {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "status": event.status,
                "starts_at": event.starts_at.isoformat() if event.starts_at else None,
                "ends_at": event.ends_at.isoformat() if event.ends_at else None,
                "linked_commitment_count": linked_count or 0,
            }
            for event, linked_count in rows
        ],
        "total": total,
    }


@router.get("/events/{event_id}")
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    """Full event detail with linked commitments."""
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    link_result = await db.execute(
        select(CommitmentEventLink, Commitment)
        .join(Commitment, Commitment.id == CommitmentEventLink.commitment_id)
        .where(CommitmentEventLink.event_id == event_id)
    )
    linked_commitments = [
        {
            "commitment_id": commitment.id,
            "commitment_title": commitment.title,
            "relationship": link.relationship,
            "confidence": float(link.confidence) if link.confidence is not None else None,
            "lifecycle_state": commitment.lifecycle_state,
            "surfaced_as": commitment.surfaced_as,
        }
        for link, commitment in link_result.all()
    ]

    return {
        "event": _event_to_dict(event),
        "linked_commitments": linked_commitments,
    }


# ===========================================================================
# Digests
# ===========================================================================

@router.get("/digests")
async def list_digests(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List digest log entries."""
    if limit > 200:
        limit = 200

    count_result = await db.execute(select(func.count()).select_from(DigestLog))
    total = count_result.scalar_one_or_none() or 0

    result = await db.execute(
        select(DigestLog)
        .order_by(desc(DigestLog.sent_at))
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": d.id,
                "sent_at": d.sent_at.isoformat(),
                "commitment_count": d.commitment_count,
                "delivery_method": d.delivery_method,
                "status": d.status,
                "error_message": d.error_message,
            }
            for d in items
        ],
        "total": total,
    }


@router.get("/digests/{digest_id}")
async def get_digest(digest_id: str, db: AsyncSession = Depends(get_db)):
    """Full digest log entry including digest_content JSONB."""
    digest = await db.get(DigestLog, digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return {
        "id": digest.id,
        "sent_at": digest.sent_at.isoformat(),
        "commitment_count": digest.commitment_count,
        "delivery_method": digest.delivery_method,
        "status": digest.status,
        "error_message": digest.error_message,
        "digest_content": digest.digest_content,
    }


# ===========================================================================
# Pipeline Triggers
# ===========================================================================

@router.post("/pipeline/run-detection")
async def trigger_detection(user_id: str | None = None):
    """Manually run detection on all unprocessed source_items.

    Finds source_items with no associated commitment_candidates and runs
    the detection pipeline on each. Optionally filter by user_id.

    Args:
        user_id: Optional user UUID to scope detection to a single user.

    Returns:
        Dict with processing counts and duration.
    """
    import logging

    log = logging.getLogger(__name__)
    start = time.monotonic()

    try:
        def _run():
            from sqlalchemy import select, and_, exists
            from app.models.orm import CommitmentCandidate

            has_candidate = (
                select(CommitmentCandidate.id)
                .where(CommitmentCandidate.originating_item_id == SourceItem.id)
                .exists()
            )

            filters = [
                ~has_candidate,
                SourceItem.is_quoted_content.is_(False),
            ]
            if user_id:
                filters.append(SourceItem.user_id == user_id)

            with get_sync_session() as session:
                unprocessed_ids = session.execute(
                    select(SourceItem.id, SourceItem.user_id)
                    .where(and_(*filters))
                    .order_by(SourceItem.ingested_at.asc())
                ).all()

            processed = 0
            total_candidates = 0
            errors = 0

            for item_id, item_user_id in unprocessed_ids:
                try:
                    with get_sync_session() as session:
                        result = run_detection(str(item_id), session)
                    count = len(result)
                    total_candidates += count
                    processed += 1
                    log.info(
                        "Pipeline: admin detection — %d candidate(s) from source_item %s",
                        count, item_id,
                    )
                except Exception:
                    log.exception(
                        "Pipeline: admin detection FAILED for source_item %s",
                        item_id,
                    )
                    errors += 1

            return {
                "unprocessed_found": len(unprocessed_ids),
                "processed": processed,
                "candidates_created": total_candidates,
                "errors": errors,
            }

        result = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)
    result["duration_ms"] = duration_ms
    return result


@router.post("/pipeline/run-surfacing")
async def trigger_surfacing():
    """Manually trigger a surfacing sweep. Uses run_in_threadpool."""
    start = time.monotonic()
    try:
        def _run():
            with get_sync_session() as db:
                return run_surfacing_sweep(db)

        result = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "commitments_scored": result.get("evaluated", 0),
        "surfaced_to_main": result.get("surfaced_main", 0),
        "surfaced_to_shortlist": result.get("surfaced_shortlist", 0),
        "duration_ms": duration_ms,
    }


@router.post("/pipeline/run-linker")
async def trigger_linker():
    """Manually trigger the deadline event linker."""
    start = time.monotonic()
    try:
        def _run():
            with get_sync_session() as db:
                commitments = db.execute(
                    select(Commitment).where(
                        Commitment.lifecycle_state.in_(("proposed", "active", "needs_clarification"))
                    )
                ).scalars().all()
                all_events = db.execute(
                    select(Event).where(Event.status != "cancelled")
                ).scalars().all()
                existing_link_ids_rows = db.execute(
                    select(CommitmentEventLink.commitment_id).where(
                        CommitmentEventLink.relationship == "delivery_at"
                    )
                ).scalars().all()
                existing_link_ids = {item for item in existing_link_ids_rows if isinstance(item, str)}

                linker = DeadlineEventLinker()
                return linker.run(
                    db,
                    user_id=None,
                    commitments=list(commitments),
                    events=all_events,
                    existing_link_ids=existing_link_ids,
                ) or {}

        result = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)
    # DeadlineEventLinker.run() returns {"links_created": ..., "implicit_events_created": ...}
    return {
        "linked": result.get("links_created", 0),
        "created_implicit": result.get("implicit_events_created", 0),
        "duration_ms": duration_ms,
    }


@router.post("/pipeline/run-nudge")
async def trigger_nudge():
    """Manually trigger the pre-event nudge service."""
    start = time.monotonic()
    try:
        def _run():
            with get_sync_session() as db:
                now = datetime.now(timezone.utc)
                pairs = NudgeService.load_pairs(db, now)
                service = NudgeService()
                return service.run(db, commitment_event_pairs=pairs)

        result = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "nudged": result.get("nudged", 0),
        "duration_ms": duration_ms,
    }


@router.post("/pipeline/run-digest-preview")
async def trigger_digest_preview(db: AsyncSession = Depends(get_db)):
    """Build digest without delivering it. Returns full content for preview."""
    start = time.monotonic()

    from app.core.config import get_settings

    settings = get_settings()

    user_email = settings.digest_to_email
    user = None
    if user_email:
        result = await db.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()

    if user is None:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "main": [],
            "shortlist": [],
            "clarifications": [],
            "commitment_count": 0,
            "subject": "No user configured",
            "duration_ms": duration_ms,
        }

    user_id = user.id

    def _run():
        with get_sync_session() as sync_db:
            agg = DigestAggregator()
            return agg.aggregate_sync(sync_db, user_id=user_id)

    digest = await run_in_threadpool(_run)

    def _snap(c):
        return {
            "id": c.id,
            "title": c.title,
            "deadline": str(c.resolved_deadline) if c.resolved_deadline else None,
        }

    fmt = DigestFormatter()
    formatted = fmt.format(digest)

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "main": [_snap(c) for c in digest.main],
        "shortlist": [_snap(c) for c in digest.shortlist],
        "clarifications": [{"id": c.id, "title": c.title} for c in digest.clarifications],
        "commitment_count": len(digest.main) + len(digest.shortlist) + len(digest.clarifications),
        "subject": formatted.subject,
        "duration_ms": duration_ms,
    }


@router.post("/pipeline/run-post-event-resolver")
async def trigger_post_event_resolver():
    """Manually trigger post-event resolution."""
    start = time.monotonic()
    try:
        def _run():
            with get_sync_session() as db:
                now = datetime.now(timezone.utc)
                pairs, source_item_map = PostEventResolver.load_pairs(db, now)
                resolver = PostEventResolver()
                return resolver.run(
                    db,
                    commitment_event_pairs=pairs,
                    source_item_map=source_item_map,
                    now=now,
                )

        result = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "processed": result.get("processed", 0),
        "escalated": result.get("escalated", 0),
        "duration_ms": duration_ms,
    }


# ===========================================================================
# Test Data
# ===========================================================================

class SeedCommitmentRequest(BaseModel):
    description: str
    lifecycle_state: str | None = "active"
    resolved_deadline: datetime | None = None
    counterparty_type: str | None = None
    source_type: str | None = "email"


@router.post("/test/seed-commitment", status_code=201)
async def seed_commitment(body: SeedCommitmentRequest, db: AsyncSession = Depends(get_db)):
    """Create a full test data chain for manual testing.

    Creates: User (if needed) -> Source -> SourceItem -> CommitmentCandidate -> Commitment -> CandidateCommitment
    Source.display_name = 'admin-test-seed' for easy cleanup identification.
    """
    from app.core.config import get_settings

    settings = get_settings()

    # Get or create user
    user_email = settings.digest_to_email or "admin-test@rippled.ai"
    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email=user_email,
            display_name="Admin Test User",
        )
        db.add(user)
        await db.flush()

    # Create Source
    source = Source(
        id=str(uuid.uuid4()),
        user_id=user.id,
        source_type=body.source_type or "email",
        display_name="admin-test-seed",
        is_active=True,
    )
    db.add(source)
    await db.flush()

    # Create SourceItem
    source_item = SourceItem(
        id=str(uuid.uuid4()),
        source_id=source.id,
        user_id=user.id,
        source_type=body.source_type or "email",
        external_id=f"admin-test-{uuid.uuid4()}",
        content=body.description,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(source_item)
    await db.flush()

    # Create CommitmentCandidate
    candidate = CommitmentCandidate(
        id=str(uuid.uuid4()),
        user_id=user.id,
        originating_item_id=source_item.id,
        source_type=body.source_type or "email",
        raw_text=body.description,
        trigger_class="admin_seed",
        was_promoted=True,
        was_discarded=False,
    )
    db.add(candidate)
    await db.flush()

    # Create Commitment
    commitment = Commitment(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=body.description[:200],
        lifecycle_state=body.lifecycle_state or "active",
        resolved_deadline=body.resolved_deadline,
        counterparty_type=body.counterparty_type,
    )
    db.add(commitment)
    await db.flush()

    # Link candidate -> commitment
    link = CandidateCommitment(
        id=str(uuid.uuid4()),
        candidate_id=candidate.id,
        commitment_id=commitment.id,
    )
    db.add(link)
    await db.flush()

    return {
        "commitment_id": commitment.id,
        "user_id": user.id,
        "source_id": source.id,
        "source_item_id": source_item.id,
        "candidate_id": candidate.id,
    }


class CleanupRequest(BaseModel):
    confirm: str

    @field_validator("confirm")
    @classmethod
    def must_be_delete_test_data(cls, v: str) -> str:
        if v != "delete-test-data":
            raise ValueError("confirm must be 'delete-test-data'")
        return v


@router.delete("/test/cleanup")
async def cleanup_test_data(body: CleanupRequest, db: AsyncSession = Depends(get_db)):
    """Delete all rows created by admin-test-seed sources. Cascades via FK."""
    # Find all admin-test-seed sources
    sources_result = await db.execute(
        select(Source).where(Source.display_name == "admin-test-seed")
    )
    sources = sources_result.scalars().all()

    if not sources:
        return {
            "deleted_commitments": 0,
            "deleted_candidates": 0,
            "deleted_source_items": 0,
            "deleted_sources": 0,
        }

    source_ids = [s.id for s in sources]

    # Count source_items
    si_result = await db.execute(
        select(func.count()).select_from(SourceItem).where(SourceItem.source_id.in_(source_ids))
    )
    deleted_source_items = si_result.scalar_one_or_none() or 0

    # Count candidates via source_items
    si_ids_result = await db.execute(
        select(SourceItem.id).where(SourceItem.source_id.in_(source_ids))
    )
    si_ids = si_ids_result.scalars().all()

    deleted_candidates = 0
    if si_ids:
        cand_result = await db.execute(
            select(func.count()).select_from(CommitmentCandidate).where(
                CommitmentCandidate.originating_item_id.in_(si_ids)
            )
        )
        deleted_candidates = cand_result.scalar_one_or_none() or 0

    # Count commitments via candidates
    deleted_commitments = 0
    if si_ids:
        cand_ids_result = await db.execute(
            select(CommitmentCandidate.id).where(
                CommitmentCandidate.originating_item_id.in_(si_ids)
            )
        )
        cand_ids = cand_ids_result.scalars().all()
        if cand_ids:
            comm_result = await db.execute(
                select(func.count()).select_from(CandidateCommitment).where(
                    CandidateCommitment.candidate_id.in_(cand_ids)
                )
            )
            deleted_commitments = comm_result.scalar_one_or_none() or 0

    # Delete sources (CASCADE handles source_items, candidates, commitments via FKs)
    for source in sources:
        await db.delete(source)

    await db.flush()

    return {
        "deleted_commitments": deleted_commitments,
        "deleted_candidates": deleted_candidates,
        "deleted_source_items": deleted_source_items,
        "deleted_sources": len(sources),
    }


# ===========================================================================
# Private helpers
# ===========================================================================

def _commitment_row(c: Commitment) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "lifecycle_state": c.lifecycle_state,
        "surfaced_as": c.surfaced_as,
        "priority_score": float(c.priority_score) if c.priority_score is not None else None,
        "counterparty_type": c.counterparty_type,
        "delivery_state": c.delivery_state,
        "resolved_deadline": c.resolved_deadline.isoformat() if c.resolved_deadline else None,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _commitment_to_dict(c: Commitment) -> dict:
    """Convert all ORM fields to dict."""
    fields = [
        "id", "user_id", "version", "title", "description", "commitment_text",
        "commitment_type", "priority_class", "context_type", "resolved_owner",
        "suggested_owner", "ownership_ambiguity", "vague_time_phrase",
        "timing_ambiguity", "deliverable", "target_entity", "suggested_next_step",
        "deliverable_ambiguity", "lifecycle_state", "delivery_state",
        "counterparty_type", "counterparty_email", "surfaced_as", "surfacing_reason",
        "is_surfaced", "post_event_reviewed",
    ]
    decimal_fields = [
        "confidence_commitment", "confidence_owner", "confidence_deadline",
        "confidence_delivery", "confidence_closure", "confidence_actionability",
        "priority_score", "confidence_for_surfacing",
    ]
    dt_fields = [
        "resolved_deadline", "suggested_due_date", "state_changed_at",
        "delivered_at", "observe_until", "surfaced_at", "created_at", "updated_at",
    ]
    int_fields = ["timing_strength", "business_consequence", "cognitive_burden", "auto_close_after_hours"]

    result: dict[str, Any] = {}
    for f in fields:
        result[f] = getattr(c, f, None)
    for f in decimal_fields:
        v = getattr(c, f, None)
        result[f] = float(v) if v is not None else None
    for f in dt_fields:
        v = getattr(c, f, None)
        result[f] = v.isoformat() if v is not None else None
    for f in int_fields:
        result[f] = getattr(c, f, None)
    return result


def _candidate_row(c: CommitmentCandidate) -> dict:
    return {
        "id": c.id,
        "raw_text_snippet": (c.raw_text or "")[:200] if c.raw_text else None,
        "trigger_class": c.trigger_class,
        "model_classification": c.model_classification,
        "model_confidence": float(c.model_confidence) if c.model_confidence is not None else None,
        "was_promoted": c.was_promoted,
        "was_discarded": c.was_discarded,
        "source_type": c.source_type,
        "created_at": c.created_at.isoformat(),
    }


def _candidate_to_dict(c: CommitmentCandidate) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "raw_text": c.raw_text,
        "trigger_class": c.trigger_class,
        "model_classification": c.model_classification,
        "model_confidence": float(c.model_confidence) if c.model_confidence is not None else None,
        "model_explanation": c.model_explanation,
        "detection_method": c.detection_method,
        "was_promoted": c.was_promoted,
        "was_discarded": c.was_discarded,
        "source_type": c.source_type,
        "context_window": c.context_window,
        "confidence_score": float(c.confidence_score) if c.confidence_score is not None else None,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _event_to_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "event_type": e.event_type,
        "status": e.status,
        "starts_at": e.starts_at.isoformat() if e.starts_at else None,
        "ends_at": e.ends_at.isoformat() if e.ends_at else None,
        "is_recurring": e.is_recurring,
        "location": e.location,
        "attendees": e.attendees,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }
