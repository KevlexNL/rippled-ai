"""Deactivate placeholder email sources with RFC 2606 reserved domains.

Sources configured with example.com/example.org/example.net hostnames
are test/placeholder entries that cause spurious DNS errors on every
poll cycle. This migration deactivates them.

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "o9p0q1r2s3t4"
down_revision = "d2e3f4g5h6i7"
branch_labels = None
depends_on = None

# RFC 2606 reserved domains used as placeholder IMAP hosts
_RESERVED_HOSTS = [
    "%example.com%",
    "%example.org%",
    "%example.net%",
]


def upgrade() -> None:
    conn = op.get_bind()
    for pattern in _RESERVED_HOSTS:
        conn.execute(
            sa.text(
                """
                UPDATE sources
                SET is_active = false, updated_at = now()
                WHERE source_type = 'email'
                  AND is_active = true
                  AND credentials::text ILIKE :pattern
                """
            ),
            {"pattern": pattern},
        )


def downgrade() -> None:
    # No-op: we cannot know which sources were legitimately inactive
    # before this migration ran.
    pass
