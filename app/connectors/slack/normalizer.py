"""Normalise Slack Events API payloads to SourceItemCreate + NormalizedSignal."""
import re
from datetime import datetime, timezone

from app.connectors.shared.normalized_signal import NormalizedSignal, Participant
from app.models.schemas import SourceItemCreate

# Match Slack @mentions: <@U123ABC>
_MENTION_RE = re.compile(r"<@(U[A-Z0-9]+)>")


def normalise_slack_event(
    event: dict,
    source_id: str,
    slack_user_id: str = "",
) -> tuple[SourceItemCreate | None, NormalizedSignal | None]:
    """Translate a Slack event payload into a SourceItemCreate and NormalizedSignal.

    Args:
        event: Slack event dict from Events API payload.
        source_id: UUID of the Source record this event belongs to.
        slack_user_id: The workspace user ID of the account owner (used for
            future filtering; pass empty string if not applicable).

    Returns (None, None) if the event should be filtered (bot message, unsupported type, etc.).
    """
    event_type = event.get("type")

    # Only handle message events
    if event_type not in ("message", "message_changed"):
        return None, None

    # Per Q3: ignore message_changed events for MVP
    if event_type == "message_changed":
        return None, None

    # Filter bot messages
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return None, None

    # Filter unsupported subtypes (except file_share and message_replied which we process)
    subtype = event.get("subtype")
    if subtype and subtype not in ("file_share", "message_replied", None):
        return None, None

    ts = event.get("ts")
    if not ts:
        return None, None

    thread_ts = event.get("thread_ts") or ts
    channel = event.get("channel", "")
    text = event.get("text") or ""

    # Sender
    user_id = event.get("user") or ""
    user_profile = event.get("user_profile") or {}
    sender_name = (
        user_profile.get("display_name")
        or user_profile.get("real_name")
        or user_id
        or None
    )

    # Attachments / files
    files = event.get("files") or []
    has_attachment = bool(files)
    attachment_metadata = None
    if files:
        attachment_metadata = {
            "files": [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "mimetype": f.get("mimetype"),
                    "size": f.get("size"),
                }
                for f in files
            ]
        }

    # Permalink / source_url
    source_url = event.get("permalink") or _build_slack_url(channel, ts)

    # occurred_at from ts (Unix timestamp with decimal precision)
    try:
        occurred_at = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (ValueError, TypeError):
        occurred_at = datetime.now(timezone.utc)

    item = SourceItemCreate(
        source_id=source_id,
        source_type="slack",
        external_id=ts,
        thread_id=thread_ts,
        direction=None,
        sender_id=user_id or None,
        sender_name=sender_name,
        sender_email=None,
        is_external_participant=False,  # workspace messages are internal; Connect channels handled separately
        content=text or None,
        content_normalized=text.lower().strip() if text else None,
        has_attachment=has_attachment,
        attachment_metadata=attachment_metadata,
        recipients=None,
        source_url=source_url,
        occurred_at=occurred_at,
        metadata_={
            "channel": channel,
            "subtype": subtype,
            "team": event.get("team"),
        },
        is_quoted_content=False,
    )

    # Build NormalizedSignal
    actor = Participant(name=sender_name, role="sender")

    # Extract @mentions as addressed participants
    mentioned_ids = _MENTION_RE.findall(text)
    addressed = [Participant(name=uid, role="mentioned") for uid in mentioned_ids]

    # Prior context: parent message text if this is a thread reply
    parent_text = event.get("parent_message", {}).get("text") if event.get("thread_ts") else None

    # Attachment dicts for signal
    sig_attachments = []
    if files:
        sig_attachments = [
            {"id": f.get("id"), "name": f.get("name"), "mimetype": f.get("mimetype"), "size": f.get("size")}
            for f in files
        ]

    signal = NormalizedSignal(
        signal_id=ts,
        source_type="slack",
        source_thread_id=thread_ts if event.get("thread_ts") else None,
        source_message_id=ts,
        occurred_at=occurred_at,
        authored_at=occurred_at,
        actor_participants=[actor],
        addressed_participants=addressed,
        visible_participants=[actor] + addressed,
        latest_authored_text=text,
        prior_context_text=parent_text,
        attachments=sig_attachments,
        metadata={"channel": channel, "team": event.get("team")},
    )

    return item, signal


def _build_slack_url(channel: str, ts: str) -> str | None:
    """Build a Slack message URL from channel and timestamp."""
    if not channel or not ts:
        return None
    # Convert ts "1234567890.123456" to "1234567890123456" (remove decimal)
    ts_clean = ts.replace(".", "")
    return f"https://slack.com/archives/{channel}/p{ts_clean}"
