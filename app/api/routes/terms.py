"""Common terms routes — manage domain vocabulary for transcript enrichment."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import CommonTerm, CommonTermAlias

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity/terms", tags=["terms"])


# ─── Schemas ──────────────────────────────────────────────────────────────


class AliasRead(BaseModel):
    id: str
    alias: str
    source: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CommonTermRead(BaseModel):
    id: str
    user_id: str
    canonical_term: str
    context: str | None
    aliases: list[AliasRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateTermBody(BaseModel):
    canonical_term: str
    context: str | None = None
    aliases: list[str] = []


class UpdateTermBody(BaseModel):
    canonical_term: str | None = None
    context: str | None = None


class AddAliasBody(BaseModel):
    alias: str


# ─── Helpers ─────────────────────────────────────────────────────────────


async def _get_user_term(
    term_id: str, user_id: str, db: AsyncSession
) -> CommonTerm:
    """Fetch a term scoped to user. Raises 404 if not found."""
    result = await db.execute(
        select(CommonTerm)
        .options(selectinload(CommonTerm.aliases))
        .where(CommonTerm.id == term_id, CommonTerm.user_id == user_id)
    )
    term = result.scalar_one_or_none()
    if term is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return term


# ─── Routes ──────────────────────────────────────────────────────────────


@router.get("", response_model=list[CommonTermRead])
async def list_terms(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all terms with aliases for the current user."""
    result = await db.execute(
        select(CommonTerm)
        .where(CommonTerm.user_id == user_id)
    )
    terms = result.scalars().all()

    # Eager-load aliases for each term
    for term in terms:
        alias_result = await db.execute(
            select(CommonTermAlias).where(CommonTermAlias.term_id == term.id)
        )
        term.aliases = alias_result.scalars().all()

    return terms


@router.post("", response_model=CommonTermRead, status_code=201)
async def create_term(
    body: CreateTermBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a term with optional initial aliases."""
    term = CommonTerm()
    term.user_id = user_id
    term.canonical_term = body.canonical_term
    term.context = body.context
    db.add(term)
    await db.flush()

    for alias_str in body.aliases:
        alias = CommonTermAlias()
        alias.term_id = term.id
        alias.alias = alias_str.strip()
        alias.source = "manual"
        db.add(alias)

    await db.flush()
    await db.refresh(term)
    return term


@router.patch("/{term_id}", response_model=CommonTermRead)
async def update_term(
    term_id: str,
    body: UpdateTermBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update canonical_term and/or context."""
    term = await _get_user_term(term_id, user_id, db)

    if body.canonical_term is not None:
        term.canonical_term = body.canonical_term
    if body.context is not None:
        term.context = body.context

    await db.flush()
    await db.refresh(term)
    return term


@router.delete("/{term_id}", status_code=204)
async def delete_term(
    term_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a term (cascades aliases)."""
    term = await _get_user_term(term_id, user_id, db)
    await db.delete(term)


@router.post("/{term_id}/aliases", response_model=AliasRead, status_code=201)
async def add_alias(
    term_id: str,
    body: AddAliasBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add an alias to a term."""
    await _get_user_term(term_id, user_id, db)

    alias = CommonTermAlias()
    alias.term_id = term_id
    alias.alias = body.alias.strip()
    alias.source = "manual"
    db.add(alias)
    await db.flush()
    await db.refresh(alias)
    return alias


@router.delete("/{term_id}/aliases/{alias_id}", status_code=204)
async def delete_alias(
    term_id: str,
    alias_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove an alias from a term."""
    await _get_user_term(term_id, user_id, db)

    result = await db.execute(
        select(CommonTermAlias).where(
            CommonTermAlias.id == alias_id,
            CommonTermAlias.term_id == term_id,
        )
    )
    alias = result.scalar_one_or_none()
    if alias is None:
        raise HTTPException(status_code=404, detail="Alias not found")
    await db.delete(alias)
