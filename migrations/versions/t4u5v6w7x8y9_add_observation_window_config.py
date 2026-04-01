"""Add observation_window_config JSONB column to user_settings.

Phase D1 — User-Configurable Observation Windows.
Stores per-source-type observation window overrides as a JSONB dict.
NULL = use system defaults (no data migration needed).

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("observation_window_config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "observation_window_config")
