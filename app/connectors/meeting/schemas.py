"""Pydantic schemas for meeting transcript payloads."""
from datetime import datetime
from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    """A single speaker turn in a meeting transcript."""
    speaker: str
    text: str
    start_seconds: float
    end_seconds: float


class MeetingTranscriptPayload(BaseModel):
    """Inbound meeting transcript payload from any upstream transcription provider."""
    meeting_id: str
    meeting_title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[dict]  # {"name": "...", "email": "..."}
    segments: list[TranscriptSegment]
    source_url: str | None = None
    metadata: dict | None = None
