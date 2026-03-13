"""phase_c1_model_detection

Add model detection columns to commitment_candidates.
Supports Phase C1 — Model-Assisted Detection pipeline.

Revision ID: e9f0a1b2c3d4
Revises: d7e8f9a0b1c2
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'commitment_candidates',
        sa.Column('model_confidence', sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('model_classification', sa.String(20), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('model_explanation', sa.Text, nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('model_called_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'commitment_candidates',
        sa.Column('detection_method', sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('commitment_candidates', 'detection_method')
    op.drop_column('commitment_candidates', 'model_called_at')
    op.drop_column('commitment_candidates', 'model_explanation')
    op.drop_column('commitment_candidates', 'model_classification')
    op.drop_column('commitment_candidates', 'model_confidence')
