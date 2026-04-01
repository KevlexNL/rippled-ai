"""Add metadata JSONB column to commitment_event_links.

Phase D3 — Calendar Integration.
Stores matching details (matched_on, scoring dimensions) for calendar-as-evidence links.
NULL = no metadata (backward compatible with existing delivery_at links).

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commitment_event_links",
        sa.Column("metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("commitment_event_links", "metadata")
