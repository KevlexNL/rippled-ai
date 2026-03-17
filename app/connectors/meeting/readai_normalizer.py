"""Normalise Read.ai meeting API responses to SourceItemCreate.

Stores Read.ai's action_items as reference_action_items in metadata
(calibration signal, not ground truth commitments). See WO-RIPPLED-MEETING-BACKFILL.
"""
from datetime import datetime, timezone

from app.connectors.shared.participant_classifier import is_external_participant
from app.models.schemas import SourceItemCreate


def normalise_readai_meeting(
    meeting: dict,
    source_id: str,
) -> SourceItemCreate:
    """Convert a Read.ai meeting detail response to a SourceItemCreate.

    Content priority:
    1. Transcript segments formatted as "[Speaker]: text"
    2. Summary overview (fallback if no transcript)
    """
    meeting_id = meeting["id"]
    title = meeting.get("title")
    start_time_ms = meeting.get("start_time_ms", 0)
    duration_ms = meeting.get("duration_ms")
    participants = meeting.get("participants") or []
    summary = meeting.get("summary")
    action_items = meeting.get("action_items") or []
    transcript = meeting.get("transcript")

    # Build content from transcript or summary
    content = _build_content(transcript, summary)

    # Normalise timestamp
    occurred_at = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)

    # Build recipients from participants
    recipients = [
        {"name": p.get("name"), "email": p.get("email")}
        for p in participants
    ]

    # Determine if any participant is external
    participant_emails = [p.get("email") for p in participants if p.get("email")]
    has_external = any(is_external_participant(e) for e in participant_emails)

    # Sender = first participant (organiser)
    organiser = participants[0] if participants else None
    sender_name = organiser.get("name") if organiser else None
    sender_email = organiser.get("email") if organiser else None

    return SourceItemCreate(
        source_id=source_id,
        source_type="meeting",
        external_id=meeting_id,
        thread_id=meeting_id,
        direction=None,
        sender_name=sender_name,
        sender_email=sender_email,
        is_external_participant=has_external,
        content=content or None,
        content_normalized=content.lower().strip() if content else None,
        has_attachment=False,
        recipients=recipients if recipients else None,
        source_url=None,
        occurred_at=occurred_at,
        metadata_={
            "title": title,
            "duration_ms": duration_ms,
            "participants": participants,
            "reference_action_items": action_items,
            "summary": summary,
        },
        is_quoted_content=False,
    )


def _build_content(transcript: dict | None, summary: dict | None) -> str:
    """Build content string from transcript segments or summary."""
    if transcript and transcript.get("segments"):
        lines = [
            f"[{seg.get('speaker', 'Unknown')}]: {seg.get('text', '')}"
            for seg in transcript["segments"]
        ]
        return "\n".join(lines)

    if summary and summary.get("overview"):
        return summary["overview"]

    return ""
