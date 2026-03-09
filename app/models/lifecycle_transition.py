from sqlalchemy import text, DateTime, ForeignKey, Text, Numeric, Enum as SAEnum, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from decimal import Decimal

from app.models.base import Base
from app.models.enums import LifecycleState


class LifecycleTransition(Base):
    __tablename__ = "lifecycle_transitions"

    __table_args__ = (
        CheckConstraint(
            "confidence_at_transition BETWEEN 0 AND 1",
            name="confidence",
        ),
        Index("ix_lifecycle_transitions_commitment_id", "commitment_id"),
        Index("ix_lifecycle_transitions_user_id", "user_id"),
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
    )
    from_state: Mapped[LifecycleState | None] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state", create_type=False),
        nullable=True,  # NULL for initial creation
    )
    to_state: Mapped[LifecycleState] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state", create_type=False),
        nullable=False,
    )
    trigger_source_item_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("source_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_at_transition: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    commitment = relationship("Commitment", back_populates="lifecycle_transitions")
    user = relationship("User", back_populates="lifecycle_transitions")
    trigger_source_item = relationship(
        "SourceItem",
        foreign_keys=[trigger_source_item_id],
        back_populates="lifecycle_transitions",
    )
