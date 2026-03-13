"""Tests for app/connectors/shared/quoted_email_stripper.py"""

from app.connectors.shared.quoted_email_stripper import strip_quoted_content


class TestStripQuotedContent:
    def test_empty_body_returns_unchanged(self):
        result, is_quoted = strip_quoted_content("")
        assert result == ""
        assert is_quoted is False

    def test_plain_body_no_quotes(self):
        body = "Hello, please review the contract.\n\nThanks, Alice"
        result, is_quoted = strip_quoted_content(body)
        assert "Hello" in result
        assert is_quoted is False

    def test_single_quoted_line_stripped(self):
        body = "Thanks for the update.\n> This is a quoted line."
        result, is_quoted = strip_quoted_content(body)
        assert "> " not in result
        assert is_quoted is True
        assert "Thanks for the update." in result

    def test_multiple_quoted_lines_stripped(self):
        body = "Got it.\n> Line 1\n> Line 2\n> Line 3"
        result, is_quoted = strip_quoted_content(body)
        assert result == "Got it."
        assert is_quoted is True

    def test_original_message_divider_strips_below(self):
        body = "I'll take care of it.\n--- Original Message ---\nOld content here."
        result, is_quoted = strip_quoted_content(body)
        assert "Old content" not in result
        assert "I'll take care of it." in result
        assert is_quoted is True

    def test_on_wrote_divider_strips_below(self):
        body = "Done.\nOn Mon, Jan 1 2024, john@example.com wrote:\n> Old message"
        result, is_quoted = strip_quoted_content(body)
        assert result == "Done."
        assert is_quoted is True

    def test_body_only_quotes_returns_empty_with_flag(self):
        body = "> Line 1\n> Line 2"
        result, is_quoted = strip_quoted_content(body)
        assert result == ""
        assert is_quoted is True

    def test_new_content_before_quotes(self):
        body = "See my note below.\n> Original message\n> With more context"
        result, is_quoted = strip_quoted_content(body)
        assert result == "See my note below."
        assert is_quoted is True
