"""Backfill structure_complete=true for commitments stuck at false.

373 commitments created before the promoter fix (commit 6910419) have
structure_complete=false because the promoter did not set it and the
clarifier could not derive it from empty linked_entities.

The promoter now unconditionally sets structure_complete=true (line 185),
so these historical commitments need to be backfilled to match.

Only updates commitments in active lifecycle states — terminal states
(completed, canceled) are not re-evaluated by the surfacing sweep.

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-04-01
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE commitments
        SET structure_complete = true
        WHERE structure_complete = false
          AND lifecycle_state IN (
              'proposed', 'active', 'needs_clarification',
              'confirmed', 'in_progress'
          )
        """
    )


def downgrade() -> None:
    # One-way data migration — cannot reliably determine which rows
    # were originally false vs legitimately true.
    pass
