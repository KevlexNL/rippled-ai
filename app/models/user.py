from sqlalchemy import text, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
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
    sources = relationship("Source", back_populates="user", cascade="all, delete-orphan")
    source_items = relationship("SourceItem", back_populates="user", cascade="all, delete-orphan")
    commitments = relationship("Commitment", back_populates="user", cascade="all, delete-orphan")
    commitment_candidates = relationship(
        "CommitmentCandidate", back_populates="user", cascade="all, delete-orphan"
    )
    commitment_ambiguities = relationship(
        "CommitmentAmbiguity", back_populates="user", cascade="all, delete-orphan"
    )
    lifecycle_transitions = relationship(
        "LifecycleTransition", back_populates="user", cascade="all, delete-orphan"
    )
