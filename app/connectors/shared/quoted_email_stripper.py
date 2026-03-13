"""Strip quoted/replied content from email bodies.

Returns (stripped_body, is_quoted_content) where is_quoted_content is True
if quoted blocks were found and removed.
"""
import re

# Lines that look like quoted replies ("> quoted text")
_QUOTE_LINE_RE = re.compile(r'^\s*>')

# Common reply divider patterns — content BELOW these is quoted
_DIVIDER_PATTERNS = [
    # "--- Original Message ---" variants
    re.compile(r'^-{3,}\s*(?:original\s+message|forwarded\s+message)\s*-{3,}', re.IGNORECASE),
    # Outlook-style: "From: ...\nSent: ...\nTo: ..."
    re.compile(r'^from:\s+.+', re.IGNORECASE),
    # "On <date>, <name> wrote:" — may be split across lines
    re.compile(r'^on .{3,100} wrote:\s*$', re.IGNORECASE),
    # Underscores or dashes as dividers (common in Outlook)
    re.compile(r'^[_]{20,}$'),
    re.compile(r'^[-]{20,}$'),
]


def strip_quoted_content(body: str) -> tuple[str, bool]:
    """Strip quoted email content from body.

    Returns:
        (stripped_body, is_quoted_content) tuple where:
        - stripped_body: body with quoted lines/blocks removed
        - is_quoted_content: True if any quoted content was found and removed
    """
    if not body:
        return body, False

    lines = body.splitlines()
    new_lines: list[str] = []
    found_quote = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.rstrip()

        # Check for reply divider — everything below is quoted
        if any(p.match(stripped_line) for p in _DIVIDER_PATTERNS):
            found_quote = True
            break

        # Check for quoted-line prefix ("> text")
        if _QUOTE_LINE_RE.match(line):
            found_quote = True
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if not found_quote:
        return body.strip(), False

    stripped = '\n'.join(new_lines).strip()
    original = body.strip()

    # Only flag as quoted if content was materially reduced (not just whitespace)
    if stripped == original:
        return body.strip(), False

    return stripped, True
