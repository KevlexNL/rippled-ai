"""Pydantic schemas for inbound email payloads."""
from datetime import datetime
from pydantic import BaseModel, Field


class SendGridInboundEmail(BaseModel):
    """SendGrid Inbound Parse webhook payload fields."""
    headers: str = ""
    to: str = ""
    from_: str = Field("", alias="from")
    subject: str = ""
    text: str = ""
    html: str = ""
    envelope: str = ""
    charsets: str = ""
    dkim: str = ""
    SPF: str = ""
    spam_score: str = ""
    spam_report: str = ""
    sender_ip: str = ""
    # attachment count
    attachments: str = "0"
    attachment_info: str = ""

    model_config = {"populate_by_name": True}


class RawEmailPayload(BaseModel):
    """Generic normalised email payload — used for IMAP-fetched emails and generic webhooks."""
    message_id: str
    in_reply_to: str | None = None
    references: str | None = None
    from_name: str | None = None
    from_email: str
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str = ""
    body_plain: str = ""
    body_html: str = ""
    date: datetime
    direction: str = "inbound"  # "inbound" | "outbound"
    has_attachment: bool = False
    attachment_metadata: list[dict] | None = None
    source_url: str | None = None
    raw_headers: dict | None = None
