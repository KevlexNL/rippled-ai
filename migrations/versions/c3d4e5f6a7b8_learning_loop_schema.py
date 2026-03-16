"""Learning loop schema: detection_audit table + suppressed_senders on user_commitment_profiles.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7, f1a2b3c4d5e6
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "f1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Detection audit — tracks which tier handled each detection
    op.create_table(
        "detection_audit",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source_item_id", UUID(as_uuid=False), sa.ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier_used", sa.String(10), nullable=False),  # tier_1, tier_2, tier_3, pattern
        sa.Column("matched_phrase", sa.Text, nullable=True),
        sa.Column("matched_sender", sa.String(255), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("commitment_created", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_detection_audit_user_id", "detection_audit", ["user_id"])
    op.create_index("ix_detection_audit_tier_used", "detection_audit", ["tier_used"])
    op.create_index("ix_detection_audit_created_at", "detection_audit", ["created_at"])

    # Add suppressed_senders to user_commitment_profiles
    op.add_column(
        "user_commitment_profiles",
        sa.Column("suppressed_senders", JSONB, nullable=True),
    )

    # Add sender_weights JSONB (dict of sender -> weight) for weighted sender matching
    op.add_column(
        "user_commitment_profiles",
        sa.Column("sender_weights", JSONB, nullable=True),
    )

    # Add phrase_weights JSONB (dict of phrase -> weight) for weighted phrase matching
    op.add_column(
        "user_commitment_profiles",
        sa.Column("phrase_weights", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_commitment_profiles", "phrase_weights")
    op.drop_column("user_commitment_profiles", "sender_weights")
    op.drop_column("user_commitment_profiles", "suppressed_senders")
    op.drop_index("ix_detection_audit_created_at")
    op.drop_index("ix_detection_audit_tier_used")
    op.drop_index("ix_detection_audit_user_id")
    op.drop_table("detection_audit")
