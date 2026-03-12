"""phase04_clarifications

Add clarifications table for Phase 04 — Clarification pipeline.

Stores the per-candidate analysis result, surface recommendation, and
suggested values produced before (or at) promotion to a full Commitment.

Revision ID: a4b5c6d7e8f9
Revises: c3d9e1f2a4b5
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'c3d9e1f2a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'clarifications',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'commitment_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('commitments.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('users.id'),
            nullable=True,
        ),
        sa.Column(
            'issue_types',
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column('issue_severity', sa.String(), nullable=False),
        sa.Column('why_this_matters', sa.Text(), nullable=True),
        sa.Column(
            'observation_window_status',
            sa.String(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            'suggested_values',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            'supporting_evidence',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column('suggested_clarification_prompt', sa.Text(), nullable=True),
        sa.Column(
            'surface_recommendation',
            sa.String(),
            nullable=False,
            server_default=sa.text("'do_nothing'"),
        ),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    op.create_index(
        'ix_clarifications_commitment_id',
        'clarifications',
        ['commitment_id'],
    )
    op.create_index(
        'ix_clarifications_surface_recommendation',
        'clarifications',
        ['surface_recommendation'],
    )


def downgrade() -> None:
    op.drop_index('ix_clarifications_surface_recommendation', table_name='clarifications')
    op.drop_index('ix_clarifications_commitment_id', table_name='clarifications')
    op.drop_table('clarifications')
