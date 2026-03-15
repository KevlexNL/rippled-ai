"""frontend_backend_gap

Add counterparty_name to commitments, LLM key columns to user_settings.
Supports WO-RIPPLED-FRONTEND-BACKEND-GAP.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add counterparty_name to commitments ---
    op.add_column(
        'commitments',
        sa.Column('counterparty_name', sa.String(255), nullable=True),
    )

    # --- Add LLM API key storage to user_settings ---
    op.add_column(
        'user_settings',
        sa.Column('anthropic_api_key_encrypted', sa.Text(), nullable=True),
    )
    op.add_column(
        'user_settings',
        sa.Column('openai_api_key_encrypted', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'openai_api_key_encrypted')
    op.drop_column('user_settings', 'anthropic_api_key_encrypted')
    op.drop_column('commitments', 'counterparty_name')
