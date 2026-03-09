from sqlalchemy import (
    text, DateTime, String, Boolean, ForeignKey, Text,
    Enum as SAEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.models.base import Base
from app.models.enums import SourceType


class SourceItem(Base):
    __tablename__ = "source_items"

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_source_items_source_external"),
        Index("ix_source_items_user_id", "user_id"),
        Index("ix_source_items_thread_id", "thread_id"),
        Index("ix_source_items_occurred_at", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type", create_type=False),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String, nullable=True)
    is_external_participant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    attachment_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    is_quoted_content: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Relationships
    source = relationship("Source", back_populates="source_items")
    user = relationship("User", back_populates="source_items")
    commitment_candidates = relationship(
        "CommitmentCandidate",
        foreign_keys="CommitmentCandidate.originating_item_id",
        back_populates="originating_item",
    )
    commitment_signals = relationship("CommitmentSignal", back_populates="source_item")
    lifecycle_transitions = relationship(
        "LifecycleTransition",
        foreign_keys="LifecycleTransition.trigger_source_item_id",
        back_populates="trigger_source_item",
    )
