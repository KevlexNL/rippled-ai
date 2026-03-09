from sqlalchemy import (
    text, DateTime, String, Boolean, ForeignKey, Text,
    Integer, Numeric, Enum as SAEnum, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from decimal import Decimal

from app.models.base import Base
from app.models.enums import (
    LifecycleState,
    CommitmentClass,
    CommitmentType,
    OwnershipAmbiguityType,
    TimingAmbiguityType,
    DeliverableAmbiguityType,
)

lifecycle_state_enum = SAEnum(
    LifecycleState,
    name="lifecycle_state",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)

commitment_class_enum = SAEnum(
    CommitmentClass,
    name="commitment_class",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)

ownership_ambiguity_enum = SAEnum(
    OwnershipAmbiguityType,
    name="ownership_ambiguity_type",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)

timing_ambiguity_enum = SAEnum(
    TimingAmbiguityType,
    name="timing_ambiguity_type",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)

deliverable_ambiguity_enum = SAEnum(
    DeliverableAmbiguityType,
    name="deliverable_ambiguity_type",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)

commitment_type_enum = SAEnum(
    CommitmentType,
    name="commitment_type_enum",
    create_type=True,
    values_callable=lambda e: [m.value for m in e],
)


class Commitment(Base):
    __tablename__ = "commitments"

    __table_args__ = (
        # Note: naming convention "ck_%(table_name)s_%(constraint_name)s" is applied automatically.
        # Use only the suffix as the name — convention produces the full ck_commitments_<suffix> in DB.
        CheckConstraint("confidence_commitment BETWEEN 0 AND 1", name="conf_commitment"),
        CheckConstraint("confidence_owner BETWEEN 0 AND 1", name="conf_owner"),
        CheckConstraint("confidence_deadline BETWEEN 0 AND 1", name="conf_deadline"),
        CheckConstraint("confidence_delivery BETWEEN 0 AND 1", name="conf_delivery"),
        CheckConstraint("confidence_closure BETWEEN 0 AND 1", name="conf_closure"),
        CheckConstraint("confidence_actionability BETWEEN 0 AND 1", name="conf_actionability"),
        CheckConstraint("context_type IN ('internal', 'external')", name="context_type"),
        Index("ix_commitments_user_id", "user_id"),
        Index("ix_commitments_lifecycle_state", "lifecycle_state"),
        Index("ix_commitments_is_surfaced", "is_surfaced"),
        Index("ix_commitments_confidence_actionability", "confidence_actionability"),
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

    # Identity & versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    # Meaning
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    commitment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    commitment_type: Mapped[CommitmentType | None] = mapped_column(commitment_type_enum, nullable=True)
    priority_class: Mapped[CommitmentClass | None] = mapped_column(commitment_class_enum, nullable=True)
    context_type: Mapped[str | None] = mapped_column(String, nullable=True)

    # Ownership
    owner_candidates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    resolved_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    ownership_ambiguity: Mapped[OwnershipAmbiguityType | None] = mapped_column(
        ownership_ambiguity_enum, nullable=True
    )

    # Timing
    deadline_candidates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    resolved_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vague_time_phrase: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timing_ambiguity: Mapped[TimingAmbiguityType | None] = mapped_column(timing_ambiguity_enum, nullable=True)

    # Deliverable / Next step
    deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_entity: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliverable_ambiguity: Mapped[DeliverableAmbiguityType | None] = mapped_column(
        deliverable_ambiguity_enum, nullable=True
    )

    # Lifecycle
    lifecycle_state: Mapped[LifecycleState] = mapped_column(
        lifecycle_state_enum,
        nullable=False,
        server_default=text("'proposed'"),
    )
    state_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Confidence scores
    confidence_commitment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_owner: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_deadline: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_delivery: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_closure: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_actionability: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Evidence explanations
    commitment_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_pieces_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Observation window
    observe_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_window_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Surfacing
    is_surfaced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
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
    user = relationship("User", back_populates="commitments")
    candidate_commitments = relationship(
        "CandidateCommitment",
        back_populates="commitment",
        cascade="all, delete-orphan",
    )
    signals = relationship(
        "CommitmentSignal", back_populates="commitment", cascade="all, delete-orphan"
    )
    ambiguities = relationship(
        "CommitmentAmbiguity", back_populates="commitment", cascade="all, delete-orphan"
    )
    lifecycle_transitions = relationship(
        "LifecycleTransition", back_populates="commitment", cascade="all, delete-orphan"
    )
