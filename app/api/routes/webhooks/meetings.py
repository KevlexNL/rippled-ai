"""Meeting transcript webhook handler.

POST /webhooks/meetings/transcript — receives structured meeting transcripts.
"""
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.meeting.normalizer import normalise_meeting_transcript
from app.connectors.meeting.schemas import MeetingTranscriptPayload
from app.core.config import get_settings
from app.db.deps import get_db
from app.models.orm import Source
from app.models.schemas import SourceItemRead

router = APIRouter(prefix="/webhooks/meetings", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def _get_or_create_source(user_id: str, meeting_id: str, db: AsyncSession) -> Source:
    """Upsert Source for (user_id, meeting, provider_account_id)."""
    # Use user_id as provider_account_id since meetings don't have a fixed account
    provider_account_id = f"meetings:{user_id}"
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "meeting",
            Source.provider_account_id == provider_account_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    source = Source(
        user_id=user_id,
        source_type="meeting",
        provider_account_id=provider_account_id,
        display_name="Meeting Transcripts",
        is_active=True,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


def _verify_meeting_auth(
    user_id: str | None,
    webhook_secret_header: str | None,
) -> str:
    """Verify meeting endpoint authentication.

    If MEETING_WEBHOOK_SECRET is configured: verify X-Rippled-Webhook-Secret header.
    Otherwise: require X-User-ID header (standard auth).

    Returns the user_id or raises HTTPException.
    """
    settings = get_settings()

    if settings.meeting_webhook_secret:
        if not webhook_secret_header:
            raise HTTPException(status_code=401, detail="X-Rippled-Webhook-Secret header required")
        if not hmac.compare_digest(settings.meeting_webhook_secret, webhook_secret_header):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
        # When using webhook secret, user_id must still be provided via X-User-ID
        if not user_id:
            raise HTTPException(status_code=401, detail="X-User-ID header required")
        return user_id

    # Fallback: standard X-User-ID auth
    if not user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    return user_id


@router.post("/transcript", status_code=201)
async def receive_meeting_transcript(
    payload: MeetingTranscriptPayload,
    x_user_id: str | None = Header(None),
    x_rippled_webhook_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> SourceItemRead:
    """Receive a meeting transcript.

    Authentication: X-Rippled-Webhook-Secret (if MEETING_WEBHOOK_SECRET is set)
    or X-User-ID header (standard auth, fallback).
    """
    from sqlalchemy.exc import IntegrityError
    from app.models.orm import SourceItem

    user_id = _verify_meeting_auth(x_user_id, x_rippled_webhook_secret)

    source = await _get_or_create_source(user_id, payload.meeting_id, db)
    item = normalise_meeting_transcript(payload, source.id)

    # Ingest inline
    from app.api.routes.source_items import _build_item, _enqueue_detection
    source_item = _build_item(item, user_id)
    db.add(source_item)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        from sqlalchemy import select as sa_select
        existing = await db.execute(
            sa_select(SourceItem).where(
                SourceItem.source_id == item.source_id,
                SourceItem.external_id == item.external_id,
            )
        )
        existing_item = existing.scalar_one_or_none()
        raise HTTPException(
            status_code=409,
            detail={"message": "Duplicate source item", "existing_id": existing_item.id if existing_item else None},
        )

    await db.refresh(source_item)
    _enqueue_detection(source_item.id)
    return SourceItemRead.model_validate(source_item)
