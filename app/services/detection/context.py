"""Context window extraction for commitment candidates.

Given a SourceItem and a matched trigger span, extract the surrounding context
that downstream stages need to interpret the commitment accurately.

Each source type has different context needs:
- Meeting: surrounding speaker turns, speaker labels, timestamps
- Slack: thread parent message, neighboring messages
- Email: message body (after stripping), sender/recipients, direction
"""
from __future__ import annotations

import re
from typing import Any

from app.models.orm import SourceItem


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PRE_CONTEXT_CHARS = 200
_POST_CONTEXT_CHARS = 200

# Patterns that indicate uncertain speaker attribution in meeting transcripts
_UNCERTAIN_SPEAKER_PATTERNS = re.compile(
    r"\[(?:inaudible|crosstalk|unclear|unknown speaker)\]",
    re.IGNORECASE,
)
_GENERIC_SPEAKER_PATTERN = re.compile(
    r"^(?:Speaker\s*\d+|Unknown|Participant\s*\d+)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Meeting helpers
# ---------------------------------------------------------------------------

def _parse_speaker_turns(content: str) -> list[dict[str, str]]:
    """Parse a transcript into speaker turns.

    Supports common formats:
    - "[Speaker Name]: text"
    - "Speaker Name: text"
    - "00:01:23 [Speaker Name]: text"

    Returns list of {"speaker": str, "text": str, "timestamp": str | None}.
    """
    turns: list[dict[str, str]] = []
    # Match: optional timestamp + speaker label + colon + text
    line_pattern = re.compile(
        r"^(?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)?"  # optional timestamp
        r"\[?([^\]:\n]{1,60}?)\]?\s*:\s*"         # speaker label
        r"(.+)$",
        re.MULTILINE,
    )
    for m in line_pattern.finditer(content):
        turns.append({
            "timestamp": m.group(1),
            "speaker": m.group(2).strip(),
            "text": m.group(3).strip(),
        })

    # Fallback: if no speaker-turn structure found, treat whole content as one turn
    if not turns:
        turns.append({"timestamp": None, "speaker": None, "text": content.strip()})
    return turns


def _get_surrounding_turns(
    turns: list[dict[str, str]],
    trigger_text: str,
    window: int = 2,
) -> list[dict[str, str]]:
    """Find the turn containing trigger_text and return ±window turns."""
    trigger_idx = None
    for i, turn in enumerate(turns):
        if trigger_text.lower() in turn["text"].lower():
            trigger_idx = i
            break

    if trigger_idx is None:
        return turns[:window * 2 + 1]

    start = max(0, trigger_idx - window)
    end = min(len(turns), trigger_idx + window + 1)
    return turns[start:end]


def _flag_uncertain_attribution(turns: list[dict[str, str]], trigger_text: str) -> bool:
    """Return True if speaker attribution near the trigger looks uncertain."""
    for turn in turns:
        if trigger_text.lower() in turn["text"].lower():
            speaker = turn.get("speaker") or ""
            if _GENERIC_SPEAKER_PATTERN.match(speaker):
                return True
            if _UNCERTAIN_SPEAKER_PATTERNS.search(turn["text"]):
                return True
    return False


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def _detect_external_recipients(recipients: list | None) -> bool:
    """Return True if any recipient in the list is flagged as external."""
    if not recipients:
        return False
    for r in recipients:
        if isinstance(r, dict) and r.get("is_external"):
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_context(
    item: SourceItem,
    trigger_text: str,
    trigger_start: int,
    trigger_end: int,
    normalized_content: str,
) -> dict[str, Any]:
    """Extract context window for a detected trigger span.

    Args:
        item: The SourceItem being analysed.
        trigger_text: The exact matched text that triggered detection.
        trigger_start: Character offset of trigger start in normalized_content.
        trigger_end: Character offset of trigger end in normalized_content.
        normalized_content: The content string after suppression stripping.

    Returns:
        dict stored in CommitmentCandidate.context_window.
    """
    pre_start = max(0, trigger_start - _PRE_CONTEXT_CHARS)
    post_end = min(len(normalized_content), trigger_end + _POST_CONTEXT_CHARS)

    ctx: dict[str, Any] = {
        "trigger_text": trigger_text,
        "trigger_start": trigger_start,
        "trigger_end": trigger_end,
        "pre_context": normalized_content[pre_start:trigger_start].strip(),
        "post_context": normalized_content[trigger_end:post_end].strip(),
        "source_type": item.source_type,
        # Source-type-specific fields (populated below)
        "thread_parent": None,
        "speaker_turns": None,
        "email_direction": None,
        "has_external_recipient": None,
        "sender": item.sender_name or item.sender_email or item.sender_id,
    }

    source_type = item.source_type

    if source_type == "meeting":
        _enrich_meeting_context(ctx, item, trigger_text)
    elif source_type == "slack":
        _enrich_slack_context(ctx, item)
    elif source_type == "email":
        _enrich_email_context(ctx, item)

    return ctx


def _enrich_meeting_context(
    ctx: dict[str, Any],
    item: SourceItem,
    trigger_text: str,
) -> None:
    """Add meeting-specific context fields."""
    content = item.content_normalized or item.content or ""
    turns = _parse_speaker_turns(content)
    surrounding = _get_surrounding_turns(turns, trigger_text, window=2)
    ctx["speaker_turns"] = surrounding
    # Flag if transcript quality may affect interpretation
    ctx["flag_uncertain_speaker"] = _flag_uncertain_attribution(surrounding, trigger_text)
    ctx["has_external_recipient"] = item.is_external_participant


def _enrich_slack_context(ctx: dict[str, Any], item: SourceItem) -> None:
    """Add Slack-specific context fields."""
    # thread_parent is stored in metadata_ if available
    metadata = item.metadata_ or {}
    ctx["thread_parent"] = metadata.get("thread_parent_text")
    ctx["channel"] = metadata.get("channel_name") or metadata.get("channel_id")
    ctx["mentions"] = metadata.get("mentions", [])
    # Slack is always internal for MVP
    ctx["has_external_recipient"] = False


def _enrich_email_context(ctx: dict[str, Any], item: SourceItem) -> None:
    """Add email-specific context fields."""
    ctx["email_direction"] = item.direction  # 'inbound' | 'outbound' | None
    ctx["has_external_recipient"] = (
        item.is_external_participant
        or _detect_external_recipients(item.recipients)
    )
    # List recipients for downstream use
    ctx["recipients"] = item.recipients or []
    # Pass prior context (quoted email history) for labeled detection
    metadata = item.metadata_ or {}
    if isinstance(metadata, dict):
        ctx["prior_context"] = metadata.get("prior_context")
