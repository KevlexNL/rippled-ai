from sqlalchemy import text, DateTime, ForeignKey, Text, Boolean, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base
from app.models.enums import AmbiguityType

ambiguity_type_enum = SAEnum(
    AmbiguityType,
    name="ambiguity_type",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)


class CommitmentAmbiguity(Base):
    __tablename__ = "commitment_ambiguities"

    __table_args__ = (
        Index("ix_commitment_ambiguities_commitment_id", "commitment_id"),
        Index("ix_commitment_ambiguities_is_resolved", "is_resolved"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    commitment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("commitments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    ambiguity_type: Mapped[AmbiguityType] = mapped_column(ambiguity_type_enum, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    resolved_by_signal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("source_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    commitment = relationship("Commitment", back_populates="ambiguities")
    user = relationship("User", back_populates="commitment_ambiguities")
    resolved_by_signal = relationship(
        "SourceItem",
        foreign_keys=[resolved_by_signal_id],
    )
