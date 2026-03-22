"""Add in_progress, completed, canceled to lifecycle_state enum.

Aligns the lifecycle_state enum with the commitment lifecycle spec.
PostgreSQL ALTER TYPE ADD VALUE is append-only. No backfill needed.

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l6m7n8o9p0q1"
down_revision: Union[str, Sequence[str], None] = "k5l6m7n8o9p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'in_progress'")
    op.execute("ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'completed'")
    op.execute("ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'canceled'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
