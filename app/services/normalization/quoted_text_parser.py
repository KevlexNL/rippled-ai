"""QuotedTextParser — deterministic separation of latest authored text
from prior thread context.

Implements WO sections 4.7.1 (text extraction), 4.7.2 (quoted text separation),
4.7.3 (signature handling).
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO


@dataclass
class ParseResult:
    """Result of parsing an email body."""

    latest_authored_text: str = ""
    prior_context_text: str | None = None
    full_visible_text: str | None = None
    missing_text_body: bool = False
    html_only_body: bool = False
    quoted_text_detected: bool = False
    signature_detected: bool = False


# Divider patterns — content from the matching line downward is prior context.
_DIVIDER_PATTERNS: list[re.Pattern[str]] = [
    # "--- Original Message ---" / "--- Forwarded Message ---"
    re.compile(
        r"^-{3,}\s*(?:original\s+message|forwarded\s+message)\s*-{3,}",
        re.IGNORECASE,
    ),
    # "-----Original Message-----"
    re.compile(r"^-{5,}Original Message-{5,}", re.IGNORECASE),
    # "On <date>, <name> wrote:" (Gmail / Apple Mail)
    re.compile(r"^on .{3,100} wrote:\s*$", re.IGNORECASE),
    # Outlook-style forwarded header block: "From: ..."
    re.compile(r"^from:\s+.+", re.IGNORECASE),
    # Underscore divider (Outlook) — 20+ underscores
    re.compile(r"^[_]{20,}$"),
    # Dash divider (20+ dashes)
    re.compile(r"^-{20,}$"),
]

# Quoted-line prefix: "> text" (any nesting level)
_QUOTE_LINE_RE = re.compile(r"^\s*>")

# Signature patterns
_SIGNATURE_PATTERNS: list[re.Pattern[str]] = [
    # RFC 3676: line that is exactly "--" (with optional trailing space)
    re.compile(r"^--\s*$"),
    # "Sent from my iPhone" / "Sent from my iPad" etc.
    re.compile(r"^sent from my \w+", re.IGNORECASE),
    # "Best regards," / "Kind regards," / "Regards," / "Thanks," / "Cheers,"
    re.compile(r"^(?:best\s+regards|kind\s+regards|regards|thanks|cheers|sincerely|warm\s+regards)\s*,?\s*$", re.IGNORECASE),
]


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML-to-text extractor that preserves paragraph boundaries."""

    def __init__(self):
        super().__init__()
        self._result = StringIO()
        self._in_blockquote = False
        self._blockquote_text = StringIO()
        self._blockquote_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "blockquote":
            self._blockquote_depth += 1
            self._in_blockquote = True
        elif tag in ("p", "br", "div", "li", "tr"):
            if self._in_blockquote:
                self._blockquote_text.write("\n")
            else:
                self._result.write("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "blockquote":
            self._blockquote_depth -= 1
            if self._blockquote_depth == 0:
                self._in_blockquote = False

    def handle_data(self, data: str) -> None:
        if self._in_blockquote:
            self._blockquote_text.write(data)
        else:
            self._result.write(data)

    def get_text(self) -> str:
        return self._result.getvalue().strip()

    def get_blockquote_text(self) -> str:
        return self._blockquote_text.getvalue().strip()


class QuotedTextParser:
    """Deterministic parser for separating authored text from thread context."""

    @staticmethod
    def parse(raw_body: str) -> ParseResult:
        """Parse a plain-text email body.

        Returns a ParseResult with latest_authored_text separated from
        prior_context_text, with signature handling.
        """
        if not raw_body or not raw_body.strip():
            return ParseResult(
                latest_authored_text="",
                missing_text_body=True,
            )

        full_text = raw_body.strip()
        lines = raw_body.splitlines()

        # Find the first divider/quote line
        split_index = _find_split_index(lines)

        if split_index is None:
            # No quoted content — check for signature only
            latest, sig_detected = _strip_signature(full_text)
            return ParseResult(
                latest_authored_text=latest,
                prior_context_text=None,
                full_visible_text=full_text,
                signature_detected=sig_detected,
            )

        latest_lines = lines[:split_index]
        prior_lines = lines[split_index:]

        latest_raw = "\n".join(latest_lines).strip()
        prior = "\n".join(prior_lines).strip() or None

        # Strip signature from the authored portion
        latest, sig_detected = _strip_signature(latest_raw)

        return ParseResult(
            latest_authored_text=latest,
            prior_context_text=prior,
            full_visible_text=full_text,
            quoted_text_detected=True,
            signature_detected=sig_detected,
        )

    @staticmethod
    def parse_html(html_body: str) -> ParseResult:
        """Parse an HTML-only email body.

        Extracts text safely, preserves paragraph boundaries,
        and detects blockquote-based quoted content.
        """
        if not html_body or not html_body.strip():
            return ParseResult(
                latest_authored_text="",
                missing_text_body=True,
                html_only_body=True,
            )

        extractor = _HTMLTextExtractor()
        extractor.feed(html_body)

        authored = extractor.get_text()
        blockquote = extractor.get_blockquote_text()

        has_quotes = bool(blockquote)

        # Strip signature from authored text
        latest, sig_detected = _strip_signature(authored)

        return ParseResult(
            latest_authored_text=latest,
            prior_context_text=blockquote if has_quotes else None,
            full_visible_text=f"{authored}\n{blockquote}".strip() if blockquote else authored,
            html_only_body=True,
            quoted_text_detected=has_quotes,
            signature_detected=sig_detected,
        )


def _find_split_index(lines: list[str]) -> int | None:
    """Find the line index where quoted/prior content begins."""
    for i, line in enumerate(lines):
        stripped = line.rstrip()

        # Check for a divider pattern
        if any(p.match(stripped) for p in _DIVIDER_PATTERNS):
            return i

        # Check for quoted-line prefix ("> text")
        if _QUOTE_LINE_RE.match(line):
            return i

    return None


def _strip_signature(text: str) -> tuple[str, bool]:
    """Strip likely signatures from authored text.

    Returns (cleaned_text, signature_detected).
    """
    if not text:
        return text, False

    lines = text.splitlines()

    # Don't strip very short messages entirely
    if len(lines) <= 1:
        return text, False

    # Check for signature markers from bottom up
    sig_index = None

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if any(p.match(stripped) for p in _SIGNATURE_PATTERNS):
            sig_index = i
            break

    if sig_index is None:
        return text, False

    # Only strip if there's meaningful content before the signature
    before = "\n".join(lines[:sig_index]).strip()
    if not before:
        # Entire text is signature-like — preserve it
        return text, False

    return before, True
