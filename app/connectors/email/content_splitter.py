"""Split email body into authored content and quoted history.

Returns (latest_authored_text, prior_context_text) where prior_context_text
is None if no quoted content was detected.
"""
import re

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
    # Underscore divider (Outlook)
    re.compile(r"^[_]{20,}$"),
    # Dash divider (20+ dashes)
    re.compile(r"^-{20,}$"),
    # "Sent from my iPhone" / "Sent from my iPad" etc.
    re.compile(r"^sent from my \w+", re.IGNORECASE),
    # Signature marker: line that is exactly "--" (RFC 3676)
    re.compile(r"^--\s*$"),
]

# Quoted-line prefix: "> text" (any nesting level)
_QUOTE_LINE_RE = re.compile(r"^\s*>")


def split_email_content(raw_body: str) -> tuple[str, str | None]:
    """Split an email body into latest authored text and prior context.

    Returns:
        (latest_authored_text, prior_context_text)
        - latest_authored_text: only the current author's new content
        - prior_context_text: everything else (quoted history, signatures),
          or None if no quoted content was found
    """
    if not raw_body:
        return "", None

    lines = raw_body.splitlines()
    split_index: int | None = None

    for i, line in enumerate(lines):
        stripped = line.rstrip()

        # Check for a divider pattern
        if any(p.match(stripped) for p in _DIVIDER_PATTERNS):
            split_index = i
            break

        # Check for quoted-line prefix ("> text")
        if _QUOTE_LINE_RE.match(line):
            split_index = i
            break

    if split_index is None:
        # No quoted content found
        return raw_body.strip(), None

    latest_lines = lines[:split_index]
    prior_lines = lines[split_index:]

    latest = "\n".join(latest_lines).strip()
    prior = "\n".join(prior_lines).strip()

    if not prior:
        prior = None

    return latest, prior
