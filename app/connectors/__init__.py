"""Source connectors — normalisation layer for email, Slack, and meeting sources."""

from app.connectors.email.normalizer import normalise_email
from app.connectors.slack.normalizer import normalise_slack_event
from app.connectors.meeting.normalizer import normalise_meeting_transcript

__all__ = ["normalise_email", "normalise_slack_event", "normalise_meeting_transcript"]
