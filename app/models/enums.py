"""PostgreSQL enum types for Rippled.ai — Phase 01 schema."""

import enum


class SourceType(str, enum.Enum):
    meeting = "meeting"
    slack = "slack"
    email = "email"


class LifecycleState(str, enum.Enum):
    proposed = "proposed"
    needs_clarification = "needs_clarification"
    active = "active"
    delivered = "delivered"
    closed = "closed"
    discarded = "discarded"


class SignalRole(str, enum.Enum):
    origin = "origin"
    clarification = "clarification"
    progress = "progress"
    delivery = "delivery"
    closure = "closure"
    conflict = "conflict"
    reopening = "reopening"


class AmbiguityType(str, enum.Enum):
    # Ownership
    owner_missing = "owner_missing"
    owner_vague_collective = "owner_vague_collective"
    owner_multiple_candidates = "owner_multiple_candidates"
    owner_conflicting = "owner_conflicting"
    # Timing
    timing_missing = "timing_missing"
    timing_vague = "timing_vague"
    timing_conflicting = "timing_conflicting"
    timing_changed = "timing_changed"
    timing_inferred_weak = "timing_inferred_weak"
    # Deliverable
    deliverable_unclear = "deliverable_unclear"
    target_unclear = "target_unclear"
    # Status / commitment
    status_unclear = "status_unclear"
    commitment_unclear = "commitment_unclear"


class OwnershipAmbiguityType(str, enum.Enum):
    missing = "missing"
    vague_collective = "vague_collective"
    multiple_candidates = "multiple_candidates"
    conflicting = "conflicting"


class TimingAmbiguityType(str, enum.Enum):
    missing = "missing"
    vague = "vague"
    conflicting = "conflicting"
    changed = "changed"
    inferred_weak = "inferred_weak"


class DeliverableAmbiguityType(str, enum.Enum):
    unclear = "unclear"
    target_unknown = "target_unknown"


class CommitmentClass(str, enum.Enum):
    big_promise = "big_promise"
    small_commitment = "small_commitment"


# @REVIEW_LATER(2026-03-30)
# Action: Query `SELECT commitment_type, COUNT(*) FROM commitments WHERE commitment_type = 'other' GROUP BY 1 ORDER BY 2 DESC`
#         and review what real usage patterns have emerged. Promote frequent patterns to dedicated enum values via migration.
# Context: See build/phases/01-schema/qa-decisions.md Q4 — 'other' is intentional fallback; this review ensures it doesn't become a permanent catch-all.
class CommitmentType(str, enum.Enum):
    send = "send"
    review = "review"
    follow_up = "follow_up"
    deliver = "deliver"
    investigate = "investigate"
    introduce = "introduce"
    coordinate = "coordinate"
    update = "update"
    delegate = "delegate"
    schedule = "schedule"
    confirm = "confirm"
    other = "other"
