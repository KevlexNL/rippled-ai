"""Events API router — Phase C3.

Endpoints:
    GET    /events              → list events (next 30 days)
    GET    /events/{id}         → get event with linked commitment count
    POST   /events              → create implicit event manually
    PATCH  /events/{id}         → reschedule or cancel an event
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import CommitmentEventLink, Event

router = APIRouter(prefix="/events", tags=["events"])


# ---------------------------------------------------------------------------
# Pydantic schemas (local — not in global schemas.py to keep scope minimal)
# ---------------------------------------------------------------------------


class EventRead(BaseModel):
    id: str
    external_id: str | None
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    event_type: str
    status: str
    is_recurring: bool
    location: str | None
    attendees: list | None
    linked_commitment_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    description: str | None = None
    location: str | None = None


class EventPatch(BaseModel):
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None  # 'confirmed' | 'cancelled' | 'tentative'
    description: str | None = None
    location: str | None = None


def _event_to_schema(row: Event, linked_count: int = 0) -> EventRead:
    return EventRead(
        id=row.id,
        external_id=row.external_id,
        title=row.title,
        description=row.description,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        event_type=row.event_type,
        status=row.status,
        is_recurring=row.is_recurring,
        location=row.location,
        attendees=row.attendees,
        linked_commitment_count=linked_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _get_event_or_404(event_id: str, db: AsyncSession) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[EventRead])
async def list_events(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
    """List events in the next 30 days."""
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=30)

    events = (
        await db.execute(
            select(Event)
            .where(
                Event.starts_at >= now,
                Event.starts_at <= window_end,
            )
            .order_by(Event.starts_at.asc())
        )
    ).scalars().all()

    # Count linked commitments per event
    event_ids = [e.id for e in events]
    counts: dict[str, int] = {}
    if event_ids:
        rows = (
            await db.execute(
                select(CommitmentEventLink.event_id, func.count().label("cnt"))
                .where(CommitmentEventLink.event_id.in_(event_ids))
                .group_by(CommitmentEventLink.event_id)
            )
        ).all()
        for row in rows:
            counts[row.event_id] = row.cnt

    return [_event_to_schema(e, counts.get(e.id, 0)) for e in events]


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    """Get a single event with linked commitment count."""
    event = await _get_event_or_404(event_id, db)

    count_result = await db.execute(
        select(func.count()).where(CommitmentEventLink.event_id == event_id)
    )
    linked_count = count_result.scalar() or 0

    return _event_to_schema(event, linked_count)


@router.post("", response_model=EventRead, status_code=201)
async def create_event(
    body: EventCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    """Create an implicit event manually."""
    now = datetime.now(timezone.utc)
    event = Event(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        location=body.location,
        event_type="implicit",
        status="confirmed",
        is_recurring=False,
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return _event_to_schema(event, 0)


@router.patch("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: str,
    body: EventPatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    """Reschedule or cancel an event."""
    event = await _get_event_or_404(event_id, db)
    now = datetime.now(timezone.utc)

    if body.title is not None:
        event.title = body.title
    if body.description is not None:
        event.description = body.description
    if body.location is not None:
        event.location = body.location

    if body.starts_at is not None and event.starts_at != body.starts_at:
        event.rescheduled_from = event.starts_at
        event.starts_at = body.starts_at

    if body.ends_at is not None:
        event.ends_at = body.ends_at

    if body.status is not None:
        valid_statuses = {"confirmed", "cancelled", "tentative"}
        if body.status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status: {body.status!r}. Must be one of {sorted(valid_statuses)}",
            )
        if event.status != "cancelled" and body.status == "cancelled":
            event.cancelled_at = now
        event.status = body.status

    event.updated_at = now
    await db.flush()
    await db.refresh(event)

    count_result = await db.execute(
        select(func.count()).where(CommitmentEventLink.event_id == event_id)
    )
    linked_count = count_result.scalar() or 0

    return _event_to_schema(event, linked_count)
