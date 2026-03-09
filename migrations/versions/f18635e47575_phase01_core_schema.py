"""phase01_core_schema

Revision ID: f18635e47575
Revises: 
Create Date: 2026-03-09 16:19:44.159163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f18635e47575'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — Phase 01 core tables."""

    # Create enum types
    source_type_enum = postgresql.ENUM('meeting', 'slack', 'email', name='source_type')
    source_type_enum.create(op.get_bind(), checkfirst=True)

    lifecycle_state_enum = postgresql.ENUM(
        'proposed', 'needs_clarification', 'active', 'delivered', 'closed', 'discarded',
        name='lifecycle_state'
    )
    lifecycle_state_enum.create(op.get_bind(), checkfirst=True)

    signal_role_enum = postgresql.ENUM(
        'origin', 'clarification', 'progress', 'delivery', 'closure', 'conflict', 'reopening',
        name='signal_role'
    )
    signal_role_enum.create(op.get_bind(), checkfirst=True)

    ambiguity_type_enum = postgresql.ENUM(
        'owner_missing', 'owner_vague_collective', 'owner_multiple_candidates', 'owner_conflicting',
        'timing_missing', 'timing_vague', 'timing_conflicting', 'timing_changed', 'timing_inferred_weak',
        'deliverable_unclear', 'target_unclear', 'status_unclear', 'commitment_unclear',
        name='ambiguity_type'
    )
    ambiguity_type_enum.create(op.get_bind(), checkfirst=True)

    ownership_ambiguity_type_enum = postgresql.ENUM(
        'missing', 'vague_collective', 'multiple_candidates', 'conflicting',
        name='ownership_ambiguity_type'
    )
    ownership_ambiguity_type_enum.create(op.get_bind(), checkfirst=True)

    timing_ambiguity_type_enum = postgresql.ENUM(
        'missing', 'vague', 'conflicting', 'changed', 'inferred_weak',
        name='timing_ambiguity_type'
    )
    timing_ambiguity_type_enum.create(op.get_bind(), checkfirst=True)

    deliverable_ambiguity_type_enum = postgresql.ENUM(
        'unclear', 'target_unknown',
        name='deliverable_ambiguity_type'
    )
    deliverable_ambiguity_type_enum.create(op.get_bind(), checkfirst=True)

    commitment_class_enum = postgresql.ENUM(
        'big_promise', 'small_commitment',
        name='commitment_class'
    )
    commitment_class_enum.create(op.get_bind(), checkfirst=True)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    )

    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source_type', source_type_enum, nullable=False),
        sa.Column('provider_account_id', sa.String(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sources_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_sources')),
    )
    op.create_index(op.f('ix_sources_user_id'), 'sources', ['user_id'])

    # Create source_items table
    op.create_table(
        'source_items',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source_type', source_type_enum, nullable=False),
        sa.Column('external_id', sa.String(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=True),
        sa.Column('direction', sa.String(), nullable=True),
        sa.Column('sender_id', sa.String(), nullable=True),
        sa.Column('sender_name', sa.String(), nullable=True),
        sa.Column('sender_email', sa.String(), nullable=True),
        sa.Column('is_external_participant', sa.Boolean(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_normalized', sa.Text(), nullable=True),
        sa.Column('has_attachment', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('attachment_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recipients', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_quoted_content', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_source_items_source_id_sources'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_source_items_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_source_items')),
        sa.UniqueConstraint('source_id', 'external_id', name=op.f('uq_source_items_source_external')),
    )
    op.create_index(op.f('ix_source_items_user_id'), 'source_items', ['user_id'])
    op.create_index(op.f('ix_source_items_thread_id'), 'source_items', ['thread_id'])
    op.create_index(op.f('ix_source_items_occurred_at'), 'source_items', ['occurred_at'])
    op.create_index(op.f('ix_source_items_source_id'), 'source_items', ['source_id'])

    # Create commitments table
    op.create_table(
        'commitments',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('commitment_text', sa.Text(), nullable=True),
        sa.Column('commitment_type', sa.String(), nullable=True),
        sa.Column('priority_class', commitment_class_enum, nullable=True),
        sa.Column('context_type', sa.String(), nullable=True),
        sa.Column('owner_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolved_owner', sa.String(), nullable=True),
        sa.Column('suggested_owner', sa.String(), nullable=True),
        sa.Column('ownership_ambiguity', ownership_ambiguity_type_enum, nullable=True),
        sa.Column('deadline_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolved_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('vague_time_phrase', sa.String(), nullable=True),
        sa.Column('suggested_due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timing_ambiguity', timing_ambiguity_type_enum, nullable=True),
        sa.Column('deliverable', sa.Text(), nullable=True),
        sa.Column('target_entity', sa.String(), nullable=True),
        sa.Column('suggested_next_step', sa.Text(), nullable=True),
        sa.Column('deliverable_ambiguity', deliverable_ambiguity_type_enum, nullable=True),
        sa.Column('lifecycle_state', lifecycle_state_enum, server_default=sa.text("'proposed'"), nullable=False),
        sa.Column('state_changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('confidence_commitment', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_owner', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_deadline', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_delivery', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_closure', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_actionability', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('commitment_explanation', sa.Text(), nullable=True),
        sa.Column('missing_pieces_explanation', sa.Text(), nullable=True),
        sa.Column('delivery_explanation', sa.Text(), nullable=True),
        sa.Column('closure_explanation', sa.Text(), nullable=True),
        sa.Column('observe_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observation_window_hours', sa.Numeric(), nullable=True),
        sa.Column('is_surfaced', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('surfaced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence_commitment BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_commitment')),
        sa.CheckConstraint('confidence_owner BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_owner')),
        sa.CheckConstraint('confidence_deadline BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_deadline')),
        sa.CheckConstraint('confidence_delivery BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_delivery')),
        sa.CheckConstraint('confidence_closure BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_closure')),
        sa.CheckConstraint('confidence_actionability BETWEEN 0 AND 1', name=op.f('ck_commitments_conf_actionability')),
        sa.CheckConstraint("context_type IN ('internal', 'external', 'mixed')", name=op.f('ck_commitments_context_type')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_commitments_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commitments')),
    )
    op.create_index(op.f('ix_commitments_user_id'), 'commitments', ['user_id'])
    op.create_index(op.f('ix_commitments_lifecycle_state'), 'commitments', ['lifecycle_state'])
    op.create_index(op.f('ix_commitments_is_surfaced'), 'commitments', ['is_surfaced'])
    op.create_index(op.f('ix_commitments_confidence_actionability'), 'commitments', ['confidence_actionability'])

    # Create commitment_candidates table
    op.create_table(
        'commitment_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('originating_item_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('detection_explanation', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('was_promoted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('was_discarded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('discard_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1', name=op.f('ck_commitment_candidates_confidence')),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id'], name=op.f('fk_commitment_candidates_commitment_id_commitments'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['originating_item_id'], ['source_items.id'], name=op.f('fk_commitment_candidates_originating_item_id_source_items'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_commitment_candidates_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commitment_candidates')),
    )
    op.create_index(op.f('ix_commitment_candidates_user_id'), 'commitment_candidates', ['user_id'])
    op.create_index(op.f('ix_commitment_candidates_commitment_id'), 'commitment_candidates', ['commitment_id'])
    op.create_index(op.f('ix_commitment_candidates_originating_item_id'), 'commitment_candidates', ['originating_item_id'])

    # Create commitment_signals table
    op.create_table(
        'commitment_signals',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source_item_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('signal_role', signal_role_enum, nullable=False),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('interpretation_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence BETWEEN 0 AND 1', name=op.f('ck_commitment_signals_confidence')),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id'], name=op.f('fk_commitment_signals_commitment_id_commitments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_item_id'], ['source_items.id'], name=op.f('fk_commitment_signals_source_item_id_source_items'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_commitment_signals_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commitment_signals')),
        sa.UniqueConstraint('commitment_id', 'source_item_id', 'signal_role', name=op.f('uq_commitment_signals_commitment_item_role')),
    )
    op.create_index(op.f('ix_commitment_signals_commitment_id'), 'commitment_signals', ['commitment_id'])
    op.create_index(op.f('ix_commitment_signals_source_item_id'), 'commitment_signals', ['source_item_id'])
    op.create_index(op.f('ix_commitment_signals_user_id'), 'commitment_signals', ['user_id'])

    # Create commitment_ambiguities table
    op.create_table(
        'commitment_ambiguities',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('ambiguity_type', ambiguity_type_enum, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('resolved_by_signal_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id'], name=op.f('fk_commitment_ambiguities_commitment_id_commitments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by_signal_id'], ['source_items.id'], name=op.f('fk_commitment_ambiguities_resolved_by_signal_id_source_items'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_commitment_ambiguities_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commitment_ambiguities')),
    )
    op.create_index(op.f('ix_commitment_ambiguities_commitment_id'), 'commitment_ambiguities', ['commitment_id'])
    op.create_index(op.f('ix_commitment_ambiguities_user_id'), 'commitment_ambiguities', ['user_id'])
    op.create_index(op.f('ix_commitment_ambiguities_is_resolved'), 'commitment_ambiguities', ['is_resolved'])

    # Create lifecycle_transitions table
    op.create_table(
        'lifecycle_transitions',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('from_state', lifecycle_state_enum, nullable=True),
        sa.Column('to_state', lifecycle_state_enum, nullable=False),
        sa.Column('trigger_source_item_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('trigger_reason', sa.Text(), nullable=True),
        sa.Column('confidence_at_transition', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence_at_transition BETWEEN 0 AND 1', name=op.f('ck_lifecycle_transitions_confidence')),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id'], name=op.f('fk_lifecycle_transitions_commitment_id_commitments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trigger_source_item_id'], ['source_items.id'], name=op.f('fk_lifecycle_transitions_trigger_source_item_id_source_items'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_lifecycle_transitions_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lifecycle_transitions')),
    )
    op.create_index(op.f('ix_lifecycle_transitions_commitment_id'), 'lifecycle_transitions', ['commitment_id'])
    op.create_index(op.f('ix_lifecycle_transitions_user_id'), 'lifecycle_transitions', ['user_id'])
    op.create_index(op.f('ix_lifecycle_transitions_trigger_source_item_id'), 'lifecycle_transitions', ['trigger_source_item_id'])


def downgrade() -> None:
    """Downgrade schema — drop Phase 01 tables and enums."""
    # Drop tables in reverse dependency order
    op.drop_table('lifecycle_transitions')
    op.drop_table('commitment_ambiguities')
    op.drop_table('commitment_signals')
    op.drop_table('commitment_candidates')
    op.drop_table('commitments')
    op.drop_table('source_items')
    op.drop_table('sources')
    op.drop_table('users')

    # Drop enum types
    postgresql.ENUM(name='lifecycle_state').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='source_type').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='signal_role').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='ambiguity_type').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='ownership_ambiguity_type').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='timing_ambiguity_type').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='deliverable_ambiguity_type').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='commitment_class').drop(op.get_bind(), checkfirst=True)
