"""context_layer

Add commitment_contexts table and context_id FK on commitments.
Supports WO-RIPPLED-CONTEXT-LAYER.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'commitment_contexts',
        sa.Column('id', UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.add_column(
        'commitments',
        sa.Column('context_id', UUID(as_uuid=False), sa.ForeignKey('commitment_contexts.id', ondelete='SET NULL'), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column('commitments', 'context_id')
    op.drop_table('commitment_contexts')
