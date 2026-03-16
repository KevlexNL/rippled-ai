"""Seed pass schema: seed_processed_at on source_items + user_commitment_profiles table.

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Track which source_items have been seed-processed (idempotency)
    op.add_column(
        "source_items",
        sa.Column("seed_processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # User commitment profiles — output of seed pass analysis
    op.create_table(
        "user_commitment_profiles",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("trigger_phrases", JSONB, nullable=True),
        sa.Column("high_signal_senders", JSONB, nullable=True),
        sa.Column("domains", JSONB, nullable=True),
        sa.Column("total_items_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_commitments_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_seed_pass_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_user_commitment_profiles_user_id", "user_commitment_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_commitment_profiles_user_id")
    op.drop_table("user_commitment_profiles")
    op.drop_column("source_items", "seed_processed_at")
