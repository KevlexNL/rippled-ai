"""D4 — User feedback table + threshold_adjustments on user_commitment_profiles.

Phase D4 — User Feedback Loops for Adaptive Thresholds.
Creates user_feedback table for lightweight frontend actions (dismiss/confirm/correct).
Adds threshold_adjustments JSONB to user_commitment_profiles for per-user adaptation.

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "w7x8y9z0a1b2"
down_revision = "v6w7x8y9z0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commitment_id", UUID(as_uuid=False), sa.ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("field_changed", sa.Text, nullable=True),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=True),
        sa.Column("source_type", sa.Text, nullable=True),
        sa.Column("trigger_class", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"])
    op.create_index("ix_user_feedback_created_at", "user_feedback", ["created_at"])

    op.add_column(
        "user_commitment_profiles",
        sa.Column("threshold_adjustments", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_commitment_profiles", "threshold_adjustments")
    op.drop_index("ix_user_feedback_created_at", table_name="user_feedback")
    op.drop_index("ix_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")
