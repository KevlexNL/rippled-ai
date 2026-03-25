"""Tests for app/connectors/slack/normalizer.py"""

from app.connectors.shared.normalized_signal import (
    NormalizedAttachment,
    NormalizedParticipant,
)
from app.connectors.slack.normalizer import normalise_slack_event
from app.models.enums import Direction, NormalizationFlag, ParticipantRole


def _make_event(**kwargs) -> dict:
    defaults = {
        "type": "message",
        "ts": "1704067200.000001",
        "user": "U12345",
        "text": "I'll send the report by Friday.",
        "channel": "C12345",
        "team": "T12345",
    }
    defaults.update(kwargs)
    return defaults


class TestNormaliseSlackEvent:
    def test_standard_message_correct_fields(self):
        event = _make_event()
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.source_id == "src-001"
        assert item.source_type == "slack"
        assert item.external_id == "1704067200.000001"
        assert item.direction is None
        assert item.sender_id == "U12345"
        assert "Friday" in (item.content or "")

    def test_thread_reply_thread_id_is_parent_ts(self):
        event = _make_event(ts="1704067300.000002", thread_ts="1704067200.000001")
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.thread_id == "1704067200.000001"
        assert item.external_id == "1704067300.000002"

    def test_top_level_message_thread_id_equals_external_id(self):
        event = _make_event()  # no thread_ts
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.thread_id == item.external_id

    def test_bot_message_filtered(self):
        event = _make_event(bot_id="B12345")
        item, signal = normalise_slack_event(event, "src-001")
        assert item is None
        assert signal is None

    def test_bot_subtype_filtered(self):
        event = _make_event(subtype="bot_message")
        item, signal = normalise_slack_event(event, "src-001")
        assert item is None

    def test_message_changed_filtered(self):
        event = _make_event(type="message_changed")
        item, signal = normalise_slack_event(event, "src-001")
        assert item is None

    def test_non_message_type_filtered(self):
        event = _make_event(type="reaction_added")
        item, signal = normalise_slack_event(event, "src-001")
        assert item is None

    def test_file_attachment_detected(self):
        event = _make_event(
            files=[{"id": "F123", "name": "report.pdf", "mimetype": "application/pdf", "size": 1024}]
        )
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.has_attachment is True
        assert item.attachment_metadata is not None

    def test_user_profile_display_name_used(self):
        event = _make_event(user_profile={"display_name": "Alice Smith"})
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.sender_name == "Alice Smith"

    def test_occurred_at_parsed_from_ts(self):
        event = _make_event(ts="1704067200.000001")
        item, _signal = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.occurred_at.tzinfo is not None
        assert item.occurred_at.year == 2024


class TestNormalizedSignalWOFields:
    """Tests for WO-specified NormalizedSignal fields on Slack normalizer output."""

    def test_provider_is_slack(self):
        _, signal = normalise_slack_event(_make_event(), "src-001")
        assert signal is not None
        assert signal.provider == "slack"

    def test_provider_message_id_from_event_ts(self):
        _, signal = normalise_slack_event(_make_event(ts="1704067200.000001"), "src-001")
        assert signal.provider_message_id == "1704067200.000001"

    def test_provider_thread_id_from_thread_ts(self):
        _, signal = normalise_slack_event(
            _make_event(ts="1704067300.000002", thread_ts="1704067200.000001"), "src-001"
        )
        assert signal.provider_thread_id == "1704067200.000001"

    def test_provider_thread_id_none_for_top_level(self):
        _, signal = normalise_slack_event(_make_event(), "src-001")
        assert signal.provider_thread_id is None

    def test_signal_timestamp_matches_occurred_at(self):
        _, signal = normalise_slack_event(_make_event(), "src-001")
        assert signal.signal_timestamp is not None
        assert signal.signal_timestamp == signal.occurred_at

    def test_direction_is_inbound(self):
        _, signal = normalise_slack_event(_make_event(), "src-001")
        assert signal.direction == Direction.inbound
        assert signal.is_inbound is True
        assert signal.is_outbound is False

    def test_text_present_true_when_text(self):
        _, signal = normalise_slack_event(_make_event(text="hello"), "src-001")
        assert signal.text_present is True

    def test_text_present_false_when_empty(self):
        _, signal = normalise_slack_event(_make_event(text=""), "src-001")
        assert signal.text_present is False

    def test_sender_is_normalized_participant(self):
        _, signal = normalise_slack_event(
            _make_event(user="U12345", user_profile={"display_name": "Alice"}), "src-001"
        )
        assert signal.sender is not None
        assert isinstance(signal.sender, NormalizedParticipant)
        assert signal.sender.display_name == "Alice"
        assert signal.sender.role == ParticipantRole.sender

    def test_participants_include_sender_and_mentions(self):
        _, signal = normalise_slack_event(
            _make_event(text="Hey <@U999> check this", user="U12345"), "src-001"
        )
        assert signal.participants is not None
        assert len(signal.participants) >= 2
        roles = {p.role for p in signal.participants}
        assert ParticipantRole.sender in roles

    def test_attachment_metadata_populated(self):
        _, signal = normalise_slack_event(
            _make_event(files=[{"id": "F1", "name": "doc.pdf", "mimetype": "application/pdf", "size": 2048}]),
            "src-001",
        )
        assert len(signal.attachment_metadata) == 1
        att = signal.attachment_metadata[0]
        assert isinstance(att, NormalizedAttachment)
        assert att.filename == "doc.pdf"
        assert att.mime_type == "application/pdf"
        assert att.size_bytes == 2048
        assert att.provider_attachment_id == "F1"

    def test_normalization_flag_attachment_present(self):
        _, signal = normalise_slack_event(
            _make_event(files=[{"id": "F1", "name": "x.txt", "mimetype": "text/plain", "size": 10}]),
            "src-001",
        )
        assert NormalizationFlag.attachment_present in signal.normalization_flags

    def test_normalization_flag_quoted_text_detected(self):
        _, signal = normalise_slack_event(
            _make_event(text=">>> quoted block here"), "src-001"
        )
        assert NormalizationFlag.quoted_text_detected in signal.normalization_flags

    def test_no_flags_for_plain_message(self):
        _, signal = normalise_slack_event(
            _make_event(text="Just a plain message"), "src-001"
        )
        assert NormalizationFlag.attachment_present not in signal.normalization_flags
        assert NormalizationFlag.quoted_text_detected not in signal.normalization_flags

    def test_provider_account_id_from_team(self):
        _, signal = normalise_slack_event(_make_event(team="T99999"), "src-001")
        assert signal.provider_account_id == "T99999"
