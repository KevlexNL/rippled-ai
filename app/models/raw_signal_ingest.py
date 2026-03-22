from sqlalchemy import text, DateTime, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.models.base import Base
from app.models.enums import SourceType

source_type_enum = SAEnum(
    SourceType,
    name="source_type",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


class RawSignalIngest(Base):
    """Stores the original provider payload and ingest metadata."""
    __tablename__ = "raw_signal_ingests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_type: Mapped[SourceType] = mapped_column(source_type_enum, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    parse_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    normalized_signals = relationship(
        "NormalizedSignalModel", back_populates="raw_signal_ingest", cascade="all, delete-orphan"
    )
