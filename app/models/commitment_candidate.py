from sqlalchemy import text, DateTime, Boolean, ForeignKey, Text, Numeric, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from decimal import Decimal

from app.models.base import Base


class CommitmentCandidate(Base):
    __tablename__ = "commitment_candidates"

    __table_args__ = (
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence"),
        Index("ix_commitment_candidates_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    originating_item_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("source_items.id", ondelete="SET NULL"),
        nullable=True,  # NULLABLE ONLY for FK SET NULL on source_item deletion.
        # Application rule: never INSERT with null — use CommitmentCandidateCreate which requires this field.
        # A null value in production means the originating source_item was deleted (rare/admin operation only).
        index=True,
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    was_promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    was_discarded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    # Relationships
    user = relationship("User", back_populates="commitment_candidates")
    originating_item = relationship(
        "SourceItem",
        foreign_keys=[originating_item_id],
        back_populates="commitment_candidates",
    )
    candidate_commitments = relationship(
        "CandidateCommitment",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
