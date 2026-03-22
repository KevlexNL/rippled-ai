"""Add requester and beneficiary fields to commitments table.

Adds requester_name, requester_email, beneficiary_name, beneficiary_email,
requester_resolved, beneficiary_resolved columns (all nullable).
Backfills requester_name from counterparty_name for existing records.

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commitments", sa.Column("requester_name", sa.String(255), nullable=True))
    op.add_column("commitments", sa.Column("requester_email", sa.String(255), nullable=True))
    op.add_column("commitments", sa.Column("beneficiary_name", sa.String(255), nullable=True))
    op.add_column("commitments", sa.Column("beneficiary_email", sa.String(255), nullable=True))
    op.add_column("commitments", sa.Column("requester_resolved", sa.String(255), nullable=True))
    op.add_column("commitments", sa.Column("beneficiary_resolved", sa.String(255), nullable=True))

    # Backfill: set requester_name = counterparty_name as starting point
    op.execute(
        "UPDATE commitments SET requester_name = counterparty_name "
        "WHERE counterparty_name IS NOT NULL AND requester_name IS NULL"
    )


def downgrade() -> None:
    op.drop_column("commitments", "beneficiary_resolved")
    op.drop_column("commitments", "requester_resolved")
    op.drop_column("commitments", "beneficiary_email")
    op.drop_column("commitments", "beneficiary_name")
    op.drop_column("commitments", "requester_email")
    op.drop_column("commitments", "requester_name")
