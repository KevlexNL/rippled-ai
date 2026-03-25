"""Backfill seed_processed_at for all source_items with detection_audit records.

Items that have already been scanned by the detection pipeline should have
seed_processed_at set so the sweep idempotency guard skips them on future runs.
Sets seed_processed_at to the earliest detection_audit.created_at for each item.

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-03-25
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "p0q1r2s3t4u5"
down_revision = "o9p0q1r2s3t4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_items si
        SET seed_processed_at = sub.first_audit
        FROM (
            SELECT source_item_id, MIN(created_at) AS first_audit
            FROM detection_audit
            GROUP BY source_item_id
        ) sub
        WHERE si.id = sub.source_item_id
          AND si.seed_processed_at IS NULL
        """
    )


def downgrade() -> None:
    # Reversing the backfill: clear seed_processed_at for items that were
    # backfilled (items whose seed_processed_at matches their first audit).
    # In practice this is a one-way data migration.
    pass
