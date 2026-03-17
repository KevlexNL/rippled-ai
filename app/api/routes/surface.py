"""Surfacing API routes — Phase 06.

Queries use surfaced_as + priority_score DESC ordering (Phase 06).
Legacy is_surfaced / priority_class filters removed.

Endpoints:
    GET /surface/main            → commitments with surfaced_as = 'main'
    GET /surface/shortlist       → commitments with surfaced_as = 'shortlist'
    GET /surface/clarifications  → commitments with surfaced_as = 'clarifications'
    GET /surface/best-next-moves → grouped best next actions (≤5 items)
    GET /surface/internal        → unsurfaced active commitments (debug/admin)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, CommitmentEventLink, CommitmentSignal, Event, SourceItem
from app.models.schemas import CommitmentRead, LinkedEventRead

router = APIRouter(prefix="/surface", tags=["surfacing"])

_SURFACED_STATES = ("active", "needs_clarification", "proposed")

# Quick-win commitment types (low effort, quick to resolve)
_QUICK_WIN_TYPES = ("confirm", "send", "update", "follow_up")


class BestNextMovesGroup(BaseModel):
    label: str
    items: list[CommitmentRead]


class BestNextMovesResponse(BaseModel):
    groups: list[BestNextMovesGroup]


async def _fetch_event_map(commitment_ids: list[str], db: AsyncSession) -> dict[str, list[tuple]]:
    """Batch-fetch delivery_at linked events for a list of commitment IDs.
    Returns dict: commitment_id → list of (link, event) tuples, ordered by starts_at asc.
    Only the nearest delivery_at event per commitment is needed for the list view.
    """
    if not commitment_ids:
        return {}
    result = await db.execute(
        select(CommitmentEventLink, Event)
        .join(Event, Event.id == CommitmentEventLink.event_id)
        .where(
            CommitmentEventLink.commitment_id.in_(commitment_ids),
            CommitmentEventLink.relationship == "delivery_at",
            Event.status != "cancelled",
        )
        .order_by(Event.starts_at.asc())
    )
    event_map: dict[str, list[tuple]] = {}
    for link, event in result:
        if link.commitment_id not in event_map:
            event_map[link.commitment_id] = []
        event_map[link.commitment_id].append((link, event))
    return event_map


async def _fetch_origin_source_map(
    commitment_ids: list[str], db: AsyncSession
) -> dict[str, SourceItem]:
    """Batch-fetch the origin source item for a list of commitment IDs.
    Returns dict: commitment_id → SourceItem (first origin signal's source).
    """
    if not commitment_ids:
        return {}
    result = await db.execute(
        select(CommitmentSignal.commitment_id, SourceItem)
        .join(SourceItem, SourceItem.id == CommitmentSignal.source_item_id)
        .where(
            CommitmentSignal.commitment_id.in_(commitment_ids),
            CommitmentSignal.signal_role == "origin",
        )
        .order_by(CommitmentSignal.created_at.asc())
    )
    source_map: dict[str, SourceItem] = {}
    for commitment_id, source_item in result:
        if commitment_id not in source_map:
            source_map[commitment_id] = source_item
    return source_map


def _build_commitment_read(
    row: Commitment,
    event_map: dict[str, list[tuple]] | None = None,
    source_map: dict[str, SourceItem] | None = None,
) -> CommitmentRead:
    """Build a CommitmentRead schema, injecting linked_events and origin source info."""
    schema = CommitmentRead.model_validate(row)
    if event_map and row.id in event_map:
        schema.linked_events = [
            LinkedEventRead(
                event_id=event.id,
                title=event.title,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                relationship=link.relationship,
            )
            for link, event in event_map[row.id]
        ]
    else:
        schema.linked_events = []
    if source_map and row.id in source_map:
        src = source_map[row.id]
        schema.source_sender_name = src.sender_name
        schema.source_sender_email = src.sender_email
        schema.source_occurred_at = src.occurred_at
    return schema


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
    rows = list(result.scalars())
    ids = [r.id for r in rows]
    event_map = await _fetch_event_map(ids, db)
    source_map = await _fetch_origin_source_map(ids, db)
    return [_build_commitment_read(row, event_map, source_map) for row in rows]


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
    rows = list(result.scalars())
    ids = [r.id for r in rows]
    event_map = await _fetch_event_map(ids, db)
    source_map = await _fetch_origin_source_map(ids, db)
    return [_build_commitment_read(row, event_map, source_map) for row in rows]


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
    rows = list(result.scalars())
    ids = [r.id for r in rows]
    event_map = await _fetch_event_map(ids, db)
    source_map = await _fetch_origin_source_map(ids, db)
    return [_build_commitment_read(row, event_map, source_map) for row in rows]


@router.get("/best-next-moves", response_model=BestNextMovesResponse)
async def best_next_moves(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BestNextMovesResponse:
    """Return ≤5 commitments grouped by best-next-move rationale.

    Groups:
    - Quick wins: low-effort commitment types (confirm, send, update, follow_up)
      OR shortlist items with confidence ≥ 0.65
    - Likely blockers: overdue items with external counterparty
    - Needs focus: remaining surfaced items by priority
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # Fetch all surfaced, active commitments for this user
    result = await db.execute(
        select(Commitment)
        .where(
            Commitment.user_id == user_id,
            Commitment.lifecycle_state.in_(_SURFACED_STATES),
            Commitment.surfaced_as.isnot(None),
        )
        .order_by(Commitment.priority_score.desc().nullslast(), Commitment.created_at.desc())
    )
    all_rows = list(result.scalars())
    ids = [r.id for r in all_rows]
    event_map = await _fetch_event_map(ids, db)
    source_map = await _fetch_origin_source_map(ids, db)

    quick_wins: list[CommitmentRead] = []
    blockers: list[CommitmentRead] = []
    needs_focus: list[CommitmentRead] = []
    seen_ids: set[str] = set()
    total = 0

    # Pass 1: Quick wins — low-effort types or shortlist with decent confidence
    for row in all_rows:
        if total >= 5:
            break
        is_quick_type = row.commitment_type in _QUICK_WIN_TYPES
        is_shortlist_confident = (
            row.surfaced_as == "shortlist"
            and row.confidence_for_surfacing is not None
            and float(row.confidence_for_surfacing) >= 0.65
        )
        if is_quick_type or is_shortlist_confident:
            quick_wins.append(_build_commitment_read(row, event_map, source_map))
            seen_ids.add(row.id)
            total += 1
            if len(quick_wins) >= 2:
                break

    # Pass 2: Likely blockers — overdue with external counterparty
    for row in all_rows:
        if total >= 5:
            break
        if row.id in seen_ids:
            continue
        is_overdue = (
            row.resolved_deadline is not None
            and row.resolved_deadline < now
        ) or (
            row.suggested_due_date is not None
            and row.suggested_due_date < now
        )
        is_external = row.counterparty_type == "external"
        if is_overdue and is_external:
            blockers.append(_build_commitment_read(row, event_map, source_map))
            seen_ids.add(row.id)
            total += 1
            if len(blockers) >= 2:
                break

    # Pass 3: Needs focus — remaining surfaced items by priority
    for row in all_rows:
        if total >= 5:
            break
        if row.id in seen_ids:
            continue
        needs_focus.append(_build_commitment_read(row, event_map, source_map))
        seen_ids.add(row.id)
        total += 1

    groups = []
    if quick_wins:
        groups.append(BestNextMovesGroup(label="Quick wins", items=quick_wins))
    if blockers:
        groups.append(BestNextMovesGroup(label="Likely blockers", items=blockers))
    if needs_focus:
        groups.append(BestNextMovesGroup(label="Needs focus", items=needs_focus))

    return BestNextMovesResponse(groups=groups)


@router.get("/internal", response_model=list[CommitmentRead])
async def surface_internal(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentRead]:
    """Return unsurfaced active commitments (debug/admin view)."""
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
    rows = list(result.scalars())
    event_map = await _fetch_event_map([r.id for r in rows], db)
    return [_build_commitment_read(row, event_map, source_map) for row in rows]
