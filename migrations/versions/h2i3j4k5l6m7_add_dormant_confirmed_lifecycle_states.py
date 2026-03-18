"""Add dormant and confirmed values to lifecycle_state enum.

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'dormant'")
    op.execute("ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'confirmed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
