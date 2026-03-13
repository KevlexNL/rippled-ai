"""Shared ingest-and-enqueue utility for connector Celery tasks (sync).

Webhook routes use async DB sessions and handle ingest inline.
Celery tasks (process_slack_event, poll_email_imap) use this sync version.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.orm import Source, SourceItem
from app.models.schemas import SourceItemCreate


def get_or_create_source_sync(
    user_id: str,
    source_type: str,
    provider_account_id: str,
    db: Session,
) -> Source:
    """Upsert a Source record for (user_id, source_type, provider_account_id).

    Creates the source if it doesn't exist. Returns the existing or new Source.
    """
    existing = db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == source_type,
            Source.provider_account_id == provider_account_id,
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    source = Source(
        user_id=user_id,
        source_type=source_type,
        provider_account_id=provider_account_id,
        display_name=f"{source_type} ({provider_account_id})",
        is_active=True,
    )
    db.add(source)
    db.flush()
    db.refresh(source)
    return source


def ingest_item(
    item: SourceItemCreate,
    user_id: str,
    db: Session,
) -> tuple[SourceItem | None, bool]:
    """Ingest a SourceItem and enqueue detection. Sync version for Celery tasks.

    Returns:
        (source_item, created) where created=False means it was a duplicate (409 equivalent).
    """
    source_item = SourceItem(
        source_id=item.source_id,
        user_id=user_id,
        source_type=item.source_type,
        external_id=item.external_id,
        thread_id=item.thread_id,
        direction=item.direction,
        sender_id=item.sender_id,
        sender_name=item.sender_name,
        sender_email=item.sender_email,
        is_external_participant=item.is_external_participant,
        content=item.content,
        content_normalized=item.content_normalized,
        has_attachment=item.has_attachment,
        attachment_metadata=item.attachment_metadata,
        recipients=item.recipients,
        source_url=item.source_url,
        occurred_at=item.occurred_at,
        metadata_=item.metadata_,
        is_quoted_content=item.is_quoted_content,
        ingested_at=datetime.now(timezone.utc),
    )
    db.add(source_item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None, False

    db.refresh(source_item)
    _enqueue_detection(source_item.id)
    return source_item, True


def _enqueue_detection(source_item_id: str) -> None:
    """Fire-and-forget: enqueue detect_commitments task."""
    try:
        from app.tasks import detect_commitments
        detect_commitments.delay(source_item_id)
    except Exception:
        pass
