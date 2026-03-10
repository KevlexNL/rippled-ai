from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Source, SourceItem
from app.models.schemas import SourceItemCreate, SourceItemRead

router = APIRouter(prefix="/source-items", tags=["ingestion"])


def _to_schema(row: SourceItem) -> SourceItemRead:
    return SourceItemRead.model_validate(row)


async def _validate_source_ownership(source_id: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Source.id).where(Source.id == source_id, Source.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Source not found")


def _build_item(body: SourceItemCreate, user_id: str) -> SourceItem:
    return SourceItem(
        source_id=body.source_id,
        user_id=user_id,
        source_type=body.source_type,
        external_id=body.external_id,
        thread_id=body.thread_id,
        direction=body.direction,
        sender_id=body.sender_id,
        sender_name=body.sender_name,
        sender_email=body.sender_email,
        is_external_participant=body.is_external_participant,
        content=body.content,
        content_normalized=body.content_normalized,
        has_attachment=body.has_attachment,
        attachment_metadata=body.attachment_metadata,
        recipients=body.recipients,
        source_url=body.source_url,
        occurred_at=body.occurred_at,
        metadata_=body.metadata_,
        is_quoted_content=body.is_quoted_content,
        ingested_at=datetime.now(timezone.utc),
    )


def _enqueue_detection(source_item_id: str) -> None:
    """Fire-and-forget: enqueue detect_commitments task. Silently skips if broker unavailable."""
    try:
        from app.tasks import detect_commitments
        detect_commitments.delay(source_item_id)
    except Exception:
        pass


@router.post("", response_model=SourceItemRead, status_code=201)
async def ingest_source_item(
    body: SourceItemCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceItemRead:
    await _validate_source_ownership(body.source_id, user_id, db)

    item = _build_item(body, user_id)
    db.add(item)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Return the existing item id in the detail
        existing = await db.execute(
            select(SourceItem).where(
                SourceItem.source_id == body.source_id,
                SourceItem.external_id == body.external_id,
            )
        )
        existing_item = existing.scalar_one_or_none()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Duplicate source item",
                "existing_id": existing_item.id if existing_item else None,
            },
        )

    await db.refresh(item)
    _enqueue_detection(item.id)
    return _to_schema(item)


@router.post("/batch", status_code=207)
async def ingest_source_items_batch(
    body: list[SourceItemCreate],
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if len(body) > 100:
        raise HTTPException(status_code=422, detail="Batch size must not exceed 100 items")

    results = []

    for req_item in body:
        # Validate source ownership per item
        src_result = await db.execute(
            select(Source.id).where(Source.id == req_item.source_id, Source.user_id == user_id)
        )
        if not src_result.scalar_one_or_none():
            results.append({"status": 404, "error": "Source not found", "external_id": req_item.external_id})
            continue

        item = _build_item(req_item, user_id)
        try:
            async with db.begin_nested():
                db.add(item)
                await db.flush()
            await db.refresh(item)
            results.append({"status": 201, "id": item.id, "external_id": req_item.external_id})
            _enqueue_detection(item.id)
        except IntegrityError:
            results.append({"status": 409, "error": "Duplicate", "external_id": req_item.external_id})

    return {"results": results}


@router.get("/{item_id}", response_model=SourceItemRead)
async def get_source_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceItemRead:
    result = await db.execute(
        select(SourceItem).where(SourceItem.id == item_id, SourceItem.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Source item not found")
    return _to_schema(item)
