"""Tests for app/connectors/email/normalizer.py"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from app.connectors.email.normalizer import _extract_thread_id, normalise_email
from app.connectors.email.schemas import RawEmailPayload


def _make_payload(**kwargs) -> RawEmailPayload:
    defaults = {
        "message_id": "<msg001@example.com>",
        "from_email": "alice@example.com",
        "from_name": "Alice Smith",
        "to": ["bob@example.com"],
        "cc": [],
        "subject": "Project Update",
        "body_plain": "Hello Bob, I'll send the report by Friday.",
        "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "direction": "inbound",
    }
    defaults.update(kwargs)
    return RawEmailPayload(**defaults)


@contextmanager
def _patch_classifier(is_external: bool = True):
    with patch(
        "app.connectors.email.normalizer.is_external_participant",
        return_value=is_external,
    ):
        yield


class TestNormaliseEmail:
    def test_plain_email_correct_fields(self):
        payload = _make_payload()
        with _patch_classifier(is_external=True):
            item = normalise_email(payload, "src-001")

        assert item.source_id == "src-001"
        assert item.source_type == "email"
        assert item.external_id == "<msg001@example.com>"
        assert item.direction == "inbound"
        assert item.sender_email == "alice@example.com"
        assert item.sender_name == "Alice Smith"
        assert item.is_quoted_content is False
        assert "Friday" in (item.content or "")

    def test_outbound_email_direction(self):
        payload = _make_payload(direction="outbound")
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.direction == "outbound"

    def test_email_with_quoted_content_flagged(self):
        body = "Thanks.\n> Original message here."
        payload = _make_payload(body_plain=body)
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.is_quoted_content is True
        assert "> " not in (item.content or "")

    def test_internal_sender_not_external(self):
        payload = _make_payload(from_email="alice@company.com")
        with _patch_classifier(is_external=False):
            item = normalise_email(payload, "src-001")
        assert item.is_external_participant is False

    def test_external_sender_is_external(self):
        payload = _make_payload(from_email="vendor@external.com")
        with _patch_classifier(is_external=True):
            item = normalise_email(payload, "src-001")
        assert item.is_external_participant is True

    def test_email_with_attachments(self):
        payload = _make_payload(
            has_attachment=True,
            attachment_metadata=[{"filename": "report.pdf", "content_type": "application/pdf"}],
        )
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.has_attachment is True
        assert item.attachment_metadata is not None

    def test_recipients_populated_from_to_and_cc(self):
        payload = _make_payload(to=["bob@example.com"], cc=["carol@example.com"])
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert len(item.recipients) == 2
        assert any(r["email"] == "bob@example.com" for r in item.recipients)
        assert any(r["email"] == "carol@example.com" for r in item.recipients)

    def test_thread_id_from_in_reply_to(self):
        payload = _make_payload(in_reply_to="<parent@example.com>")
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.thread_id == "<parent@example.com>"

    def test_thread_id_from_references_uses_first(self):
        payload = _make_payload(references="<root@example.com> <parent@example.com>")
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.thread_id == "<root@example.com>"

    def test_top_level_email_thread_id_equals_message_id(self):
        payload = _make_payload()
        with _patch_classifier():
            item = normalise_email(payload, "src-001")
        assert item.thread_id == "<msg001@example.com>"


class TestExtractThreadId:
    def test_uses_first_reference_when_present(self):
        result = _extract_thread_id("<msg>", None, "<root> <parent>")
        assert result == "<root>"

    def test_falls_back_to_in_reply_to(self):
        result = _extract_thread_id("<msg>", "<parent>", None)
        assert result == "<parent>"

    def test_falls_back_to_message_id_when_no_thread(self):
        result = _extract_thread_id("<msg>", None, None)
        assert result == "<msg>"
