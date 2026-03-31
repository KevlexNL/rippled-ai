"""Add context_tags JSONB field to commitments table.

context_tags is a JSONB array (e.g. ["meeting"], ["slack"], ["client"]) that
categorises a commitment by the signal source or contextual labels.

Populated at promotion time based on the originating source_type:
  - meeting → ["meeting"]
  - slack   → ["slack"]
  - email   → ["email"]

Existing rows are backfilled from the originating CommitmentCandidate's
source_type via a join on candidate_commitments.

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, None] = "q1r2s3t4u5v6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add context_tags column (nullable JSONB, default empty array for non-null rows)
    op.add_column(
        "commitments",
        sa.Column("context_tags", JSONB, nullable=True),
    )

    # Backfill from originating candidate's source_type
    op.execute(
        """
        UPDATE commitments c
        SET context_tags = to_jsonb(ARRAY[cc_candidate.source_type])
        FROM candidate_commitments cc_join
        JOIN commitment_candidates cc_candidate
          ON cc_candidate.id = cc_join.candidate_id
        WHERE cc_join.commitment_id = c.id
          AND cc_candidate.source_type IS NOT NULL
          AND c.context_tags IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("commitments", "context_tags")
