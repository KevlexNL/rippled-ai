"""phase_c2_daily_digest

Create user_settings and digest_log tables.
Supports Phase C2 — Daily Digest.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e9f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_settings — one row per user, stores digest preferences
    op.create_table(
        'user_settings',
        sa.Column('user_id', UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('digest_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('digest_time', sa.String(5), server_default='08:00', nullable=False),
        sa.Column('last_digest_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # digest_log — audit trail for every digest attempt
    op.create_table(
        'digest_log',
        sa.Column('id', UUID(as_uuid=False), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('commitment_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('delivery_method', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('digest_content', JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('digest_log')
    op.drop_table('user_settings')
