"""Tests for app/connectors/meeting/normalizer.py"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.meeting.normalizer import normalise_meeting_transcript
from app.connectors.meeting.schemas import MeetingTranscriptPayload, TranscriptSegment


def _make_payload(**kwargs) -> MeetingTranscriptPayload:
    defaults = {
        "meeting_id": "meeting-001",
        "meeting_title": "Sprint Planning",
        "started_at": datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        "ended_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        "participants": [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
        ],
        "segments": [
            TranscriptSegment(speaker="Alice", text="I'll prepare the report.", start_seconds=0, end_seconds=5),
            TranscriptSegment(speaker="Bob", text="Sounds good.", start_seconds=5, end_seconds=8),
        ],
    }
    defaults.update(kwargs)
    return MeetingTranscriptPayload(**defaults)


def _patch_classifier(is_external: bool = False):
    return patch(
        "app.connectors.meeting.normalizer.is_external_participant",
        return_value=is_external,
    )


class TestNormaliseMeetingTranscript:
    def test_one_source_item_per_meeting(self):
        with _patch_classifier():
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert item is not None
        assert item.source_type == "meeting"

    def test_external_id_equals_meeting_id(self):
        with _patch_classifier():
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert item.external_id == "meeting-001"
        assert item.thread_id == "meeting-001"

    def test_content_is_full_transcript_with_speakers(self):
        with _patch_classifier():
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert "[Alice]:" in item.content
        assert "[Bob]:" in item.content
        assert "I'll prepare the report." in item.content

    def test_segments_stored_in_metadata(self):
        with _patch_classifier():
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert item.metadata_["segments"] is not None
        assert len(item.metadata_["segments"]) == 2

    def test_occurred_at_equals_started_at(self):
        started = datetime(2024, 3, 1, 14, 0, 0, tzinfo=timezone.utc)
        payload = _make_payload(started_at=started)
        with _patch_classifier():
            item = normalise_meeting_transcript(payload, "src-001")
        assert item.occurred_at == started

    def test_external_participant_flag(self):
        with _patch_classifier(is_external=True):
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert item.is_external_participant is True

    def test_participants_in_recipients(self):
        with _patch_classifier():
            item = normalise_meeting_transcript(_make_payload(), "src-001")
        assert item.recipients is not None
        assert any(r["email"] == "alice@example.com" for r in item.recipients)
