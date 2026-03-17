"""Create eval harness tables (eval_datasets, eval_runs, eval_run_items).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- eval_datasets ---
    op.create_table(
        "eval_datasets",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_item_id", UUID(as_uuid=False), sa.ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_has_commitment", sa.Boolean, nullable=False),
        sa.Column("expected_commitment_count", sa.Integer, nullable=True),
        sa.Column("label_notes", sa.Text, nullable=True),
        sa.Column("labeled_by", sa.String(100), nullable=True),
        sa.Column("labeled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_eval_datasets_user_id", "eval_datasets", ["user_id"])

    # --- eval_runs ---
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("items_tested", sa.Integer, server_default="0", nullable=False),
        sa.Column("true_positives", sa.Integer, server_default="0", nullable=False),
        sa.Column("false_positives", sa.Integer, server_default="0", nullable=False),
        sa.Column("true_negatives", sa.Integer, server_default="0", nullable=False),
        sa.Column("false_negatives", sa.Integer, server_default="0", nullable=False),
        sa.Column("precision_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("recall_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("f1_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("total_cost_estimate", sa.Numeric(10, 6), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # --- eval_run_items ---
    op.create_table(
        "eval_run_items",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("eval_run_id", UUID(as_uuid=False), sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_item_id", UUID(as_uuid=False), sa.ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_has_commitment", sa.Boolean, nullable=False),
        sa.Column("actual_has_commitment", sa.Boolean, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("raw_prompt", sa.Text, nullable=True),
        sa.Column("raw_response", sa.Text, nullable=True),
        sa.Column("parsed_commitments", JSONB, nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("cost_estimate", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_eval_run_items_eval_run_id", "eval_run_items", ["eval_run_id"])


def downgrade() -> None:
    op.drop_table("eval_run_items")
    op.drop_table("eval_runs")
    op.drop_table("eval_datasets")
