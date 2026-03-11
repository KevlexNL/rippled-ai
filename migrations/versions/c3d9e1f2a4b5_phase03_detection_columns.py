"""phase03_detection_columns

Add detection-specific columns to commitment_candidates table:
  - trigger_class: detection category (explicit_self_commitment, etc.)
  - is_explicit: explicit vs implicit signal
  - priority_hint: high / medium / low
  - commitment_class_hint: big_promise / small_commitment / unknown
  - context_window: surrounding text, speaker turns, thread context (JSONB)
  - linked_entities: people, dates, deliverables detected (JSONB)
  - observe_until: when observation window closes
  - flag_reanalysis: transcript quality flag
  - source_type: denormalized for query efficiency

Also adds CHECK constraint on confidence_score (0–1 range, parity with commitments table).
Also adds composite index (user_id, was_promoted) for detection pipeline queries.

Revision ID: c3d9e1f2a4b5
Revises: 23ab33b28525
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d9e1f2a4b5'
down_revision: Union[str, Sequence[str], None] = '23ab33b28525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 03 detection columns to commitment_candidates."""

    # -------------------------------------------------------------------------
    # New columns for detection metadata
    # -------------------------------------------------------------------------
    op.add_column(
        'commitment_candidates',
        sa.Column('trigger_class', sa.Text(), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('is_explicit', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column(
            'priority_hint',
            sa.Text(),
            sa.CheckConstraint(
                "priority_hint IN ('high', 'medium', 'low')",
                name=op.f('ck_commitment_candidates_priority_hint'),
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column(
            'commitment_class_hint',
            sa.Text(),
            sa.CheckConstraint(
                "commitment_class_hint IN ('big_promise', 'small_commitment', 'unknown')",
                name=op.f('ck_commitment_candidates_commitment_class_hint'),
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('context_window', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('linked_entities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('observe_until', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('flag_reanalysis', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('source_type', sa.Text(), nullable=True),
    )

    # -------------------------------------------------------------------------
    # CHECK constraint on confidence_score (0–1 range, parity with commitments)
    # -------------------------------------------------------------------------
    op.create_check_constraint(
        op.f('ck_commitment_candidates_confidence'),
        'commitment_candidates',
        'confidence_score BETWEEN 0 AND 1',
    )

    # -------------------------------------------------------------------------
    # Composite index for detection pipeline queries
    # -------------------------------------------------------------------------
    op.create_index(
        'ix_commitment_candidates_user_promoted',
        'commitment_candidates',
        ['user_id', 'was_promoted'],
        postgresql_where=sa.text('was_promoted = true'),
    )

    # -------------------------------------------------------------------------
    # Index on source_type for grouping/filtering candidates by source
    # -------------------------------------------------------------------------
    op.create_index(
        'ix_commitment_candidates_source_type',
        'commitment_candidates',
        ['source_type'],
    )


def downgrade() -> None:
    """Remove Phase 03 detection columns from commitment_candidates."""

    op.drop_index('ix_commitment_candidates_source_type', table_name='commitment_candidates')
    op.drop_index('ix_commitment_candidates_user_promoted', table_name='commitment_candidates')
    op.drop_constraint(
        op.f('ck_commitment_candidates_confidence'),
        'commitment_candidates',
        type_='check',
    )
    op.drop_column('commitment_candidates', 'source_type')
    op.drop_column('commitment_candidates', 'flag_reanalysis')
    op.drop_column('commitment_candidates', 'observe_until')
    op.drop_column('commitment_candidates', 'linked_entities')
    op.drop_column('commitment_candidates', 'context_window')
    op.drop_column('commitment_candidates', 'commitment_class_hint')
    op.drop_column('commitment_candidates', 'priority_hint')
    op.drop_column('commitment_candidates', 'is_explicit')
    op.drop_column('commitment_candidates', 'trigger_class')
