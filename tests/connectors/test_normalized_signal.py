"""Tests for NormalizedSignal contract and connector signal output."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.connectors.shared.normalized_signal import NormalizedSignal, Participant


class TestNormalizedSignalDataclass:
    """Verify the NormalizedSignal dataclass structure."""

    def test_create_minimal_signal(self):
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sig = NormalizedSignal(
            signal_id="msg-001",
            source_type="email",
            source_thread_id=None,
            source_message_id="msg-001",
            occurred_at=now,
            authored_at=now,
            actor_participants=[],
            addressed_participants=[],
            visible_participants=[],
            latest_authored_text="Hello world",
            prior_context_text=None,
        )
        assert sig.signal_id == "msg-001"
        assert sig.source_type == "email"
        assert sig.latest_authored_text == "Hello world"
        assert sig.prior_context_text is None
        assert sig.attachments == []
        assert sig.links == []
        assert sig.metadata == {}

    def test_participant_fields(self):
        p = Participant(name="Alice", email="alice@example.com", role="sender")
        assert p.name == "Alice"
        assert p.email == "alice@example.com"
        assert p.role == "sender"

    def test_participant_defaults_to_none(self):
        p = Participant()
        assert p.name is None
        assert p.email is None
        assert p.role is None


class TestEmailNormalizerSignal:
    """Email normalizer must return (SourceItemCreate, NormalizedSignal)."""

    def _make_payload(self, **kwargs):
        from app.connectors.email.schemas import RawEmailPayload

        defaults = {
            "message_id": "<msg001@example.com>",
            "from_email": "alice@example.com",
            "from_name": "Alice Smith",
            "to": ["bob@example.com"],
            "cc": ["carol@example.com"],
            "subject": "Project Update",
            "body_plain": "I'll send the report by Friday.",
            "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "direction": "inbound",
        }
        defaults.update(kwargs)
        return RawEmailPayload(**defaults)

    def test_returns_tuple_of_source_item_and_signal(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload()
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=True):
            result = normalise_email(payload, "src-001")

        # Must return a tuple now
        assert isinstance(result, tuple)
        item, signal = result
        assert signal is not None
        assert isinstance(signal, NormalizedSignal)

    def test_signal_latest_authored_text_excludes_quoted(self):
        from app.connectors.email.normalizer import normalise_email

        body = "I'll handle this.\n\nOn Jan 1, 2024, Bob wrote:\n> Can you handle this?"
        payload = self._make_payload(body_plain=body)
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        assert "I'll handle this" in signal.latest_authored_text
        assert "Can you handle this" not in signal.latest_authored_text

    def test_signal_prior_context_contains_quoted(self):
        from app.connectors.email.normalizer import normalise_email

        body = "I'll handle this.\n\nOn Jan 1, 2024, Bob wrote:\n> Can you handle this?"
        payload = self._make_payload(body_plain=body)
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        assert signal.prior_context_text is not None
        assert "Can you handle this" in signal.prior_context_text

    def test_signal_no_prior_context_for_clean_email(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload(body_plain="Clean email, no quotes.")
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        assert signal.prior_context_text is None

    def test_signal_actor_from_sender(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload()
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=True):
            _, signal = normalise_email(payload, "src-001")

        assert len(signal.actor_participants) == 1
        assert signal.actor_participants[0].name == "Alice Smith"
        assert signal.actor_participants[0].email == "alice@example.com"
        assert signal.actor_participants[0].role == "sender"

    def test_signal_addressed_from_to_and_cc(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload(to=["bob@example.com"], cc=["carol@example.com"])
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        emails = [p.email for p in signal.addressed_participants]
        assert "bob@example.com" in emails
        assert "carol@example.com" in emails
        # Check roles
        roles = {p.email: p.role for p in signal.addressed_participants}
        assert roles["bob@example.com"] == "recipient"
        assert roles["carol@example.com"] == "cc"

    def test_signal_source_fields(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload(
            references="<root@example.com> <parent@example.com>"
        )
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        assert signal.signal_id == "<msg001@example.com>"
        assert signal.source_type == "email"
        assert signal.source_thread_id == "<root@example.com>"
        assert signal.source_message_id == "<msg001@example.com>"

    def test_signal_metadata_includes_subject(self):
        from app.connectors.email.normalizer import normalise_email

        payload = self._make_payload(subject="Budget Review")
        with patch("app.connectors.email.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_email(payload, "src-001")

        assert signal.metadata.get("subject") == "Budget Review"


class TestSlackNormalizerSignal:
    """Slack normalizer must return (SourceItemCreate | None, NormalizedSignal | None)."""

    def _make_event(self, **kwargs):
        defaults = {
            "type": "message",
            "ts": "1704067200.000001",
            "channel": "C123",
            "text": "I'll follow up on the budget",
            "user": "U456",
            "user_profile": {"display_name": "Alice", "real_name": "Alice Smith"},
            "team": "T789",
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_tuple(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event()
        result = normalise_slack_event(event, "src-001")
        assert isinstance(result, tuple)
        item, signal = result
        assert item is not None
        assert signal is not None

    def test_filtered_event_returns_none_tuple(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event(bot_id="B123")
        result = normalise_slack_event(event, "src-001")
        assert result == (None, None)

    def test_signal_actor_from_sender(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event()
        _, signal = normalise_slack_event(event, "src-001")
        assert len(signal.actor_participants) == 1
        assert signal.actor_participants[0].name == "Alice"
        assert signal.actor_participants[0].role == "sender"

    def test_signal_addressed_from_mentions(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event(text="Hey <@U789> can you review this?")
        _, signal = normalise_slack_event(event, "src-001")
        mentioned = [p for p in signal.addressed_participants if p.role == "mentioned"]
        assert len(mentioned) == 1
        assert mentioned[0].name == "U789"

    def test_signal_thread_id_from_thread_ts(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event(thread_ts="1704067100.000001")
        _, signal = normalise_slack_event(event, "src-001")
        assert signal.source_thread_id == "1704067100.000001"

    def test_signal_latest_authored_text(self):
        from app.connectors.slack.normalizer import normalise_slack_event

        event = self._make_event(text="I'll send the report")
        _, signal = normalise_slack_event(event, "src-001")
        assert signal.latest_authored_text == "I'll send the report"


class TestMeetingNormalizerSignal:
    """Meeting normalizer must return (SourceItemCreate, NormalizedSignal)."""

    def _make_payload(self):
        from app.connectors.meeting.schemas import MeetingTranscriptPayload, TranscriptSegment

        return MeetingTranscriptPayload(
            meeting_id="mtg-001",
            meeting_title="Sprint Review",
            started_at=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            segments=[
                TranscriptSegment(speaker="Alice", text="I'll handle the deployment.", start_seconds=0, end_seconds=5),
                TranscriptSegment(speaker="Bob", text="I'll review the PR.", start_seconds=5, end_seconds=10),
            ],
            participants=[
                {"name": "Alice", "email": "alice@company.com"},
                {"name": "Bob", "email": "bob@external.com"},
            ],
        )

    def test_returns_tuple(self):
        from app.connectors.meeting.normalizer import normalise_meeting_transcript

        payload = self._make_payload()
        with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
            result = normalise_meeting_transcript(payload, "src-001")
        assert isinstance(result, tuple)
        item, signal = result
        assert signal is not None

    def test_signal_actor_from_speakers(self):
        from app.connectors.meeting.normalizer import normalise_meeting_transcript

        payload = self._make_payload()
        with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_meeting_transcript(payload, "src-001")
        speaker_names = [p.name for p in signal.actor_participants]
        assert "Alice" in speaker_names
        assert "Bob" in speaker_names

    def test_signal_visible_from_attendees(self):
        from app.connectors.meeting.normalizer import normalise_meeting_transcript

        payload = self._make_payload()
        with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_meeting_transcript(payload, "src-001")
        visible_emails = [p.email for p in signal.visible_participants]
        assert "alice@company.com" in visible_emails
        assert "bob@external.com" in visible_emails

    def test_signal_latest_authored_text_is_transcript(self):
        from app.connectors.meeting.normalizer import normalise_meeting_transcript

        payload = self._make_payload()
        with patch("app.connectors.meeting.normalizer.is_external_participant", return_value=False):
            _, signal = normalise_meeting_transcript(payload, "src-001")
        assert "[Alice]: I'll handle the deployment." in signal.latest_authored_text
        assert "[Bob]: I'll review the PR." in signal.latest_authored_text


class TestReadaiNormalizerSignal:
    """Read.ai normalizer must return (SourceItemCreate, NormalizedSignal)."""

    def _make_meeting(self):
        return {
            "id": "readai-001",
            "title": "Weekly Sync",
            "start_time_ms": 1704110400000,
            "duration_ms": 1800000,
            "participants": [
                {"name": "Alice", "email": "alice@company.com"},
                {"name": "Bob", "email": "bob@external.com"},
            ],
            "transcript": {
                "segments": [
                    {"speaker": "Alice", "text": "I'll send the notes."},
                    {"speaker": "Bob", "text": "I'll check the metrics."},
                ]
            },
            "summary": {"overview": "Sprint sync discussion."},
            "action_items": [{"text": "Send notes", "assignee": "Alice"}],
        }

    def test_returns_tuple(self):
        from app.connectors.meeting.readai_normalizer import normalise_readai_meeting

        with patch("app.connectors.meeting.readai_normalizer.is_external_participant", return_value=False):
            result = normalise_readai_meeting(self._make_meeting(), "src-001")
        assert isinstance(result, tuple)
        item, signal = result
        assert signal is not None

    def test_signal_actor_from_transcript_speakers(self):
        from app.connectors.meeting.readai_normalizer import normalise_readai_meeting

        with patch("app.connectors.meeting.readai_normalizer.is_external_participant", return_value=False):
            _, signal = normalise_readai_meeting(self._make_meeting(), "src-001")
        speaker_names = [p.name for p in signal.actor_participants]
        assert "Alice" in speaker_names
        assert "Bob" in speaker_names
