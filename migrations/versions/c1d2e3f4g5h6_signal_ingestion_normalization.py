"""Signal ingestion & normalization layer

Revision ID: c1d2e3f4g5h6
Revises: b2c3d4e5f6a7
Create Date: 2026-03-22

Adds raw_signal_ingests, normalized_signals, normalization_runs tables
and the direction enum type.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID


# revision identifiers
revision = "c1d2e3f4g5h6"
down_revision = "n8o9p0q1r2s3"
branch_labels = None
depends_on = None

# Reference existing enums without creating them
_source_type = ENUM("meeting", "slack", "email", name="source_type", create_type=False)
_direction = ENUM("inbound", "outbound", "unknown", name="direction", create_type=False)


def upgrade() -> None:
    # Create direction enum type (source_type already exists from Phase 01)
    direction_enum = sa.Enum("inbound", "outbound", "unknown", name="direction")
    direction_enum.create(op.get_bind(), checkfirst=True)

    # --- raw_signal_ingests ---
    op.create_table(
        "raw_signal_ingests",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source_type", _source_type, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=False),
        sa.Column("provider_thread_id", sa.String(), nullable=True),
        sa.Column("provider_account_id", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parse_status", sa.String(20), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_raw_signal_ingests_payload_hash", "raw_signal_ingests", ["payload_hash"])

    # --- normalized_signals ---
    op.create_table(
        "normalized_signals",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("raw_signal_ingest_id", UUID(as_uuid=False), sa.ForeignKey("raw_signal_ingests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", _source_type, nullable=False),
        sa.Column("source_subtype", sa.String(30), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=False),
        sa.Column("provider_thread_id", sa.String(), nullable=True),
        sa.Column("provider_account_id", sa.String(), nullable=True),
        sa.Column("signal_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", _direction, nullable=True),
        sa.Column("is_inbound", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_outbound", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("latest_authored_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("prior_context_text", sa.Text(), nullable=True),
        sa.Column("full_visible_text", sa.Text(), nullable=True),
        sa.Column("html_present", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("text_present", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sender_json", JSONB(), nullable=True),
        sa.Column("to_json", JSONB(), nullable=True),
        sa.Column("cc_json", JSONB(), nullable=True),
        sa.Column("bcc_json", JSONB(), nullable=True),
        sa.Column("reply_to_json", JSONB(), nullable=True),
        sa.Column("participants_json", JSONB(), nullable=True),
        sa.Column("attachment_metadata_json", JSONB(), nullable=True),
        sa.Column("thread_position", sa.Integer(), nullable=True),
        sa.Column("message_index_guess", sa.Integer(), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        sa.Column("normalization_version", sa.String(20), server_default=sa.text("'v1'"), nullable=False),
        sa.Column("normalization_flags", JSONB(), nullable=True),
        sa.Column("normalization_warnings", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_normalized_signals_raw_signal_ingest_id", "normalized_signals", ["raw_signal_ingest_id"])

    # --- normalization_runs ---
    op.create_table(
        "normalization_runs",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("normalized_signal_id", UUID(as_uuid=False), sa.ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalization_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("warnings_json", JSONB(), nullable=True),
        sa.Column("timings_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_normalization_runs_normalized_signal_id", "normalization_runs", ["normalized_signal_id"])


def downgrade() -> None:
    op.drop_table("normalization_runs")
    op.drop_table("normalized_signals")
    op.drop_table("raw_signal_ingests")
    sa.Enum(name="direction").drop(op.get_bind(), checkfirst=True)
