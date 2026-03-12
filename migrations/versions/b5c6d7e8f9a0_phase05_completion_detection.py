"""phase05_completion_detection

Add delivered_at and auto_close_after_hours columns to commitments table.
Supports Phase 05 — Completion Detection pipeline.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'commitments',
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column(
            'auto_close_after_hours',
            sa.Integer(),
            nullable=False,
            server_default='48',
        ),
    )
    op.create_index(
        'ix_commitments_state_delivered_at',
        'commitments',
        ['lifecycle_state', 'delivered_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_commitments_state_delivered_at', table_name='commitments')
    op.drop_column('commitments', 'auto_close_after_hours')
    op.drop_column('commitments', 'delivered_at')
