"""Normalise inbound email payloads to SourceItemCreate + NormalizedSignal."""
from datetime import timezone

from app.connectors.email.content_splitter import split_email_content
from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.normalized_signal import NormalizedSignal, Participant
from app.connectors.shared.participant_classifier import is_external_participant
from app.models.schemas import SourceItemCreate


def normalise_email(
    payload: RawEmailPayload,
    source_id: str,
) -> tuple[SourceItemCreate, NormalizedSignal]:
    """Translate a RawEmailPayload into a SourceItemCreate and NormalizedSignal.

    Strips quoted content and classifies participant as internal/external.
    """
    # Normalise occurred_at to UTC
    occurred_at = payload.date
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)

    # Split email into authored content and quoted history
    raw_body = payload.body_plain or ""
    latest_authored, prior_context = split_email_content(raw_body)
    is_quoted = prior_context is not None

    # Thread ID: use in_reply_to if present, else message_id (start of thread)
    thread_id = _extract_thread_id(payload.message_id, payload.in_reply_to, payload.references)

    # Build recipients list
    recipients = [{"email": e, "type": "to"} for e in payload.to]
    recipients += [{"email": e, "type": "cc"} for e in payload.cc]

    # Sender classification
    external = is_external_participant(payload.from_email)

    # Build metadata with prior context when available
    metadata: dict = {
        "subject": payload.subject,
        "raw_headers": payload.raw_headers or {},
    }
    if prior_context:
        metadata["prior_context"] = prior_context

    item = SourceItemCreate(
        source_id=source_id,
        source_type="email",
        external_id=payload.message_id,
        thread_id=thread_id,
        direction=payload.direction,
        sender_name=payload.from_name,
        sender_email=payload.from_email,
        is_external_participant=external,
        content=raw_body.strip() if raw_body.strip() else None,
        content_normalized=latest_authored if latest_authored else None,
        has_attachment=payload.has_attachment,
        attachment_metadata={"attachments": payload.attachment_metadata} if payload.attachment_metadata else None,
        recipients=recipients if recipients else None,
        source_url=payload.source_url,
        occurred_at=occurred_at,
        metadata_=metadata,
        is_quoted_content=is_quoted,
    )

    # Build NormalizedSignal
    actor = Participant(
        name=payload.from_name,
        email=payload.from_email,
        role="sender",
    )
    addressed = [
        Participant(email=e, role="recipient") for e in payload.to
    ] + [
        Participant(email=e, role="cc") for e in payload.cc
    ]

    # Attachments as list of dicts
    attachments = []
    if payload.attachment_metadata:
        attachments = payload.attachment_metadata

    signal = NormalizedSignal(
        signal_id=payload.message_id,
        source_type="email",
        source_thread_id=thread_id,
        source_message_id=payload.message_id,
        occurred_at=occurred_at,
        authored_at=occurred_at,
        actor_participants=[actor],
        addressed_participants=addressed,
        visible_participants=[actor] + addressed,
        latest_authored_text=latest_authored or "",
        prior_context_text=prior_context,
        attachments=attachments,
        metadata={"subject": payload.subject},
    )

    return item, signal


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
