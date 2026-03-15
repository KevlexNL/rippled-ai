"""phase_c6_events_user_id

Add user_id column to events table to scope events per user.
Required fix: GET /events was returning all users' events (C3 bug).

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id as nullable (backward-compatible with existing rows)
    op.add_column(
        'events',
        sa.Column(
            'user_id',
            UUID(as_uuid=False),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=True,
        ),
    )
    op.create_index('ix_events_user_id', 'events', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_events_user_id', 'events')
    op.drop_column('events', 'user_id')
