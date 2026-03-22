"""Tests for app/connectors/email/content_splitter.py"""

from app.connectors.email.content_splitter import split_email_content


class TestSplitEmailContent:
    """Test split_email_content returns (latest_authored_text, prior_context_text)."""

    def test_empty_body(self):
        latest, prior = split_email_content("")
        assert latest == ""
        assert prior is None

    def test_plain_body_no_quotes(self):
        body = "Hello, please review the contract.\n\nThanks, Alice"
        latest, prior = split_email_content(body)
        assert latest == body.strip()
        assert prior is None

    # --- Quoted lines with > prefix ---

    def test_single_quoted_line(self):
        body = "Thanks for the update.\n> This is a quoted line."
        latest, prior = split_email_content(body)
        assert latest == "Thanks for the update."
        assert "> This is a quoted line." in prior

    def test_multiple_quoted_lines(self):
        body = "Got it.\n> Line 1\n> Line 2\n> Line 3"
        latest, prior = split_email_content(body)
        assert latest == "Got it."
        assert "Line 1" in prior
        assert "Line 3" in prior

    def test_multi_level_nested_quotes(self):
        body = "My reply.\n> Their reply\n>> Original message\n>>> Even deeper"
        latest, prior = split_email_content(body)
        assert latest == "My reply."
        assert "Their reply" in prior
        assert "Original message" in prior
        assert "Even deeper" in prior

    # --- On ... wrote: header ---

    def test_on_wrote_gmail_style(self):
        body = "Sounds good.\n\nOn Mon, Jan 1 2024, john@example.com wrote:\n> Old message here"
        latest, prior = split_email_content(body)
        assert latest == "Sounds good."
        assert "john@example.com wrote:" in prior
        assert "Old message here" in prior

    def test_on_wrote_outlook_style(self):
        body = "I agree.\nOn January 1, 2024 at 10:00 AM John Smith wrote:\nPrevious content"
        latest, prior = split_email_content(body)
        assert latest == "I agree."
        assert "John Smith wrote:" in prior

    # --- Forwarded email headers ---

    def test_forwarded_message_divider(self):
        body = "FYI see below.\n--- Forwarded Message ---\nFrom: someone@example.com\nOld stuff"
        latest, prior = split_email_content(body)
        assert latest == "FYI see below."
        assert "Forwarded Message" in prior

    # --- Original Message divider ---

    def test_original_message_divider(self):
        body = "I'll handle it.\n-----Original Message-----\nFrom: boss@example.com\nDo this please."
        latest, prior = split_email_content(body)
        assert latest == "I'll handle it."
        assert "Original Message" in prior

    # --- Outlook underscore divider ---

    def test_outlook_underscore_divider(self):
        body = "Noted.\n________________________________\nFrom: sender@example.com\nOld content"
        latest, prior = split_email_content(body)
        assert latest == "Noted."
        assert "Old content" in prior

    # --- Outlook dash divider ---

    def test_outlook_dash_divider(self):
        body = "Will do.\n--------------------\nFrom: someone\nPrevious stuff"
        latest, prior = split_email_content(body)
        assert latest == "Will do."
        assert "Previous stuff" in prior

    # --- From: header as divider ---

    def test_from_header_divider(self):
        body = "Thanks.\nFrom: alice@example.com\nSent: Monday\nTo: bob@example.com\nSubject: Re: Hello"
        latest, prior = split_email_content(body)
        assert latest == "Thanks."
        assert "alice@example.com" in prior

    # --- Sent from my iPhone signature ---

    def test_sent_from_iphone_signature(self):
        body = "I'll call you tomorrow.\n\nSent from my iPhone"
        latest, prior = split_email_content(body)
        assert latest == "I'll call you tomorrow."
        assert "Sent from my iPhone" in prior

    # --- Body that is entirely quoted ---

    def test_entirely_quoted_body(self):
        body = "> Line 1\n> Line 2"
        latest, prior = split_email_content(body)
        assert latest == ""
        assert "Line 1" in prior

    # --- Whitespace handling ---

    def test_trailing_whitespace_stripped_from_latest(self):
        body = "My reply.\n\n\n> Quoted stuff"
        latest, prior = split_email_content(body)
        assert latest == "My reply."
        assert not latest.endswith("\n")

    # --- Signature marker -- ---

    def test_signature_double_dash(self):
        body = "I'll review the doc.\n\n--\nAlice Smith\nCTO, Acme Inc."
        latest, prior = split_email_content(body)
        assert latest == "I'll review the doc."
        assert "Alice Smith" in prior

    # --- Mixed: authored text, then quote, then more authored (rare) ---

    def test_content_before_first_divider_is_latest(self):
        """Only content before the FIRST divider is latest_authored_text."""
        body = "First part.\n\nOn Mon wrote:\n> Quoted\n\nSecond part after quote."
        latest, prior = split_email_content(body)
        assert latest == "First part."
        # Everything from divider down is prior context
        assert "Quoted" in prior
