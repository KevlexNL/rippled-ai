"""Normalise inbound email payloads to SourceItemCreate."""
from datetime import timezone

from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.participant_classifier import is_external_participant
from app.connectors.shared.quoted_email_stripper import strip_quoted_content
from app.models.schemas import SourceItemCreate


def normalise_email(
    payload: RawEmailPayload,
    source_id: str,
) -> SourceItemCreate:
    """Translate a RawEmailPayload into a SourceItemCreate.

    Strips quoted content and classifies participant as internal/external.
    """
    # Normalise occurred_at to UTC
    occurred_at = payload.date
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)

    # Strip quoted content
    raw_body = payload.body_plain or ""
    content, is_quoted = strip_quoted_content(raw_body)

    # Thread ID: use in_reply_to if present, else message_id (start of thread)
    thread_id = _extract_thread_id(payload.message_id, payload.in_reply_to, payload.references)

    # Build recipients list
    recipients = [{"email": e, "type": "to"} for e in payload.to]
    recipients += [{"email": e, "type": "cc"} for e in payload.cc]

    # Sender classification
    external = is_external_participant(payload.from_email)

    return SourceItemCreate(
        source_id=source_id,
        source_type="email",
        external_id=payload.message_id,
        thread_id=thread_id,
        direction=payload.direction,
        sender_name=payload.from_name,
        sender_email=payload.from_email,
        is_external_participant=external,
        content=content if content else None,
        content_normalized=content.lower().strip() if content else None,
        has_attachment=payload.has_attachment,
        attachment_metadata={"attachments": payload.attachment_metadata} if payload.attachment_metadata else None,
        recipients=recipients if recipients else None,
        source_url=payload.source_url,
        occurred_at=occurred_at,
        metadata_={
            "subject": payload.subject,
            "raw_headers": payload.raw_headers or {},
        },
        is_quoted_content=is_quoted,
    )


def _extract_thread_id(
    message_id: str,
    in_reply_to: str | None,
    references: str | None,
) -> str:
    """Extract the root message ID to use as thread_id.

    Prefers the oldest reference (first in References header) or in_reply_to.
    Falls back to message_id itself (top-level message).
    """
    if references:
        # References is a space-separated list, oldest first
        refs = references.strip().split()
        if refs:
            return refs[0]

    if in_reply_to:
        return in_reply_to.strip()

    return message_id
