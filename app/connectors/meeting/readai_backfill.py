"""Read.ai meeting backfill orchestrator.

Fetches historical meetings from Read.ai API, normalizes them,
and ingests as SourceItems. Deduplication is handled by the
(source_id, external_id) UniqueConstraint on source_items.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.connectors.meeting.readai_client import ReadAIClient
from app.connectors.meeting.readai_normalizer import normalise_readai_meeting
from app.connectors.shared.credentials_utils import decrypt_credentials
from app.connectors.shared.ingestor import ingest_item
from app.models.orm import Source

logger = logging.getLogger(__name__)


def _get_readai_client(source: Source) -> ReadAIClient:
    """Create a ReadAIClient from Source credentials."""
    creds = decrypt_credentials(source.credentials or {})
    return ReadAIClient(
        access_token=creds.get("access_token", ""),
        refresh_token=creds.get("refresh_token", ""),
        client_id=creds.get("client_id", ""),
        client_secret=creds.get("client_secret", ""),
    )


def backfill_meetings(
    source: Source,
    days: int,
    db: Session,
) -> dict:
    """Backfill historical meetings from Read.ai for a given source.

    Args:
        source: The Source row with Read.ai credentials.
        days: How many days back to fetch.
        db: SQLAlchemy sync session.

    Returns:
        Dict with fetched, created, duplicates, errors, batch_id.
    """
    batch_id = str(uuid.uuid4())
    user_id = source.user_id
    source_id = source.id

    logger.info(
        "Read.ai backfill: starting for source %s, user %s, days=%d, batch_id=%s",
        source_id, user_id, days, batch_id,
    )

    client = _get_readai_client(source)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_ms = int(since.timestamp() * 1000)

    meetings = client.list_meetings(since_ms=since_ms)
    logger.info(
        "Read.ai backfill: fetched %d meeting(s) from API for source %s",
        len(meetings), source_id,
    )

    created = 0
    duplicates = 0
    errors = 0

    for i, meeting_summary in enumerate(meetings, 1):
        meeting_id = meeting_summary.get("id")
        try:
            detail = client.get_meeting_detail(meeting_id)
            if not detail:
                logger.warning(
                    "Read.ai backfill: empty detail for meeting %s — skipping",
                    meeting_id,
                )
                errors += 1
                continue

            item = normalise_readai_meeting(detail, source_id=str(source_id))

            # Add batch tracking to metadata
            if item.metadata_:
                item.metadata_["backfill_batch_id"] = batch_id
            else:
                item.metadata_ = {"backfill_batch_id": batch_id}

            _, was_created = ingest_item(item, str(user_id), db)

            if was_created:
                created += 1
            else:
                duplicates += 1

            if i % 10 == 0:
                logger.info(
                    "Read.ai backfill: progress %d/%d (created=%d, dupes=%d, errors=%d)",
                    i, len(meetings), created, duplicates, errors,
                )

        except Exception:
            logger.exception(
                "Read.ai backfill: error processing meeting %s", meeting_id,
            )
            errors += 1

    logger.info(
        "Read.ai backfill: complete for source %s — fetched=%d, created=%d, duplicates=%d, errors=%d, batch_id=%s",
        source_id, len(meetings), created, duplicates, errors, batch_id,
    )

    return {
        "fetched": len(meetings),
        "created": created,
        "duplicates": duplicates,
        "errors": errors,
        "batch_id": batch_id,
    }
