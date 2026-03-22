from sqlalchemy import text, DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.models.base import Base


class NormalizationRunModel(Base):
    """Audit record for each normalization pass."""
    __tablename__ = "normalization_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    normalized_signal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("normalized_signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    normalization_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    warnings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    normalized_signal = relationship("NormalizedSignalModel", back_populates="normalization_runs")
