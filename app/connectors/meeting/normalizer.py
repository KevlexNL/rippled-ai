"""Normalise meeting transcript payloads to SourceItemCreate.

One SourceItem per meeting (per Q1 decision).
Full transcript as content; segments stored in metadata_.
"""
from datetime import timezone

from app.connectors.meeting.schemas import MeetingTranscriptPayload
from app.connectors.shared.participant_classifier import is_external_participant
from app.models.schemas import SourceItemCreate


def normalise_meeting_transcript(
    payload: MeetingTranscriptPayload,
    source_id: str,
) -> SourceItemCreate:
    """Translate a MeetingTranscriptPayload into a single SourceItemCreate.

    Content = full transcript as "[Speaker]: text" lines.
    Segments are stored in metadata_ for traceability.
    """
    # Build full transcript content
    transcript_lines = [
        f"[{seg.speaker}]: {seg.text}"
        for seg in payload.segments
    ]
    content = "\n".join(transcript_lines)

    # Normalise occurred_at to UTC
    occurred_at = payload.started_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)

    # Build recipients from participants
    recipients = [
        {"name": p.get("name"), "email": p.get("email")}
        for p in payload.participants
    ]

    # Determine if any participant is external
    participant_emails = [p.get("email") for p in payload.participants if p.get("email")]
    has_external = any(is_external_participant(e) for e in participant_emails)

    # Sender = first participant or None
    organiser = payload.participants[0] if payload.participants else None
    sender_name = organiser.get("name") if organiser else None
    sender_email = organiser.get("email") if organiser else None

    return SourceItemCreate(
        source_id=source_id,
        source_type="meeting",
        external_id=payload.meeting_id,
        thread_id=payload.meeting_id,
        direction=None,
        sender_name=sender_name,
        sender_email=sender_email,
        is_external_participant=has_external,
        content=content or None,
        content_normalized=content.lower().strip() if content else None,
        has_attachment=False,
        recipients=recipients if recipients else None,
        source_url=payload.source_url,
        occurred_at=occurred_at,
        metadata_={
            "title": payload.meeting_title,
            "segments": [seg.model_dump() for seg in payload.segments],
            "ended_at": payload.ended_at.isoformat() if payload.ended_at else None,
            **(payload.metadata or {}),
        },
        is_quoted_content=False,
    )
