"""Add auto_close_config JSONB column to user_settings.

Phase D2 — User-Configurable Auto-Close Timing.
Stores per-user auto-close timing overrides as a JSONB dict.
NULL = use system defaults (no data migration needed).

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-04-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("auto_close_config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "auto_close_config")
