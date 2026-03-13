"""Pydantic v2 schemas for Rippled.ai API — Phase 01."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    SourceType,
    LifecycleState,
    CommitmentClass,
    CommitmentType,
    OwnershipAmbiguityType,
    TimingAmbiguityType,
    DeliverableAmbiguityType,
    AmbiguityType,
    SignalRole,
)


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _Base(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,  # allow both alias and field name on input
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserRead(_Base):
    id: str
    email: str
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class UserCreate(_Base):
    email: str
    display_name: str | None = None


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class SourceRead(_Base):
    id: str
    user_id: str
    source_type: SourceType
    provider_account_id: str | None
    display_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SourceCreate(_Base):
    source_type: SourceType
    provider_account_id: str | None = None
    display_name: str | None = None
    # Field alias: API clients send {"metadata": ...}, stored as metadata_ in Python to avoid reserved name
    metadata_: dict | None = Field(None, alias="metadata")


class SourceUpdate(_Base):
    display_name: str | None = None
    is_active: bool | None = None
    metadata_: dict | None = Field(None, alias="metadata")


# ---------------------------------------------------------------------------
# SourceItem
# ---------------------------------------------------------------------------

class SourceItemRead(_Base):
    id: str
    source_id: str
    user_id: str
    source_type: SourceType
    external_id: str
    thread_id: str | None
    direction: str | None
    sender_name: str | None
    sender_email: str | None
    is_external_participant: bool | None
    content: str | None
    has_attachment: bool
    source_url: str | None
    occurred_at: datetime
    ingested_at: datetime
    is_quoted_content: bool


class SourceItemCreate(_Base):
    source_id: str
    source_type: SourceType
    external_id: str
    thread_id: str | None = None
    direction: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    is_external_participant: bool | None = None
    content: str | None = None
    content_normalized: str | None = None
    has_attachment: bool = False
    attachment_metadata: dict | None = None
    recipients: list[dict] | None = None
    source_url: str | None = None
    occurred_at: datetime
    metadata_: dict | None = Field(None, alias="metadata")
    is_quoted_content: bool = False


# ---------------------------------------------------------------------------
# Commitment
# ---------------------------------------------------------------------------

class CommitmentRead(_Base):
    id: str
    user_id: str
    version: int
    title: str
    description: str | None
    commitment_text: str | None
    commitment_type: CommitmentType | None
    priority_class: CommitmentClass | None
    context_type: str | None
    resolved_owner: str | None
    suggested_owner: str | None
    ownership_ambiguity: OwnershipAmbiguityType | None
    resolved_deadline: datetime | None
    vague_time_phrase: str | None
    suggested_due_date: datetime | None
    timing_ambiguity: TimingAmbiguityType | None
    deliverable: str | None
    target_entity: str | None
    suggested_next_step: str | None
    deliverable_ambiguity: DeliverableAmbiguityType | None
    lifecycle_state: LifecycleState
    state_changed_at: datetime
    confidence_commitment: Decimal | None
    confidence_owner: Decimal | None
    confidence_deadline: Decimal | None
    confidence_delivery: Decimal | None
    confidence_closure: Decimal | None
    confidence_actionability: Decimal | None
    commitment_explanation: str | None
    missing_pieces_explanation: str | None
    is_surfaced: bool
    surfaced_at: datetime | None
    observe_until: datetime | None
    observation_window_hours: Decimal | None
    # Phase 06 surfacing fields
    surfaced_as: str | None
    priority_score: Decimal | None
    timing_strength: int | None
    business_consequence: int | None
    cognitive_burden: int | None
    confidence_for_surfacing: Decimal | None
    surfacing_reason: str | None
    # JSONB candidate arrays (read-only; included for surfacing/UI context)
    owner_candidates: list[Any] | None
    deadline_candidates: list[Any] | None
    created_at: datetime
    updated_at: datetime


class CommitmentCreate(_Base):
    title: str
    description: str | None = None
    commitment_text: str | None = None
    commitment_type: CommitmentType | None = None
    priority_class: CommitmentClass | None = None
    context_type: str | None = None
    owner_candidates: list[Any] | None = None
    resolved_owner: str | None = None
    suggested_owner: str | None = None
    ownership_ambiguity: OwnershipAmbiguityType | None = None
    deadline_candidates: list[Any] | None = None
    resolved_deadline: datetime | None = None
    vague_time_phrase: str | None = None
    suggested_due_date: datetime | None = None
    timing_ambiguity: TimingAmbiguityType | None = None
    deliverable: str | None = None
    target_entity: str | None = None
    suggested_next_step: str | None = None
    deliverable_ambiguity: DeliverableAmbiguityType | None = None
    confidence_commitment: Decimal | None = None
    confidence_actionability: Decimal | None = None
    commitment_explanation: str | None = None
    observe_until: datetime | None = None
    observation_window_hours: Decimal | None = None


class CommitmentUpdate(_Base):
    title: str | None = None
    description: str | None = None
    lifecycle_state: LifecycleState | None = None
    resolved_owner: str | None = None
    resolved_deadline: datetime | None = None
    deliverable: str | None = None
    confidence_actionability: Decimal | None = None
    is_surfaced: bool | None = None


# ---------------------------------------------------------------------------
# CommitmentSignal
# ---------------------------------------------------------------------------

class CommitmentSignalRead(_Base):
    id: str
    commitment_id: str
    source_item_id: str
    user_id: str
    signal_role: SignalRole
    confidence: Decimal | None
    interpretation_note: str | None
    created_at: datetime


class CommitmentSignalCreate(_Base):
    commitment_id: str
    source_item_id: str
    signal_role: SignalRole
    confidence: Decimal | None = None
    interpretation_note: str | None = None


# ---------------------------------------------------------------------------
# CommitmentAmbiguity
# ---------------------------------------------------------------------------

class CommitmentAmbiguityRead(_Base):
    id: str
    commitment_id: str
    ambiguity_type: AmbiguityType
    description: str | None
    is_resolved: bool
    resolved_by_item_id: str | None  # source_item that resolved this ambiguity (null if unresolved)
    resolved_at: datetime | None
    created_at: datetime


class CommitmentAmbiguityCreate(_Base):
    ambiguity_type: AmbiguityType
    description: str | None = None


# ---------------------------------------------------------------------------
# LifecycleTransition
# ---------------------------------------------------------------------------

class LifecycleTransitionRead(_Base):
    id: str
    commitment_id: str
    from_state: LifecycleState | None
    to_state: LifecycleState
    trigger_source_item_id: str | None  # source_item that drove the transition (null if SET NULL on delete)
    trigger_reason: str | None
    confidence_at_transition: Decimal | None
    created_at: datetime


# ---------------------------------------------------------------------------
# CommitmentCandidate
# ---------------------------------------------------------------------------

class CommitmentCandidateRead(_Base):
    id: str
    user_id: str
    originating_item_id: str | None  # nullable only if originating source_item was deleted
    source_type: str | None
    raw_text: str | None
    trigger_class: str | None
    is_explicit: bool | None
    detection_explanation: str | None
    confidence_score: Decimal | None
    priority_hint: str | None
    commitment_class_hint: str | None
    context_window: dict | None
    linked_entities: dict | None
    observe_until: datetime | None
    flag_reanalysis: bool
    was_promoted: bool
    was_discarded: bool
    discard_reason: str | None
    created_at: datetime
    updated_at: datetime


class CommitmentCandidateCreate(_Base):
    # originating_item_id is required on create — DB is nullable only for FK SET NULL on delete.
    # Never pass null from application code.
    originating_item_id: str
    source_type: str | None = None
    raw_text: str | None = None
    trigger_class: str | None = None
    is_explicit: bool | None = None
    detection_explanation: str | None = None
    confidence_score: Decimal | None = None
    priority_hint: str | None = None
    commitment_class_hint: str | None = None
    context_window: dict | None = None
    linked_entities: dict | None = None
    observe_until: datetime | None = None
    flag_reanalysis: bool = False


# ---------------------------------------------------------------------------
# CandidateCommitment (N:M join table)
# ---------------------------------------------------------------------------

class CandidateCommitmentCreate(_Base):
    candidate_id: str
    commitment_id: str


class CandidateCommitmentRead(_Base):
    id: str
    candidate_id: str
    commitment_id: str
    created_at: datetime
