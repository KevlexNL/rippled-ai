from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import encrypt_credentials
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Source
from app.models.schemas import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_schema(row: Source) -> SourceRead:
    return SourceRead(
        id=row.id,
        user_id=row.user_id,
        source_type=row.source_type,
        provider_account_id=row.provider_account_id,
        display_name=row.display_name,
        is_active=row.is_active,
        has_credentials=bool(row.credentials),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("", response_model=SourceRead, status_code=201)
async def create_source(
    body: SourceCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    source = Source(
        user_id=user_id,
        source_type=body.source_type,
        provider_account_id=body.provider_account_id,
        display_name=body.display_name,
        metadata_=body.metadata_,
        credentials=encrypt_credentials(body.credentials) if body.credentials else None,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.get("", response_model=list[SourceRead])
async def list_sources(
    limit: int = 5,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SourceRead]:
    if limit > 200:
        limit = 200
    result = await db.execute(
        select(Source)
        .where(Source.user_id == user_id)
        .order_by(Source.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _to_schema(source)


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: str,
    body: SourceUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if body.display_name is not None:
        source.display_name = body.display_name
    if body.is_active is not None:
        source.is_active = body.is_active
    if body.metadata_ is not None:
        source.metadata_ = body.metadata_
    if body.credentials is not None:
        from app.connectors.shared.credentials_utils import encrypt_credentials
        source.credentials = encrypt_credentials(body.credentials)

    source.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_active = False
    source.updated_at = datetime.now(timezone.utc)
