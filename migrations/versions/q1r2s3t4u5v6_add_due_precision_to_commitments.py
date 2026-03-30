"""Add due_precision enum field to commitments table.

Adds a 'due_precision' column (due_precision enum: day, week, month, vague)
to the commitments table. Backfills existing rows:
  - resolved_deadline IS NOT NULL → 'day' (exact deadline was parsed)
  - vague_time_phrase IS NOT NULL AND resolved_deadline IS NULL → 'vague'
  - otherwise → NULL (no timing info available)

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, None] = "p0q1r2s3t4u5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DUE_PRECISION_VALUES = ('day', 'week', 'month', 'vague')


def upgrade() -> None:
    # Create the PostgreSQL enum type
    op.execute(
        "CREATE TYPE due_precision AS ENUM ('day', 'week', 'month', 'vague')"
    )

    # Add the column (nullable, no default — backfill below)
    op.add_column(
        "commitments",
        sa.Column(
            "due_precision",
            sa.Enum(*_DUE_PRECISION_VALUES, name="due_precision", create_type=False),
            nullable=True,
        ),
    )

    # Backfill: exact deadline parsed → 'day'
    op.execute(
        """
        UPDATE commitments
        SET due_precision = 'day'
        WHERE resolved_deadline IS NOT NULL
          AND due_precision IS NULL
        """
    )

    # Backfill: vague phrase present but no resolved deadline → 'vague'
    op.execute(
        """
        UPDATE commitments
        SET due_precision = 'vague'
        WHERE vague_time_phrase IS NOT NULL
          AND resolved_deadline IS NULL
          AND due_precision IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("commitments", "due_precision")
    op.execute("DROP TYPE IF EXISTS due_precision")
