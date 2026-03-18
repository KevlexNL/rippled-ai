"""Add user_id column to surfacing_audit table.

Adds user_id (UUID, NOT NULL, FK to users.id ON DELETE CASCADE).
Backfills existing rows with Kevin's user ID.

Revision ID: g1h2i3j4k5l6
Revises: f6a7b8c9d0e1
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kevin's user ID — used to backfill pre-existing rows
KEVIN_USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"


def upgrade() -> None:
    # Step 1: add as nullable so existing rows are not blocked
    op.add_column(
        "surfacing_audit",
        sa.Column("user_id", UUID(as_uuid=False), nullable=True),
    )

    # Step 2: backfill existing rows with Kevin's user ID
    op.execute(
        f"UPDATE surfacing_audit SET user_id = '{KEVIN_USER_ID}' WHERE user_id IS NULL"
    )

    # Step 3: set NOT NULL constraint now that all rows have a value
    op.alter_column("surfacing_audit", "user_id", nullable=False)

    # Step 4: add foreign key to users.id with ON DELETE CASCADE
    op.create_foreign_key(
        "fk_surfacing_audit_user_id",
        "surfacing_audit",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 5: index for efficient per-user queries
    op.create_index(
        "ix_surfacing_audit_user_id",
        "surfacing_audit",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_surfacing_audit_user_id", table_name="surfacing_audit")
    op.drop_constraint("fk_surfacing_audit_user_id", "surfacing_audit", type_="foreignkey")
    op.drop_column("surfacing_audit", "user_id")
