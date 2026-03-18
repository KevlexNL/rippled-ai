"""Add user_identity_profiles table.

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, Sequence[str], None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_identity_profiles",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity_type", sa.String(50), nullable=False),
        sa.Column("identity_value", sa.String(255), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "identity_type", "identity_value", name="uq_uip_user_type_value"),
    )
    op.create_index("ix_uip_user_id", "user_identity_profiles", ["user_id"])
    op.create_index("ix_uip_value", "user_identity_profiles", ["identity_value"])


def downgrade() -> None:
    op.drop_index("ix_uip_value", table_name="user_identity_profiles")
    op.drop_index("ix_uip_user_id", table_name="user_identity_profiles")
    op.drop_table("user_identity_profiles")
