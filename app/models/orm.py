"""SQLAlchemy 2.0 ORM models for Rippled.ai — Phase 02.

These mirror the Alembic-managed tables exactly. Used for DB queries only.
Always convert to Pydantic schemas at the API boundary.
UUIDs use postgresql.UUID(as_uuid=False) so Python works with strings
while asyncpg correctly types them as UUID at the wire level.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Mirror the PostgreSQL enum types created in the Phase 01 migration.
# create_type=False tells SQLAlchemy not to CREATE TYPE (they already exist in the DB).
_source_type = ENUM('meeting', 'slack', 'email', name='source_type', create_type=False)
_lifecycle_state = ENUM(
    'proposed', 'needs_clarification', 'active', 'confirmed', 'in_progress',
    'dormant', 'delivered', 'completed', 'canceled', 'closed', 'discarded',
    name='lifecycle_state', create_type=False,
)
_signal_role = ENUM(
    'origin', 'clarification', 'progress', 'delivery', 'closure', 'conflict', 'reopening',
    name='signal_role', create_type=False,
)
_ambiguity_type = ENUM(
    'owner_missing', 'owner_vague_collective', 'owner_multiple_candidates', 'owner_conflicting',
    'timing_missing', 'timing_vague', 'timing_conflicting', 'timing_changed', 'timing_inferred_weak',
    'deliverable_unclear', 'target_unclear', 'status_unclear', 'commitment_unclear',
    name='ambiguity_type', create_type=False,
)
_ownership_ambiguity_type = ENUM(
    'missing', 'vague_collective', 'multiple_candidates', 'conflicting',
    name='ownership_ambiguity_type', create_type=False,
)
_timing_ambiguity_type = ENUM(
    'missing', 'vague', 'conflicting', 'changed', 'inferred_weak',
    name='timing_ambiguity_type', create_type=False,
)
_due_precision = ENUM(
    'day', 'week', 'month', 'vague',
    name='due_precision', create_type=False,
)
_deliverable_ambiguity_type = ENUM(
    'unclear', 'target_unknown',
    name='deliverable_ambiguity_type', create_type=False,
)
_commitment_class = ENUM(
    'big_promise', 'small_commitment',
    name='commitment_class', create_type=False,
)
_commitment_type_enum = ENUM(
    'send', 'review', 'follow_up', 'deliver', 'investigate', 'introduce',
    'coordinate', 'update', 'delegate', 'schedule', 'confirm', 'other',
    name='commitment_type_enum', create_type=False,
)
_user_relationship_enum = ENUM(
    'mine', 'contributing', 'watching',
    name='user_relationship_enum', create_type=False,
)


def _uuid(**kwargs):
    """Shorthand: PostgreSQL UUID stored/returned as Python str."""
    return UUID(as_uuid=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(_source_type, nullable=False)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    credentials: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SourceItem(Base):
    __tablename__ = "source_items"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    source_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(_source_type, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String, nullable=True)
    is_external_participant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachment: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    attachment_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    is_quoted_content: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    seed_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommitmentContext(Base):
    __tablename__ = "commitment_contexts"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    context_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("commitment_contexts.id", ondelete="SET NULL"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    commitment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    commitment_type: Mapped[str | None] = mapped_column(_commitment_type_enum, nullable=True)
    priority_class: Mapped[str | None] = mapped_column(_commitment_class, nullable=True)
    context_type: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_candidates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    resolved_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    ownership_ambiguity: Mapped[str | None] = mapped_column(_ownership_ambiguity_type, nullable=True)
    deadline_candidates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    resolved_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vague_time_phrase: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timing_ambiguity: Mapped[str | None] = mapped_column(_timing_ambiguity_type, nullable=True)
    due_precision: Mapped[str | None] = mapped_column(_due_precision, nullable=True)
    deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_entity: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliverable_ambiguity: Mapped[str | None] = mapped_column(_deliverable_ambiguity_type, nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(_lifecycle_state, server_default="proposed", nullable=False, index=True)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confidence_commitment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_owner: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_deadline: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_delivery: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_closure: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_actionability: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True, index=True)
    commitment_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_pieces_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_close_after_hours: Mapped[int] = mapped_column(Integer, server_default="48", nullable=False)
    observe_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_window_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    is_surfaced: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False, index=True)
    surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase 06 surfacing columns
    surfaced_as: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    timing_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_consequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cognitive_burden: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_for_surfacing: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    surfacing_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Phase C3 — delivery state + counterparty tracking
    delivery_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    counterparty_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # DEPRECATED: use requester/beneficiary
    counterparty_email: Mapped[str | None] = mapped_column(Text, nullable=True)  # DEPRECATED: use requester/beneficiary
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # DEPRECATED: use requester/beneficiary
    # Commitment structure enforcement
    counterparty_resolved: Mapped[str | None] = mapped_column(String(255), nullable=True)  # DEPRECATED: use requester/beneficiary
    # Requester + beneficiary (replaces counterparty_*)
    requester_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requester_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beneficiary_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beneficiary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requester_resolved: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beneficiary_resolved: Mapped[str | None] = mapped_column(String(255), nullable=True)
    speech_act: Mapped[str | None] = mapped_column(String(30), nullable=True)
    user_relationship: Mapped[str | None] = mapped_column(_user_relationship_enum, nullable=True)
    structure_complete: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    post_event_reviewed: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    # Skip state — item removed from review queue without lifecycle change
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Context tags — signal source labels (e.g. ["meeting"], ["slack"], ["email"])
    context_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitmentSignal(Base):
    __tablename__ = "commitment_signals"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    source_item_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id"), nullable=False, index=True)
    signal_role: Mapped[str] = mapped_column(_signal_role, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    interpretation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitmentAmbiguity(Base):
    __tablename__ = "commitment_ambiguities"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id"), nullable=False, index=True)
    ambiguity_type: Mapped[str] = mapped_column(_ambiguity_type, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False, index=True)
    resolved_by_item_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LifecycleTransition(Base):
    __tablename__ = "lifecycle_transitions"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id"), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(_lifecycle_state, nullable=True)
    to_state: Mapped[str] = mapped_column(_lifecycle_state, nullable=False)
    trigger_source_item_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_at_transition: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitmentCandidate(Base):
    __tablename__ = "commitment_candidates"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    originating_item_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_explicit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detection_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    priority_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    commitment_class_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_window: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    linked_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    observe_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flag_reanalysis: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    was_promoted: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    was_discarded: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase C1 — model detection columns
    model_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    model_classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detection_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CandidateCommitment(Base):
    __tablename__ = "candidate_commitments"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    candidate_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitment_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Signal Ingestion & Normalization Layer
# ---------------------------------------------------------------------------

_direction_enum = ENUM('inbound', 'outbound', 'unknown', name='direction', create_type=False)
_normalization_flag_enum = ENUM(
    'missing_subject', 'missing_text_body', 'html_only_body', 'quoted_text_detected',
    'signature_detected', 'thread_context_unavailable', 'attachment_present',
    'malformed_headers', 'sender_unresolved', 'multiple_possible_authored_blocks',
    name='normalization_flag', create_type=False,
)


class RawSignalIngest(Base):
    """Stores the original provider payload and ingest metadata."""
    __tablename__ = "raw_signal_ingests"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    source_type: Mapped[str] = mapped_column(_source_type, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    parse_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pending, success, failed
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class NormalizedSignalORM(Base):
    """Canonical normalized signal derived from RawSignalIngest."""
    __tablename__ = "normalized_signals"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    raw_signal_ingest_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("raw_signal_ingests.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source_type: Mapped[str] = mapped_column(_source_type, nullable=False)
    source_subtype: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    signal_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    direction: Mapped[str | None] = mapped_column(_direction_enum, nullable=True)
    is_inbound: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    is_outbound: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_authored_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    prior_context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_present: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    text_present: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    sender_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    to_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cc_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bcc_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    reply_to_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    participants_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    attachment_metadata_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    thread_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_index_guess: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    normalization_version: Mapped[str] = mapped_column(String(20), server_default="v1", nullable=False)
    normalization_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    normalization_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NormalizationRun(Base):
    """Audit record for each normalization pass."""
    __tablename__ = "normalization_runs"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    normalized_signal_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    normalization_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, partial_success, failed
    warnings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Clarification(Base):
    __tablename__ = "clarifications"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("users.id"), nullable=True)
    issue_types: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)
    issue_severity: Mapped[str] = mapped_column(String, nullable=False)
    why_this_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    observation_window_status: Mapped[str] = mapped_column(String, server_default="open", nullable=False)
    suggested_values: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    supporting_evidence: Mapped[list] = mapped_column(JSONB, server_default="[]", nullable=False)
    suggested_clarification_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    surface_recommendation: Mapped[str] = mapped_column(String, server_default="do_nothing", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SurfacingAudit(Base):
    __tablename__ = "surfacing_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    old_surfaced_as: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_surfaced_as: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), server_default="explicit", nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="confirmed", nullable=False, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rescheduled_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    attendees: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitmentEventLink(Base):
    __tablename__ = "commitment_event_links"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # Phase D3 — matching metadata (matched_on, scoring dimensions)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    digest_time: Mapped[str] = mapped_column(String(5), server_default="08:00", nullable=False)
    last_digest_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase C3 — Google OAuth tokens (Fernet-encrypted at write/read)
    google_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    digest_to_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LLM API key storage (Fernet-encrypted)
    anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase D1 — per-source observation window overrides (calendar hours)
    observation_window_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase D2 — per-user auto-close timing overrides (hours)
    auto_close_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Admin panel access
    is_super_admin: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserCommitmentProfile(Base):
    __tablename__ = "user_commitment_profiles"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    trigger_phrases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    high_signal_senders: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    suppressed_senders: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sender_weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    phrase_weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_items_processed: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    total_commitments_found: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    last_seed_pass_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Phase D4 — per-user feedback-driven threshold adjustments
    threshold_adjustments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserFeedback(Base):
    """Phase D4 — lightweight user feedback on commitments (dismiss/confirm/correct)."""
    __tablename__ = "user_feedback"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    field_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DigestLog(Base):
    __tablename__ = "digest_log"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    commitment_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class EvalDataset(Base):
    __tablename__ = "eval_datasets"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_item_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    expected_has_commitment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_commitment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    labeled_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    labeled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    items_tested: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    false_positives: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    true_negatives: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    false_negatives: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    precision_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    recall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    f1_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    total_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvalRunItem(Base):
    __tablename__ = "eval_run_items"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    eval_run_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_item_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    expected_has_commitment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_has_commitment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_commitments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DetectionAudit(Base):
    __tablename__ = "detection_audit"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    source_item_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tier_used: Mapped[str] = mapped_column(String(10), nullable=False)
    matched_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    commitment_created: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


# ---------------------------------------------------------------------------
# Feedback schema (WO-RIPPLED-FEEDBACK-SCHEMA)
# ---------------------------------------------------------------------------

class SignalFeedback(Base):
    """Tier 2 — extraction review feedback."""
    __tablename__ = "signal_feedback"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_signal_feedback_rating"),
    )

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_audit_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("detection_audit.id", ondelete="SET NULL"), nullable=True)
    source_item_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    extraction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missed_commitments: Mapped[str | None] = mapped_column(Text, nullable=True)
    false_positives: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutcomeFeedback(Base):
    """Tier 2 — outcome review feedback."""
    __tablename__ = "outcome_feedback"
    __table_args__ = (
        CheckConstraint("usefulness_rating BETWEEN 1 AND 5", name="ck_outcome_feedback_usefulness_rating"),
    )

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    commitment_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    was_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    usefulness_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_timely: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdhocSignal(Base):
    """Tier 3 — Telegram ad-hoc input."""
    __tablename__ = "adhoc_signals"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), server_default="telegram", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    match_status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=True, index=True)
    matched_commitment_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("commitments.id", ondelete="SET NULL"), nullable=True)
    matched_source_item_id: Mapped[str | None] = mapped_column(_uuid(), ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True)
    match_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    was_found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserIdentityProfile(Base):
    __tablename__ = "user_identity_profiles"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    identity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    identity_value: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LlmJudgeRun(Base):
    """Tier 1 — automated LLM-as-judge self-improvement."""
    __tablename__ = "llm_judge_runs"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    student_model: Mapped[str] = mapped_column(String(100), nullable=False)
    items_reviewed: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    false_positives_found: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    false_negatives_found: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    prompt_improvement_suggestions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_judge_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# LLM Orchestration Layer (Track 2)
# ---------------------------------------------------------------------------

class SignalProcessingRun(Base):
    """Top-level record for one orchestration pipeline run."""
    __tablename__ = "signal_processing_runs"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    normalized_signal_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pipeline_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed, partial_success
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_routing_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    final_routing_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SignalProcessingStageRun(Base):
    """Per-stage record within an orchestration run."""
    __tablename__ = "signal_processing_stage_runs"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    signal_processing_run_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("signal_processing_runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed, skipped
    model_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CandidateSignalRecord(Base):
    """Candidate record produced by the orchestration pipeline for downstream use."""
    __tablename__ = "candidate_signal_records"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    normalized_signal_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    signal_processing_run_id: Mapped[str] = mapped_column(
        _uuid(), ForeignKey("signal_processing_runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    candidate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    speech_act: Mapped[str | None] = mapped_column(String(30), nullable=True)
    owner_resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)
    owner_text: Mapped[str | None] = mapped_column(String, nullable=True)
    deliverable_text: Mapped[str | None] = mapped_column(String, nullable=True)
    timing_text: Mapped[str | None] = mapped_column(String, nullable=True)
    target_text: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    field_confidence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    routing_action: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Common Terms (Domain Vocabulary)
# ---------------------------------------------------------------------------

class CommonTerm(Base):
    """User-defined canonical term with context for transcript enrichment."""
    __tablename__ = "common_terms"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_term: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    aliases: Mapped[list["CommonTermAlias"]] = relationship(
        "CommonTermAlias", back_populates="term", cascade="all, delete-orphan",
    )


class CommonTermAlias(Base):
    """Alias string that resolves to a CommonTerm."""
    __tablename__ = "common_term_aliases"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    term_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("common_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), server_default="manual", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    term: Mapped["CommonTerm"] = relationship("CommonTerm", back_populates="aliases")
