"""Extend detection_audit with full prompt/response logging columns.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detection_audit", sa.Column("prompt_version", sa.String(50), nullable=True))
    op.add_column("detection_audit", sa.Column("raw_prompt", sa.Text, nullable=True))
    op.add_column("detection_audit", sa.Column("raw_response", sa.Text, nullable=True))
    op.add_column("detection_audit", sa.Column("parsed_result", JSONB, nullable=True))
    op.add_column("detection_audit", sa.Column("tokens_in", sa.Integer, nullable=True))
    op.add_column("detection_audit", sa.Column("tokens_out", sa.Integer, nullable=True))
    op.add_column("detection_audit", sa.Column("cost_estimate", sa.Numeric(10, 6), nullable=True))
    op.add_column("detection_audit", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("detection_audit", sa.Column("duration_ms", sa.Integer, nullable=True))
    op.add_column("detection_audit", sa.Column("error_detail", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("detection_audit", "error_detail")
    op.drop_column("detection_audit", "duration_ms")
    op.drop_column("detection_audit", "model")
    op.drop_column("detection_audit", "cost_estimate")
    op.drop_column("detection_audit", "tokens_out")
    op.drop_column("detection_audit", "tokens_in")
    op.drop_column("detection_audit", "parsed_result")
    op.drop_column("detection_audit", "raw_response")
    op.drop_column("detection_audit", "raw_prompt")
    op.drop_column("detection_audit", "prompt_version")
