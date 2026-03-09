from sqlalchemy import (
    text, DateTime, ForeignKey, Text, Numeric,
    Enum as SAEnum, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from decimal import Decimal

from app.models.base import Base
from app.models.enums import SignalRole

signal_role_enum = SAEnum(
    SignalRole,
    name="signal_role",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)


class CommitmentSignal(Base):
    __tablename__ = "commitment_signals"

    __table_args__ = (
        UniqueConstraint(
            "commitment_id", "source_item_id", "signal_role",
            name="uq_commitment_signals_commitment_item_role",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_commitment_signals_confidence"),
        Index("ix_commitment_signals_commitment_id", "commitment_id"),
        Index("ix_commitment_signals_source_item_id", "source_item_id"),
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
    source_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("source_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    signal_role: Mapped[SignalRole] = mapped_column(signal_role_enum, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    interpretation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    commitment = relationship("Commitment", back_populates="signals")
    source_item = relationship("SourceItem", back_populates="commitment_signals")
