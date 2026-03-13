"""Email inbound webhook handler.

POST /webhooks/email/inbound — receives inbound email from SendGrid or generic sender.
"""
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.email.normalizer import normalise_email
from app.connectors.email.schemas import RawEmailPayload
from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from app.models.orm import Source, SourceItem
from app.models.schemas import SourceItemCreate, SourceItemRead

router = APIRouter(prefix="/webhooks/email", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def _get_or_create_source(user_id: str, provider_account_id: str, db: AsyncSession) -> Source:
    """Upsert Source for (user_id, email, provider_account_id)."""
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "email",
            Source.provider_account_id == provider_account_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    source = Source(
        user_id=user_id,
        source_type="email",
        provider_account_id=provider_account_id,
        display_name=f"email ({provider_account_id})",
        is_active=True,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


async def _ingest_async(item: SourceItemCreate, user_id: str, db: AsyncSession) -> SourceItemRead:
    """Ingest a SourceItemCreate into the DB and enqueue detection. Raises 409 on duplicate."""
    from app.api.routes.source_items import _build_item, _enqueue_detection
    source_item = _build_item(item, user_id)
    db.add(source_item)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = await db.execute(
            select(SourceItem).where(
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


def _verify_email_webhook_secret(request_secret: str | None) -> bool:
    """Verify optional email webhook secret. Returns True if verification passes."""
    settings = get_settings()
    configured_secret = settings.email_webhook_secret
    if not configured_secret:
        logger.warning("EMAIL_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    if not request_secret:
        return False
    return hmac.compare_digest(configured_secret, request_secret)


@router.post("/inbound", status_code=200)
async def receive_inbound_email(
    payload: RawEmailPayload,
    x_email_webhook_secret: str | None = Header(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive an inbound email via webhook (SendGrid / Mailgun / generic).

    Authentication: X-User-ID header (standard) + optional X-Email-Webhook-Secret.
    """
    if not _verify_email_webhook_secret(x_email_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    source = await _get_or_create_source(user_id, payload.from_email, db)
    item = normalise_email(payload, source.id)

    try:
        result = await _ingest_async(item, user_id, db)
    except HTTPException as e:
        if e.status_code == 409:
            raise
        raise

    return {"accepted": 1, "id": result.id}
