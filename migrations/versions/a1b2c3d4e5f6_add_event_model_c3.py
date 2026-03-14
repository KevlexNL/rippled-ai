"""add_event_model_c3

Event model, CommitmentEventLink, new Commitment columns, new UserSettings columns.
Supports Phase C3 — Event Model + Calendar Integration.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # events — first-class calendar events (explicit from Google or implicit from deadlines)
    op.create_table(
        'events',
        sa.Column('id', UUID(as_uuid=False), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_id', UUID(as_uuid=False), sa.ForeignKey('sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('recurrence_rule', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(20), nullable=False, server_default='explicit'),
        sa.Column('status', sa.String(20), nullable=False, server_default='confirmed'),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rescheduled_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('attendees', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_events_starts_at', 'events', ['starts_at'])
    op.create_index('ix_events_external_id', 'events', ['external_id'])
    op.create_index('ix_events_status', 'events', ['status'])

    # commitment_event_links — many-to-many between commitments and events
    op.create_table(
        'commitment_event_links',
        sa.Column('id', UUID(as_uuid=False), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('commitment_id', UUID(as_uuid=False), sa.ForeignKey('commitments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', UUID(as_uuid=False), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Numeric(4, 3), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('commitment_id', 'event_id', 'relationship', name='uq_commitment_event_relationship'),
    )
    op.create_index('ix_cel_commitment_id', 'commitment_event_links', ['commitment_id'])
    op.create_index('ix_cel_event_id', 'commitment_event_links', ['event_id'])

    # New columns on commitments
    op.add_column('commitments', sa.Column('delivery_state', sa.String(30), nullable=True))
    op.add_column('commitments', sa.Column('counterparty_type', sa.String(20), nullable=True))
    op.add_column('commitments', sa.Column('counterparty_email', sa.Text(), nullable=True))
    op.add_column('commitments', sa.Column('post_event_reviewed', sa.Boolean(), server_default='false', nullable=False))

    # New columns on user_settings (Google OAuth tokens, Fernet-encrypted)
    op.add_column('user_settings', sa.Column('google_access_token', sa.Text(), nullable=True))
    op.add_column('user_settings', sa.Column('google_refresh_token', sa.Text(), nullable=True))
    op.add_column('user_settings', sa.Column('google_token_expiry', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove UserSettings columns
    op.drop_column('user_settings', 'google_token_expiry')
    op.drop_column('user_settings', 'google_refresh_token')
    op.drop_column('user_settings', 'google_access_token')

    # Remove Commitment columns
    op.drop_column('commitments', 'post_event_reviewed')
    op.drop_column('commitments', 'counterparty_email')
    op.drop_column('commitments', 'counterparty_type')
    op.drop_column('commitments', 'delivery_state')

    # Drop tables (order: FK-dependent first)
    op.drop_index('ix_cel_event_id', 'commitment_event_links')
    op.drop_index('ix_cel_commitment_id', 'commitment_event_links')
    op.drop_table('commitment_event_links')

    op.drop_index('ix_events_status', 'events')
    op.drop_index('ix_events_external_id', 'events')
    op.drop_index('ix_events_starts_at', 'events')
    op.drop_table('events')
