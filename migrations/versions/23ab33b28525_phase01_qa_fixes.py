"""phase01_qa_fixes

Applies all Phase 01 Q&A-approved schema changes:
  - Drop commitment_candidates.commitment_id FK column (replaced by candidate_commitments join table)
  - Create candidate_commitments N:M join table
  - Tighten commitments.context_type CHECK to ('internal', 'external') — remove 'mixed'
  - Add commitment_type_enum PostgreSQL enum type
  - Alter commitments.commitment_type from TEXT to commitment_type_enum

See: build/phases/01-schema/qa-decisions.md

Revision ID: 23ab33b28525
Revises: f18635e47575
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '23ab33b28525'
down_revision: Union[str, Sequence[str], None] = 'f18635e47575'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Phase 01 Q&A schema fixes."""

    # -------------------------------------------------------------------------
    # Q1: Drop commitment_candidates.commitment_id (replaced by join table)
    # -------------------------------------------------------------------------
    op.drop_index('ix_commitment_candidates_commitment_id', table_name='commitment_candidates')
    op.drop_constraint(
        'fk_commitment_candidates_commitment_id_commitments',
        'commitment_candidates',
        type_='foreignkey',
    )
    op.drop_column('commitment_candidates', 'commitment_id')

    # -------------------------------------------------------------------------
    # Q1: Create candidate_commitments join table
    # -------------------------------------------------------------------------
    op.create_table(
        'candidate_commitments',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=False),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['candidate_id'],
            ['commitment_candidates.id'],
            name=op.f('fk_candidate_commitments_candidate_id_commitment_candidates'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['commitment_id'],
            ['commitments.id'],
            name=op.f('fk_candidate_commitments_commitment_id_commitments'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_candidate_commitments')),
        sa.UniqueConstraint(
            'candidate_id', 'commitment_id',
            name=op.f('uq_candidate_commitments_candidate_id'),
        ),
    )
    op.create_index(
        op.f('ix_candidate_commitments_candidate_id'),
        'candidate_commitments',
        ['candidate_id'],
    )
    op.create_index(
        op.f('ix_candidate_commitments_commitment_id'),
        'candidate_commitments',
        ['commitment_id'],
    )

    # -------------------------------------------------------------------------
    # Q3: Tighten context_type CHECK — remove 'mixed'
    # -------------------------------------------------------------------------
    op.drop_constraint('ck_commitments_context_type', 'commitments', type_='check')
    op.create_check_constraint(
        'ck_commitments_context_type',
        'commitments',
        "context_type IN ('internal', 'external')",
    )

    # -------------------------------------------------------------------------
    # Q4: Add commitment_type_enum and alter commitments.commitment_type column
    # -------------------------------------------------------------------------
    commitment_type_enum = postgresql.ENUM(
        'send', 'review', 'follow_up', 'deliver', 'investigate',
        'introduce', 'coordinate', 'update', 'delegate', 'schedule',
        'confirm', 'other',
        name='commitment_type_enum',
    )
    commitment_type_enum.create(op.get_bind(), checkfirst=True)

    op.execute(
        "ALTER TABLE commitments ALTER COLUMN commitment_type "
        "TYPE commitment_type_enum USING commitment_type::commitment_type_enum"
    )


def downgrade() -> None:
    """Reverse Phase 01 Q&A schema fixes."""

    # -------------------------------------------------------------------------
    # Q4: Revert commitments.commitment_type back to TEXT
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE commitments ALTER COLUMN commitment_type "
        "TYPE VARCHAR USING commitment_type::text"
    )
    postgresql.ENUM(name='commitment_type_enum').drop(op.get_bind(), checkfirst=True)

    # -------------------------------------------------------------------------
    # Q3: Restore original context_type CHECK (with 'mixed')
    # -------------------------------------------------------------------------
    op.drop_constraint('ck_commitments_context_type', 'commitments', type_='check')
    op.create_check_constraint(
        'ck_commitments_context_type',
        'commitments',
        "context_type IN ('internal', 'external', 'mixed')",
    )

    # -------------------------------------------------------------------------
    # Q1: Drop candidate_commitments join table
    # -------------------------------------------------------------------------
    op.drop_index(op.f('ix_candidate_commitments_commitment_id'), table_name='candidate_commitments')
    op.drop_index(op.f('ix_candidate_commitments_candidate_id'), table_name='candidate_commitments')
    op.drop_table('candidate_commitments')

    # -------------------------------------------------------------------------
    # Q1: Restore commitment_candidates.commitment_id FK column
    # -------------------------------------------------------------------------
    op.add_column(
        'commitment_candidates',
        sa.Column('commitment_id', postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_commitment_candidates_commitment_id_commitments'),
        'commitment_candidates',
        'commitments',
        ['commitment_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_commitment_candidates_commitment_id'),
        'commitment_candidates',
        ['commitment_id'],
    )
