"""Add speech_act column to commitments table.

Adds a varchar speech_act column (nullable) for speech act classification.
Backfills existing records with 'self_commitment' as safe default.

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALID_SPEECH_ACTS = (
    "request", "self_commitment", "acceptance", "status_update",
    "completion", "cancellation", "decline", "reassignment", "informational",
)


def upgrade() -> None:
    op.add_column(
        "commitments",
        sa.Column("speech_act", sa.String(30), nullable=True),
    )
    # Check constraint to enforce valid values
    op.create_check_constraint(
        "ck_commitments_speech_act_valid",
        "commitments",
        sa.column("speech_act").in_(_VALID_SPEECH_ACTS),
    )
    # Backfill existing records — all existing commitments were extracted
    # as self-commitments (not requests), so this is a safe default.
    op.execute("UPDATE commitments SET speech_act = 'self_commitment' WHERE speech_act IS NULL")


def downgrade() -> None:
    op.drop_constraint("ck_commitments_speech_act_valid", "commitments", type_="check")
    op.drop_column("commitments", "speech_act")
