"""Tests for QuotedTextParser — deterministic separation of authored text
from prior thread context. Covers WO sections 4.7.1, 4.7.2, 4.7.3."""

import pytest

from app.services.normalization.quoted_text_parser import QuotedTextParser


class TestLatestAuthoredTextExtraction:
    """4.7.1 — derive latestAuthoredText, priorContextText, fullVisibleText."""

    def test_plain_text_no_quotes(self):
        result = QuotedTextParser.parse("Hello, please review the contract.")
        assert result.latest_authored_text == "Hello, please review the contract."
        assert result.prior_context_text is None

    def test_empty_body(self):
        result = QuotedTextParser.parse("")
        assert result.latest_authored_text == ""
        assert result.prior_context_text is None
        assert result.missing_text_body is True

    def test_html_only_body(self):
        result = QuotedTextParser.parse_html(
            "<p>Please review the <b>contract</b>.</p><p>Thanks, Alice</p>"
        )
        assert "Please review the contract" in result.latest_authored_text
        assert result.html_only_body is True

    def test_html_preserves_paragraph_boundaries(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        result = QuotedTextParser.parse_html(html)
        assert "\n" in result.latest_authored_text

    def test_full_visible_text_populated(self):
        body = "My reply.\n\nOn Jan 1, Alice wrote:\n> Old text here."
        result = QuotedTextParser.parse(body)
        assert result.full_visible_text == body.strip()


class TestQuotedTextSeparation:
    """4.7.2 — Hard requirement: deterministic separation."""

    def test_gmail_on_date_wrote(self):
        body = "Sounds good.\n\nOn Mon, Jan 1 2024, john@example.com wrote:\n> Old message here"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Sounds good."
        assert "john@example.com wrote:" in result.prior_context_text
        assert result.quoted_text_detected is True

    def test_outlook_from_sent_to_subject(self):
        body = "Thanks.\nFrom: alice@example.com\nSent: Monday\nTo: bob@example.com\nSubject: Re: Hello"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Thanks."
        assert "alice@example.com" in result.prior_context_text

    def test_forwarded_message_divider(self):
        body = "FYI see below.\n--- Forwarded Message ---\nFrom: someone@example.com\nOld stuff"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "FYI see below."
        assert "Forwarded Message" in result.prior_context_text

    def test_original_message_divider(self):
        body = "I'll handle it.\n-----Original Message-----\nFrom: boss@example.com\nDo this please."
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "I'll handle it."

    def test_quoted_line_prefix(self):
        body = "Thanks for the update.\n> This is a quoted line."
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Thanks for the update."
        assert "> This is a quoted line." in result.prior_context_text

    def test_nested_quotes(self):
        body = "My reply.\n> Their reply\n>> Original message"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "My reply."
        assert "Their reply" in result.prior_context_text
        assert "Original message" in result.prior_context_text

    def test_underscore_divider(self):
        body = "Noted.\n________________________________\nFrom: sender@example.com\nOld content"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Noted."

    def test_dash_divider(self):
        body = "Will do.\n--------------------\nFrom: someone\nPrevious stuff"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Will do."

    def test_html_blockquote(self):
        html = "<p>I agree.</p><blockquote>Previous email content here</blockquote>"
        result = QuotedTextParser.parse_html(html)
        assert "I agree." in result.latest_authored_text
        assert result.quoted_text_detected is True

    def test_ambiguous_split_adds_warning(self):
        """If uncertain about split point, add warning flag."""
        # Two possible authored blocks after quoted content
        body = "First part.\n\nOn Mon wrote:\n> Quoted\n\nSecond part after quote."
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "First part."
        assert result.prior_context_text is not None

    def test_entirely_quoted_body(self):
        body = "> Line 1\n> Line 2"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == ""
        assert "Line 1" in result.prior_context_text


class TestSignatureHandling:
    """4.7.3 — Remove likely signatures from latestAuthoredText."""

    def test_rfc3676_signature_marker(self):
        body = "I'll review the doc.\n\n--\nAlice Smith\nCTO, Acme Inc."
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "I'll review the doc."
        assert result.signature_detected is True

    def test_sent_from_iphone(self):
        body = "I'll call you tomorrow.\n\nSent from my iPhone"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "I'll call you tomorrow."
        assert result.signature_detected is True

    def test_common_signature_patterns(self):
        body = "Sounds good.\n\nBest regards,\nBob Johnson\nSenior Engineer\n555-123-4567"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Sounds good."
        assert result.signature_detected is True

    def test_short_body_not_mistaken_for_signature(self):
        """A short body shouldn't be entirely stripped as signature."""
        body = "Thanks"
        result = QuotedTextParser.parse(body)
        assert result.latest_authored_text == "Thanks"
        assert result.signature_detected is False
