"""Clarification model — Phase 04.

Stores the analysis result and surface recommendation for a commitment
candidate at the point it is evaluated (and optionally promoted).
"""
from datetime import datetime

from sqlalchemy import (
    text,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Clarification(Base):
    __tablename__ = "clarifications"

    __table_args__ = (
        Index("ix_clarifications_commitment_id", "commitment_id"),
        Index("ix_clarifications_surface_recommendation", "surface_recommendation"),
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
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id"),
        nullable=True,  # Populated at promotion; null before candidate is promoted
    )
    issue_types: Mapped[list] = mapped_column(
        ARRAY(Text()),
        nullable=False,
    )
    issue_severity: Mapped[str] = mapped_column(String, nullable=False)
    why_this_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    observation_window_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'open'"),
    )
    suggested_values: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
    )
    supporting_evidence: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
    )
    suggested_clarification_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    surface_recommendation: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'do_nothing'"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    # Relationships — no back_populates on Commitment/User to avoid modifying Phase 01/02 models
    commitment = relationship("Commitment", foreign_keys=[commitment_id])
    user = relationship("User", foreign_keys=[user_id])
