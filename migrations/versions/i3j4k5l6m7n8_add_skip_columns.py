"""Add skipped_at and skip_reason columns to commitments.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, Sequence[str], None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commitments", sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("commitments", sa.Column("skip_reason", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("commitments", "skip_reason")
    op.drop_column("commitments", "skipped_at")
