"""Identity profile routes — manage user identity aliases for owner resolution."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Commitment, SourceItem, UserIdentityProfile
from app.services.identity.owner_resolver import resolve_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity", tags=["identity"])

# Newsletter / system patterns to skip during seed detection
_SKIP_PATTERNS = re.compile(
    r"(noreply|no-reply|notifications?|mailer-daemon|postmaster|bounce)",
    re.IGNORECASE,
)


# ─── Schemas ──────────────────────────────────────────────────────────────


class IdentityProfileRead(BaseModel):
    id: str
    user_id: str
    identity_type: str
    identity_value: str
    source: str | None
    confirmed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConfirmBody(BaseModel):
    confirm_ids: list[str] = []
    reject_ids: list[str] = []


class ManualBody(BaseModel):
    identity_type: str
    identity_value: str


class BackfillResult(BaseModel):
    updated: int


# ─── Helpers ──────────────────────────────────────────────────────────────


async def run_backfill(user_id: str, db: AsyncSession) -> int:
    """Resolve ownership for all unresolved commitments belonging to a user."""
    result = await db.execute(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.resolved_owner.is_(None),
            Commitment.suggested_owner.isnot(None),
        )
    )
    commitments = result.scalars().all()

    updated = 0
    for c in commitments:
        resolved = await resolve_owner(c.suggested_owner, user_id, db)
        if resolved:
            c.resolved_owner = resolved
            updated += 1

    if updated:
        await db.flush()

    logger.info("Backfill for user %s: %d/%d commitments resolved", user_id, updated, len(commitments))
    return updated


# ─── Routes ───────────────────────────────────────────────────────────────


@router.get("/profile", response_model=list[IdentityProfileRead])
async def get_identity_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[IdentityProfileRead]:
    result = await db.execute(
        select(UserIdentityProfile)
        .where(UserIdentityProfile.user_id == user_id)
        .order_by(UserIdentityProfile.created_at.desc())
    )
    return [IdentityProfileRead.model_validate(row) for row in result.scalars()]


@router.post("/seed", response_model=list[IdentityProfileRead])
async def seed_identities(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[IdentityProfileRead]:
    """Scan outbound source items to detect identity candidates."""
    result = await db.execute(
        select(SourceItem).where(
            SourceItem.user_id == user_id,
            SourceItem.direction == "outbound",
        )
    )
    items = result.scalars().all()

    # Collect unique emails and names
    emails: set[str] = set()
    names: set[str] = set()

    for item in items:
        if item.sender_email:
            email = item.sender_email.strip().lower()
            if email and not _SKIP_PATTERNS.search(email):
                emails.add(email)
        if item.sender_name:
            name = item.sender_name.strip()
            if name and not _SKIP_PATTERNS.search(name):
                names.add(name)

    # Upsert candidates
    for email in emails:
        stmt = pg_insert(UserIdentityProfile).values(
            user_id=user_id,
            identity_type="email",
            identity_value=email,
            source="seed_detected",
            confirmed=False,
        ).on_conflict_do_nothing(
            constraint="uq_uip_user_type_value",
        )
        await db.execute(stmt)

    for name in names:
        stmt = pg_insert(UserIdentityProfile).values(
            user_id=user_id,
            identity_type="full_name",
            identity_value=name,
            source="seed_detected",
            confirmed=False,
        ).on_conflict_do_nothing(
            constraint="uq_uip_user_type_value",
        )
        await db.execute(stmt)

    await db.flush()

    # Return all profiles (confirmed and unconfirmed)
    all_result = await db.execute(
        select(UserIdentityProfile)
        .where(UserIdentityProfile.user_id == user_id)
        .order_by(UserIdentityProfile.created_at.desc())
    )
    return [IdentityProfileRead.model_validate(row) for row in all_result.scalars()]


@router.post("/confirm", response_model=list[IdentityProfileRead])
async def confirm_identities(
    body: ConfirmBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[IdentityProfileRead]:
    """Confirm or reject identity candidates, then run backfill."""
    if body.confirm_ids:
        await db.execute(
            update(UserIdentityProfile)
            .where(
                UserIdentityProfile.id.in_(body.confirm_ids),
                UserIdentityProfile.user_id == user_id,
            )
            .values(confirmed=True)
        )

    if body.reject_ids:
        await db.execute(
            delete(UserIdentityProfile).where(
                UserIdentityProfile.id.in_(body.reject_ids),
                UserIdentityProfile.user_id == user_id,
            )
        )

    await db.flush()

    # Run backfill after confirming
    await run_backfill(user_id, db)

    # Return updated list
    result = await db.execute(
        select(UserIdentityProfile)
        .where(UserIdentityProfile.user_id == user_id)
        .order_by(UserIdentityProfile.created_at.desc())
    )
    return [IdentityProfileRead.model_validate(row) for row in result.scalars()]


@router.post("/manual", response_model=IdentityProfileRead)
async def add_manual_identity(
    body: ManualBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> IdentityProfileRead:
    """Manually add a confirmed identity entry, then run backfill."""
    valid_types = {"full_name", "first_name", "email", "alias"}
    if body.identity_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid identity_type: {body.identity_type!r}. Must be one of {sorted(valid_types)}",
        )

    profile = UserIdentityProfile(
        user_id=user_id,
        identity_type=body.identity_type,
        identity_value=body.identity_value.strip(),
        source="manual",
        confirmed=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    # Run backfill after adding
    await run_backfill(user_id, db)

    return IdentityProfileRead.model_validate(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_identity(
    profile_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(UserIdentityProfile).where(
            UserIdentityProfile.id == profile_id,
            UserIdentityProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Identity profile not found")
    await db.delete(profile)


@router.get("/status")
async def identity_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check whether the user has any confirmed identity profiles."""
    from sqlalchemy import func as sa_func

    result = await db.execute(
        select(sa_func.count(UserIdentityProfile.id)).where(
            UserIdentityProfile.user_id == user_id,
            UserIdentityProfile.confirmed.is_(True),
        )
    )
    count = result.scalar_one_or_none() or 0
    return {"has_confirmed_identities": count > 0, "confirmed_count": count}


@router.post("/backfill", response_model=BackfillResult)
async def backfill_owners(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BackfillResult:
    """Run owner resolution backfill for the current user."""
    updated = await run_backfill(user_id, db)
    return BackfillResult(updated=updated)
