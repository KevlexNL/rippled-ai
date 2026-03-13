"""phase06_surfacing

Add surfacing columns to commitments and create surfacing_audit table.
Supports Phase 06 — Surfacing & Prioritization pipeline.

Revision ID: d7e8f9a0b1c2
Revises: b5c6d7e8f9a0
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extend commitments table with Phase 06 surfacing columns ---

    op.add_column(
        'commitments',
        sa.Column('surfaced_as', sa.String(20), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column('priority_score', sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column('timing_strength', sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column('business_consequence', sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column('cognitive_burden', sa.SmallInteger(), nullable=True),
    )
    # Stored on 0-1 scale to match codebase convention (Q3 decision)
    op.add_column(
        'commitments',
        sa.Column('confidence_for_surfacing', sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        'commitments',
        sa.Column('surfacing_reason', sa.String(255), nullable=True),
    )

    # Composite index for efficient surface queries ordered by priority
    op.create_index(
        'ix_commitments_surfaced_as_priority',
        'commitments',
        ['surfaced_as', sa.text('priority_score DESC')],
        postgresql_where=sa.text('surfaced_as IS NOT NULL'),
    )

    # --- Create surfacing_audit table (Q4 decision) ---

    op.create_table(
        'surfacing_audit',
        sa.Column(
            'id',
            sa.BigInteger(),
            sa.Identity(always=False),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'commitment_id',
            sa.String(),
            sa.ForeignKey('commitments.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('old_surfaced_as', sa.String(20), nullable=True),
        sa.Column('new_surfaced_as', sa.String(20), nullable=True),
        sa.Column('priority_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table('surfacing_audit')

    op.drop_index('ix_commitments_surfaced_as_priority', table_name='commitments')

    op.drop_column('commitments', 'surfacing_reason')
    op.drop_column('commitments', 'confidence_for_surfacing')
    op.drop_column('commitments', 'cognitive_burden')
    op.drop_column('commitments', 'business_consequence')
    op.drop_column('commitments', 'timing_strength')
    op.drop_column('commitments', 'priority_score')
    op.drop_column('commitments', 'surfaced_as')
