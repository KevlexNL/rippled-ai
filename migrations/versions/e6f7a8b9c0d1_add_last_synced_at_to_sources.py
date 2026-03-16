"""add_last_synced_at_to_sources

Close Alembic gap: sources.last_synced_at was only in manual SQL migration 004.
WO-RIPPLED-SCHEMA-AUDIT.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Column may already exist if manual migration 004 was run.
    # Use raw SQL with IF NOT EXISTS for idempotency.
    op.execute(
        "ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.drop_column("sources", "last_synced_at")
