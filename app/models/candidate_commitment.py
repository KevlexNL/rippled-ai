"""Join table: one candidate → many commitments, many candidates → one commitment."""

from sqlalchemy import text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base


class CandidateCommitment(Base):
    """N:M join between commitment_candidates and commitments.

    One candidate can spawn multiple commitments (e.g. one email with two topics).
    Multiple candidates can merge into one commitment.

    Set was_promoted = True on the parent CommitmentCandidate when any row is
    created here for that candidate.
    """

    __tablename__ = "candidate_commitments"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "commitment_id",
            name="uq_candidate_commitments_candidate_commitment",
        ),
        Index("ix_candidate_commitments_candidate_id", "candidate_id"),
        Index("ix_candidate_commitments_commitment_id", "commitment_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    candidate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("commitment_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    commitment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("commitments.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    candidate = relationship("CommitmentCandidate", back_populates="candidate_commitments")
    commitment = relationship("Commitment", back_populates="candidate_commitments")
