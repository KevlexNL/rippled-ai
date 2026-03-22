"""LLM orchestration layer — staged pipeline tables

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2026-03-22

Adds signal_processing_runs, signal_processing_stage_runs,
candidate_signal_records tables for Track 2 orchestration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers
revision = "d2e3f4g5h6i7"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- signal_processing_runs ---
    op.create_table(
        "signal_processing_runs",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("normalized_signal_id", UUID(as_uuid=False), sa.ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_json", JSONB(), nullable=True),
        sa.Column("final_routing_action", sa.String(50), nullable=True),
        sa.Column("final_routing_reason", sa.String(255), nullable=True),
    )
    op.create_index("ix_signal_processing_runs_normalized_signal_id", "signal_processing_runs", ["normalized_signal_id"])

    # --- signal_processing_stage_runs ---
    op.create_table(
        "signal_processing_stage_runs",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("signal_processing_run_id", UUID(as_uuid=False), sa.ForeignKey("signal_processing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_name", sa.String(50), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model_provider", sa.String(30), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("prompt_template_id", sa.String(50), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("input_json", JSONB(), nullable=False),
        sa.Column("output_json", JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage_json", JSONB(), nullable=True),
        sa.Column("error_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_signal_processing_stage_runs_run_id", "signal_processing_stage_runs", ["signal_processing_run_id"])

    # --- candidate_signal_records ---
    op.create_table(
        "candidate_signal_records",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("normalized_signal_id", UUID(as_uuid=False), sa.ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_processing_run_id", UUID(as_uuid=False), sa.ForeignKey("signal_processing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_type", sa.String(50), nullable=False),
        sa.Column("speech_act", sa.String(30), nullable=True),
        sa.Column("owner_resolution", sa.String(30), nullable=True),
        sa.Column("owner_text", sa.String(), nullable=True),
        sa.Column("deliverable_text", sa.String(), nullable=True),
        sa.Column("timing_text", sa.String(), nullable=True),
        sa.Column("target_text", sa.String(), nullable=True),
        sa.Column("evidence_span", sa.Text(), nullable=True),
        sa.Column("evidence_source", sa.String(30), nullable=True),
        sa.Column("field_confidence_json", JSONB(), nullable=True),
        sa.Column("routing_action", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_candidate_signal_records_normalized_signal_id", "candidate_signal_records", ["normalized_signal_id"])
    op.create_index("ix_candidate_signal_records_run_id", "candidate_signal_records", ["signal_processing_run_id"])


def downgrade() -> None:
    op.drop_table("candidate_signal_records")
    op.drop_table("signal_processing_stage_runs")
    op.drop_table("signal_processing_runs")
