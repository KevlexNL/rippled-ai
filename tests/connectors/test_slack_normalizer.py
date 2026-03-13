"""Tests for app/connectors/slack/normalizer.py"""

from app.connectors.slack.normalizer import normalise_slack_event


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
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.source_id == "src-001"
        assert item.source_type == "slack"
        assert item.external_id == "1704067200.000001"
        assert item.direction is None
        assert item.sender_id == "U12345"
        assert "Friday" in (item.content or "")

    def test_thread_reply_thread_id_is_parent_ts(self):
        event = _make_event(ts="1704067300.000002", thread_ts="1704067200.000001")
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.thread_id == "1704067200.000001"
        assert item.external_id == "1704067300.000002"

    def test_top_level_message_thread_id_equals_external_id(self):
        event = _make_event()  # no thread_ts
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.thread_id == item.external_id

    def test_bot_message_filtered(self):
        event = _make_event(bot_id="B12345")
        assert normalise_slack_event(event, "src-001") is None

    def test_bot_subtype_filtered(self):
        event = _make_event(subtype="bot_message")
        assert normalise_slack_event(event, "src-001") is None

    def test_message_changed_filtered(self):
        event = _make_event(type="message_changed")
        assert normalise_slack_event(event, "src-001") is None

    def test_non_message_type_filtered(self):
        event = _make_event(type="reaction_added")
        assert normalise_slack_event(event, "src-001") is None

    def test_file_attachment_detected(self):
        event = _make_event(
            files=[{"id": "F123", "name": "report.pdf", "mimetype": "application/pdf", "size": 1024}]
        )
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.has_attachment is True
        assert item.attachment_metadata is not None

    def test_user_profile_display_name_used(self):
        event = _make_event(user_profile={"display_name": "Alice Smith"})
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.sender_name == "Alice Smith"

    def test_occurred_at_parsed_from_ts(self):
        event = _make_event(ts="1704067200.000001")
        item = normalise_slack_event(event, "src-001")
        assert item is not None
        assert item.occurred_at.tzinfo is not None
        assert item.occurred_at.year == 2024
