"""Shared NormalizedSignal contract — WO-RIPPLED-SIGNAL-INGESTION-NORMALIZATION.

All connectors must produce a NormalizedSignal before hitting the detection
pipeline. This is the canonical Pydantic model used for both in-memory
processing and persistence (via NormalizedSignalORM).
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Direction, NormalizationFlag, ParticipantRole


class NormalizedParticipant(BaseModel):
    """A participant with typed role and primary-user flag."""

    email: str | None = None
    display_name: str | None = None
    role: ParticipantRole = ParticipantRole.unknown
    is_primary_user: bool = False
    confidence: float | None = None


class NormalizedAttachment(BaseModel):
    """Attachment metadata extracted from a signal."""

    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    provider_attachment_id: str | None = None
    is_inline: bool = False
    has_content_fetched: bool = False


# Backward-compatible Participant (used by existing connectors)
class Participant(BaseModel):
    """A person involved in a signal event (legacy compat)."""

    name: str | None = None
    email: str | None = None
    role: str | None = None


class NormalizedSignal(BaseModel):
    """Canonical input contract for the detection and normalization pipeline.

    Every connector normalizes its platform-specific payload into this
    structure before detection runs. Supports both legacy field patterns
    (signal_id, actor_participants) and the new WO-specified fields
    (id, sender, direction, normalization_flags, etc.).
    """

    # --- Legacy fields (backward compatible with existing connectors) ---
    signal_id: str  # maps to source_item.external_id
    source_type: str  # email | slack | meeting
    source_thread_id: str | None = None
    source_message_id: str | None = None
    occurred_at: datetime  # when the event happened
    authored_at: datetime  # when the text was authored
    actor_participants: list[Participant] = Field(default_factory=list)
    addressed_participants: list[Participant] = Field(default_factory=list)
    visible_participants: list[Participant] = Field(default_factory=list)
    latest_authored_text: str = ""
    prior_context_text: str | None = None
    attachments: list[dict] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    # --- New WO fields (set by EmailNormalizationService) ---
    id: str | None = None  # UUID assigned by normalization service
    raw_signal_ingest_id: str | None = None  # FK to RawSignalIngest.id
    source_subtype: str | None = None  # e.g. "reply", "forward"
    provider: str | None = None
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    provider_account_id: str | None = None
    signal_timestamp: datetime | None = None
    direction: Direction | None = None
    is_inbound: bool = False
    is_outbound: bool = False
    subject: str | None = None
    full_visible_text: str | None = None
    html_present: bool = False
    text_present: bool = False
    sender: NormalizedParticipant | None = None
    to: list[NormalizedParticipant] = Field(default_factory=list)
    cc: list[NormalizedParticipant] = Field(default_factory=list)
    bcc: list[NormalizedParticipant] = Field(default_factory=list)
    reply_to: list[NormalizedParticipant] = Field(default_factory=list)
    participants: list[NormalizedParticipant] = Field(default_factory=list)
    attachment_metadata: list[NormalizedAttachment] = Field(default_factory=list)
    thread_position: int | None = None
    message_index_guess: int | None = None
    language_code: str | None = None
    normalization_version: str = "v1"
    normalization_flags: list[NormalizationFlag] = Field(default_factory=list)
    normalization_warnings: list[str] = Field(default_factory=list)
