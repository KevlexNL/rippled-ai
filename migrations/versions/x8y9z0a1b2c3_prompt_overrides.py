"""Prompt overrides table for admin prompt management.

Stores per-prompt text overrides that take precedence over hardcoded defaults.
Used by the prompt registry to serve customized prompts to pipeline stages.

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-04-03
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_overrides",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("prompt_overrides")
