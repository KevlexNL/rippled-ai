"""Normalise Read.ai meeting API responses to SourceItemCreate + NormalizedSignal.

Stores Read.ai's action_items as reference_action_items in metadata
(calibration signal, not ground truth commitments). See WO-RIPPLED-MEETING-BACKFILL.
"""
from datetime import datetime, timezone

from app.connectors.shared.normalized_signal import NormalizedParticipant, NormalizedSignal, Participant
from app.connectors.shared.participant_classifier import is_external_participant
from app.models.enums import Direction, NormalizationFlag, ParticipantRole
from app.models.schemas import SourceItemCreate


def normalise_readai_meeting(
    meeting: dict,
    source_id: str,
) -> tuple[SourceItemCreate, NormalizedSignal]:
    """Convert a Read.ai meeting detail response to a SourceItemCreate and NormalizedSignal.

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

    item = SourceItemCreate(
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

    # Build NormalizedSignal
    # Actor participants = speakers from transcript (if available)
    actors = _extract_speakers(transcript)

    # Visible participants = all meeting attendees (legacy)
    visible = [
        Participant(
            name=p.get("name"),
            email=p.get("email"),
            role="attendee",
        )
        for p in participants
    ]

    # NormalizedParticipant list (new WO field)
    normalized_participants = [
        NormalizedParticipant(
            email=p.get("email"),
            display_name=p.get("name"),
            role=ParticipantRole.unknown,
            is_primary_user=False,
        )
        for p in participants
    ]

    # Normalization flags
    flags: list[NormalizationFlag] = []
    if _has_unresolved_speakers(transcript):
        flags.append(NormalizationFlag.speaker_unresolved)

    signal = NormalizedSignal(
        signal_id=meeting_id,
        source_type="meeting",
        source_thread_id=meeting_id,
        source_message_id=None,
        occurred_at=occurred_at,
        authored_at=occurred_at,
        actor_participants=actors,
        addressed_participants=[],
        visible_participants=visible,
        latest_authored_text=content,
        prior_context_text=None,
        # New WO fields
        provider="readai",
        provider_message_id=meeting_id,
        provider_thread_id=None,
        signal_timestamp=occurred_at,
        direction=Direction.inbound,
        is_inbound=True,
        is_outbound=False,
        text_present=bool(content),
        participants=normalized_participants,
        normalization_flags=flags,
        metadata={
            "title": title,
            "duration_ms": duration_ms,
            "reference_action_items": action_items,
        },
    )

    return item, signal


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


def _extract_speakers(transcript: dict | None) -> list[Participant]:
    """Extract unique speakers from transcript as actor participants."""
    if not transcript or not transcript.get("segments"):
        return []
    speaker_names = list(dict.fromkeys(
        seg.get("speaker", "Unknown") for seg in transcript["segments"]
    ))
    return [Participant(name=name, role="speaker") for name in speaker_names]


def _has_unresolved_speakers(transcript: dict | None) -> bool:
    """Check if any speaker in the transcript is unresolved ('Unknown')."""
    if not transcript or not transcript.get("segments"):
        return False
    return any(
        seg.get("speaker", "Unknown") == "Unknown"
        for seg in transcript["segments"]
    )
