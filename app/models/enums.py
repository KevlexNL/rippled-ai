"""PostgreSQL enum types for Rippled.ai — Phase 01 schema."""

import enum


class SourceType(str, enum.Enum):
    meeting = "meeting"
    slack = "slack"
    email = "email"


class LifecycleState(str, enum.Enum):
    """Lifecycle states for commitments.

    proposed — Detected, not yet reviewed by user. Default for all new commitments.
    needs_clarification — System cannot resolve enough structure. Waiting for more context.
    active — Commitment is real, confirmed, and open. User is aware.
    confirmed — User has explicitly verified this commitment is real.
    in_progress — Work has started. User or system flagged as underway.
    dormant — Not relevant now, retained for future surfacing. User said "not now."
    delivered — Action appears taken / thing sent. System-detected from completion signals.
    completed — Work fully done. User confirmed or strong completion evidence.
    canceled — Commitment explicitly withdrawn or declined.
    closed — Obligation no longer requires attention (covers completed + canceled + stale).
    discarded — Wrong extraction, noise, or explicitly rejected. Never surfaces again.

    Delivered vs Completed vs Closed:
    - delivered = the thing was sent/done (system-detected, may need user confirmation)
    - completed = user confirmed it's fully done
    - closed = no longer needs attention (broader)
    """

    proposed = "proposed"
    needs_clarification = "needs_clarification"
    active = "active"
    confirmed = "confirmed"
    in_progress = "in_progress"
    dormant = "dormant"
    delivered = "delivered"
    completed = "completed"
    canceled = "canceled"
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
class UserRelationship(str, enum.Enum):
    mine = "mine"
    contributing = "contributing"
    watching = "watching"


class SpeechAct(str, enum.Enum):
    request = "request"
    self_commitment = "self_commitment"
    acceptance = "acceptance"
    status_update = "status_update"
    completion = "completion"
    cancellation = "cancellation"
    decline = "decline"
    reassignment = "reassignment"
    informational = "informational"


class Direction(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    unknown = "unknown"


class ParticipantRole(str, enum.Enum):
    sender = "sender"
    to = "to"
    cc = "cc"
    bcc = "bcc"
    reply_to = "reply_to"
    unknown = "unknown"


class NormalizationFlag(str, enum.Enum):
    missing_subject = "missing_subject"
    missing_text_body = "missing_text_body"
    html_only_body = "html_only_body"
    quoted_text_detected = "quoted_text_detected"
    signature_detected = "signature_detected"
    thread_context_unavailable = "thread_context_unavailable"
    attachment_present = "attachment_present"
    malformed_headers = "malformed_headers"
    sender_unresolved = "sender_unresolved"
    multiple_possible_authored_blocks = "multiple_possible_authored_blocks"


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
