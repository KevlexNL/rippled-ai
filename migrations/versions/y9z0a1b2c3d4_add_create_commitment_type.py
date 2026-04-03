"""Add 'create' to commitment_type enum.

Brief 10 Type D (create/revise/prepare) is a distinct commitment category
with unique completion detection difficulty — requires artifact signals.

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-04-03
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "y9z0a1b2c3d4"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE commitment_type ADD VALUE IF NOT EXISTS 'create'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # The value will remain but be unused after downgrade.
    pass
