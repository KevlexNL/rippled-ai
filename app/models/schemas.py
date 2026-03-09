"""Pydantic v2 schemas for Rippled.ai API — Phase 01."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import (
    SourceType,
    LifecycleState,
    CommitmentClass,
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
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


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
    metadata_: dict | None = None


class SourceUpdate(_Base):
    display_name: str | None = None
    is_active: bool | None = None
    metadata_: dict | None = None


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
    metadata_: dict | None = None
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
    commitment_type: str | None
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
    created_at: datetime
    updated_at: datetime


class CommitmentCreate(_Base):
    title: str
    description: str | None = None
    commitment_text: str | None = None
    commitment_type: str | None = None
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
    trigger_reason: str | None
    confidence_at_transition: Decimal | None
    created_at: datetime
