"""Add commitment structure enforcement columns.

counterparty_resolved, user_relationship, structure_complete columns
for canonical commitment structure: [Owner] promised [Deliverable] to [Counterparty].

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, Sequence[str], None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the user_relationship_enum type
    user_relationship_enum = sa.Enum(
        "mine", "contributing", "watching",
        name="user_relationship_enum",
    )
    user_relationship_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "commitments",
        sa.Column("counterparty_resolved", sa.String(255), nullable=True),
    )
    op.add_column(
        "commitments",
        sa.Column(
            "user_relationship",
            user_relationship_enum,
            nullable=True,
        ),
    )
    op.add_column(
        "commitments",
        sa.Column(
            "structure_complete",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    # Index for surfacing queries that filter by user_relationship
    op.create_index(
        "ix_commitments_user_relationship",
        "commitments",
        ["user_relationship"],
    )
    # Index for structure_complete gate
    op.create_index(
        "ix_commitments_structure_complete",
        "commitments",
        ["structure_complete"],
    )


def downgrade() -> None:
    op.drop_index("ix_commitments_structure_complete", table_name="commitments")
    op.drop_index("ix_commitments_user_relationship", table_name="commitments")
    op.drop_column("commitments", "structure_complete")
    op.drop_column("commitments", "user_relationship")
    op.drop_column("commitments", "counterparty_resolved")
    sa.Enum(name="user_relationship_enum").drop(op.get_bind(), checkfirst=True)
