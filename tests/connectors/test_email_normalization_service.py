"""Tests for EmailNormalizationService — full pipeline tests with 12+ fixtures.

Covers WO sections: text extraction, quoted text separation, signature handling,
direction detection, participant normalization, attachment metadata, thread metadata.
"""

import hashlib
import json
import pytest
from datetime import datetime, timezone

from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.normalized_signal import NormalizedSignal
from app.models.enums import Direction, NormalizationFlag, ParticipantRole
from app.services.normalization.email_normalization_service import EmailNormalizationService


def _make_payload(**kwargs) -> RawEmailPayload:
    """Helper to build RawEmailPayload with sensible defaults."""
    defaults = {
        "message_id": "<msg001@example.com>",
        "from_email": "alice@example.com",
        "from_name": "Alice Smith",
        "to": ["bob@example.com"],
        "cc": [],
        "subject": "Project Update",
        "body_plain": "Hello Bob, I'll send the report by Friday.",
        "body_html": "",
        "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "direction": "inbound",
    }
    defaults.update(kwargs)
    return RawEmailPayload(**defaults)


def _normalize(payload: RawEmailPayload, user_email: str = "bob@example.com") -> NormalizedSignal:
    """Run the normalization service and return the signal."""
    service = EmailNormalizationService(user_email=user_email)
    return service.normalize(payload)


# ---- Fixture 1: Simple inbound email ----

class TestFixtureSimpleInbound:
    def test_basic_fields(self):
        signal = _normalize(_make_payload())
        assert signal.latest_authored_text == "Hello Bob, I'll send the report by Friday."
        assert signal.prior_context_text is None
        assert signal.subject == "Project Update"
        assert signal.provider_message_id == "<msg001@example.com>"

    def test_direction_inbound(self):
        signal = _normalize(_make_payload())
        assert signal.direction == Direction.inbound
        assert signal.is_inbound is True
        assert signal.is_outbound is False

    def test_sender_participant(self):
        signal = _normalize(_make_payload())
        assert signal.sender is not None
        assert signal.sender.email == "alice@example.com"
        assert signal.sender.display_name == "Alice Smith"
        assert signal.sender.role == ParticipantRole.sender

    def test_to_participants(self):
        signal = _normalize(_make_payload())
        assert len(signal.to) == 1
        assert signal.to[0].email == "bob@example.com"
        assert signal.to[0].is_primary_user is True

    def test_text_present_flag(self):
        signal = _normalize(_make_payload())
        assert signal.text_present is True
        assert signal.html_present is False


# ---- Fixture 2: Simple outbound email ----

class TestFixtureSimpleOutbound:
    def test_outbound_direction(self):
        signal = _normalize(
            _make_payload(
                from_email="me@company.com",
                to=["vendor@external.com"],
            ),
            user_email="me@company.com",
        )
        assert signal.direction == Direction.outbound
        assert signal.is_outbound is True
        assert signal.is_inbound is False
        assert signal.sender.is_primary_user is True


# ---- Fixture 3: Reply with quoted content ----

class TestFixtureReplyWithQuotes:
    def test_quoted_text_separated(self):
        body = "I'll handle this.\n\nOn Jan 1, 2024, Bob wrote:\n> Can you handle this?"
        signal = _normalize(_make_payload(body_plain=body))
        assert signal.latest_authored_text == "I'll handle this."
        assert signal.prior_context_text is not None
        assert "Can you handle this" in signal.prior_context_text

    def test_quoted_text_flag(self):
        body = "I'll handle this.\n\nOn Jan 1, 2024, Bob wrote:\n> Can you handle this?"
        signal = _normalize(_make_payload(body_plain=body))
        assert NormalizationFlag.quoted_text_detected in signal.normalization_flags

    def test_source_subtype_reply(self):
        body = "I'll handle this.\n\nOn Jan 1, 2024, Bob wrote:\n> Can you handle this?"
        signal = _normalize(_make_payload(
            body_plain=body,
            subject="Re: Project Update",
            in_reply_to="<original@example.com>",
        ))
        assert signal.source_subtype == "reply"


# ---- Fixture 4: Forwarded email ----

class TestFixtureForwardedEmail:
    def test_forward_detected(self):
        body = "FYI, see below.\n--- Forwarded Message ---\nFrom: carol@example.com\nOriginal content."
        signal = _normalize(_make_payload(
            body_plain=body,
            subject="Fwd: Important doc",
        ))
        assert signal.latest_authored_text == "FYI, see below."
        assert signal.source_subtype == "forward"


# ---- Fixture 5: Email with attachments ----

class TestFixtureWithAttachments:
    def test_attachment_metadata_captured(self):
        signal = _normalize(_make_payload(
            has_attachment=True,
            attachment_metadata=[
                {"filename": "report.pdf", "content_type": "application/pdf", "size": 1024},
                {"filename": "data.xlsx", "content_type": "application/vnd.ms-excel", "size": 2048},
            ],
        ))
        assert len(signal.attachment_metadata) == 2
        assert signal.attachment_metadata[0].filename == "report.pdf"
        assert signal.attachment_metadata[0].mime_type == "application/pdf"
        assert signal.attachment_metadata[0].size_bytes == 1024
        assert NormalizationFlag.attachment_present in signal.normalization_flags


# ---- Fixture 6: HTML-only email ----

class TestFixtureHtmlOnly:
    def test_html_only_extraction(self):
        signal = _normalize(_make_payload(
            body_plain="",
            body_html="<p>Please review the <b>contract</b> by EOD.</p>",
        ))
        assert "Please review the contract by EOD." in signal.latest_authored_text
        assert signal.html_present is True
        assert NormalizationFlag.html_only_body in signal.normalization_flags


# ---- Fixture 7: Email with signature ----

class TestFixtureWithSignature:
    def test_signature_stripped(self):
        body = "I'll review the doc.\n\n--\nAlice Smith\nCTO, Acme Inc.\nalice@acme.com"
        signal = _normalize(_make_payload(body_plain=body))
        assert signal.latest_authored_text == "I'll review the doc."
        assert NormalizationFlag.signature_detected in signal.normalization_flags


# ---- Fixture 8: Multiple recipients ----

class TestFixtureMultipleRecipients:
    def test_all_recipients_normalized(self):
        signal = _normalize(_make_payload(
            to=["bob@example.com", "carol@example.com"],
            cc=["dave@example.com", "eve@example.com"],
        ))
        assert len(signal.to) == 2
        assert len(signal.cc) == 2
        to_emails = {p.email for p in signal.to}
        cc_emails = {p.email for p in signal.cc}
        assert "bob@example.com" in to_emails
        assert "carol@example.com" in to_emails
        assert "dave@example.com" in cc_emails
        assert "eve@example.com" in cc_emails


# ---- Fixture 9: Missing subject ----

class TestFixtureMissingSubject:
    def test_missing_subject_flag(self):
        signal = _normalize(_make_payload(subject=""))
        assert NormalizationFlag.missing_subject in signal.normalization_flags
        assert signal.subject == ""


# ---- Fixture 10: Missing text body ----

class TestFixtureMissingTextBody:
    def test_missing_body_flag(self):
        signal = _normalize(_make_payload(body_plain="", body_html=""))
        assert NormalizationFlag.missing_text_body in signal.normalization_flags
        assert signal.latest_authored_text == ""


# ---- Fixture 11: Thread metadata ----

class TestFixtureThreadMetadata:
    def test_thread_from_references(self):
        signal = _normalize(_make_payload(
            references="<root@example.com> <parent@example.com>",
            in_reply_to="<parent@example.com>",
        ))
        assert signal.provider_thread_id == "<root@example.com>"

    def test_thread_from_in_reply_to(self):
        signal = _normalize(_make_payload(
            in_reply_to="<parent@example.com>",
        ))
        assert signal.provider_thread_id == "<parent@example.com>"

    def test_top_level_message_thread_id(self):
        signal = _normalize(_make_payload())
        assert signal.provider_thread_id == "<msg001@example.com>"


# ---- Fixture 12: Complex real-world email ----

class TestFixtureComplexRealWorld:
    """Realistic email with signature, quoted text, attachments, multiple recipients."""

    def test_complex_email_normalizes_cleanly(self):
        body = (
            "Hi team,\n\n"
            "I've attached the Q4 report. Please review by Friday.\n\n"
            "Best regards,\n"
            "Alice Smith\n"
            "VP of Engineering\n\n"
            "On Dec 28, 2023, Bob wrote:\n"
            "> Can someone pull the Q4 numbers?\n"
            "> We need them for the board meeting."
        )
        signal = _normalize(_make_payload(
            body_plain=body,
            to=["bob@example.com", "carol@example.com"],
            cc=["dave@example.com"],
            has_attachment=True,
            attachment_metadata=[{"filename": "Q4-report.pdf", "content_type": "application/pdf"}],
            references="<thread-root@example.com>",
            in_reply_to="<bobs-msg@example.com>",
        ))
        # Authored text should have greeting + content, no signature or quotes
        assert "Q4 report" in signal.latest_authored_text
        assert "board meeting" not in signal.latest_authored_text
        assert signal.prior_context_text is not None
        assert "board meeting" in signal.prior_context_text
        assert signal.direction == Direction.inbound
        assert len(signal.to) == 2
        assert len(signal.cc) == 1
        assert len(signal.attachment_metadata) == 1
        assert signal.provider_thread_id == "<thread-root@example.com>"
        assert NormalizationFlag.quoted_text_detected in signal.normalization_flags
        assert NormalizationFlag.attachment_present in signal.normalization_flags


# ---- Fixture 13: Ambiguous quoted text ----

class TestFixtureAmbiguousQuotedText:
    def test_ambiguous_best_effort(self):
        """When multiple possible authored blocks exist, use best effort."""
        body = "> Quoted line at top\n\nSome authored text.\n\nMore authored text."
        signal = _normalize(_make_payload(body_plain=body))
        # Should still produce a usable signal
        assert signal.latest_authored_text is not None


# ---- Fixture 14: Email with BCC (metadata only) ----

class TestFixtureEmailWithBcc:
    def test_bcc_not_present_in_normal_headers(self):
        """BCC typically not visible in received email; test empty handling."""
        signal = _normalize(_make_payload())
        assert signal.bcc == []


# ---- Contract / Snapshot Tests ----

class TestNormalizedSignalContract:
    """Validate exact NormalizedSignal output structure."""

    def test_all_required_fields_present(self):
        signal = _normalize(_make_payload())
        # Core identity
        assert signal.provider_message_id is not None
        assert signal.source_type == "email"
        assert signal.normalization_version == "v1"
        # Direction
        assert signal.direction is not None
        # Participants
        assert signal.sender is not None
        # Text
        assert isinstance(signal.latest_authored_text, str)
        # Flags
        assert isinstance(signal.normalization_flags, list)
        assert isinstance(signal.normalization_warnings, list)

    def test_normalization_version(self):
        signal = _normalize(_make_payload())
        assert signal.normalization_version == "v1"

    def test_signal_id_matches_provider_message_id(self):
        signal = _normalize(_make_payload())
        assert signal.signal_id == signal.provider_message_id

    def test_occurred_at_and_signal_timestamp_consistent(self):
        signal = _normalize(_make_payload())
        assert signal.occurred_at == signal.signal_timestamp
