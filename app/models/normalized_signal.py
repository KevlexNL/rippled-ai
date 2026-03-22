from sqlalchemy import (
    text, Boolean, DateTime, Integer, String, Text,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.models.base import Base
from app.models.enums import Direction, SourceType

source_type_enum = SAEnum(
    SourceType,
    name="source_type",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)

direction_enum = SAEnum(
    Direction,
    name="direction",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)


class NormalizedSignalModel(Base):
    """Canonical normalized signal derived from RawSignalIngest."""
    __tablename__ = "normalized_signals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    raw_signal_ingest_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("raw_signal_ingests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(source_type_enum, nullable=False)
    source_subtype: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    signal_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    direction: Mapped[Direction | None] = mapped_column(direction_enum, nullable=True)
    is_inbound: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_outbound: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_authored_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    prior_context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_present: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    text_present: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sender_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    to_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cc_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bcc_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    reply_to_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    participants_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    attachment_metadata_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    thread_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_index_guess: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    normalization_version: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'v1'")
    )
    normalization_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    normalization_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    raw_signal_ingest = relationship("RawSignalIngest", back_populates="normalized_signals")
    normalization_runs = relationship(
        "NormalizationRunModel", back_populates="normalized_signal", cascade="all, delete-orphan"
    )
