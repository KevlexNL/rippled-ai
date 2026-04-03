"""Typed stage output contracts for the orchestration pipeline.

Every stage produces one of these Pydantic models. They are validated
before persistence and form the contract between stages.
"""

from __future__ import annotations

import enum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field


# ---------------------------------------------------------------------------
# Pipeline-specific enums (separate from app/models/enums.py DB enums)
# ---------------------------------------------------------------------------

class CandidateType(str, enum.Enum):
    none = "none"
    commitment_candidate = "commitment_candidate"
    completion_candidate = "completion_candidate"
    ambiguous_action_candidate = "ambiguous_action_candidate"


class PipelineSpeechAct(str, enum.Enum):
    """Speech-act labels for the orchestration pipeline (closed enum)."""
    request = "request"
    self_commitment = "self_commitment"
    acceptance = "acceptance"
    delegation = "delegation"
    update = "update"
    completion = "completion"
    suggestion = "suggestion"
    information = "information"
    unclear = "unclear"
    deadline_change = "deadline_change"
    collective_commitment = "collective_commitment"


# ---------------------------------------------------------------------------
# LLM synonym normalization — LLMs return creative synonyms for enum values
# ---------------------------------------------------------------------------

_CANDIDATE_TYPE_SYNONYMS: dict[str, str] = {
    "non_candidate": "none",
    "not_a_candidate": "none",
    "no_candidate": "none",
    "not_candidate": "none",
}

_SPEECH_ACT_SYNONYMS: dict[str, str] = {
    "inform": "information",
    "informational": "information",
    "info": "information",
}


def _normalize_candidate_type(v: Any) -> Any:
    if isinstance(v, str):
        return _CANDIDATE_TYPE_SYNONYMS.get(v, v)
    return v


def _normalize_speech_act(v: Any) -> Any:
    if isinstance(v, str):
        return _SPEECH_ACT_SYNONYMS.get(v, v)
    return v


NormalizedCandidateType = Annotated[CandidateType, BeforeValidator(_normalize_candidate_type)]
NormalizedSpeechAct = Annotated[PipelineSpeechAct, BeforeValidator(_normalize_speech_act)]


class ActorHint(str, enum.Enum):
    sender = "sender"
    recipient = "recipient"
    other = "other"
    unclear = "unclear"


class OwnerResolution(str, enum.Enum):
    sender = "sender"
    recipient = "recipient"
    third_party = "third_party"
    unknown = "unknown"
    not_applicable = "not_applicable"
    ambiguous = "ambiguous"


class EvidenceSource(str, enum.Enum):
    latest_authored_text = "latest_authored_text"
    prior_context_text = "prior_context_text"
    mixed = "mixed"
    unknown = "unknown"


class DuePrecision(str, enum.Enum):
    day = "day"
    week = "week"
    month = "month"
    vague = "vague"


class RoutingAction(str, enum.Enum):
    discard = "discard"
    observe_quietly = "observe_quietly"
    escalate_model = "escalate_model"
    create_candidate_record = "create_candidate_record"
    create_completion_candidate = "create_completion_candidate"
    mark_for_clarification_review = "mark_for_clarification_review"


class EligibilityReason(str, enum.Enum):
    ok = "ok"
    unsupported_source = "unsupported_source"
    missing_text = "missing_text"
    invalid_normalized_signal = "invalid_normalized_signal"
    bulk_mail_content = "bulk_mail_content"
    newsletter_sender = "newsletter_sender"
    automated_sender_header = "automated_sender_header"
    fragment_too_short = "fragment_too_short"


# ---------------------------------------------------------------------------
# Stage 0 — Eligibility check
# ---------------------------------------------------------------------------

class EligibilityResult(BaseModel):
    eligible: bool
    reason: EligibilityReason


# ---------------------------------------------------------------------------
# Stage 1 — Candidate gate
# ---------------------------------------------------------------------------

class CandidateGateResult(BaseModel):
    candidate_type: NormalizedCandidateType
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_short: str
    escalate_recommended: bool = False


# ---------------------------------------------------------------------------
# Stage 2 — Speech-act classification
# ---------------------------------------------------------------------------

class SpeechActResult(BaseModel):
    speech_act: NormalizedSpeechAct
    confidence: float = Field(ge=0.0, le=1.0)
    actor_hint: ActorHint = ActorHint.unclear
    target_hint: ActorHint = ActorHint.unclear
    rationale_short: str = ""
    ambiguity_flags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 3 — Commitment field extraction
# ---------------------------------------------------------------------------

class CommitmentExtractionResult(BaseModel):
    candidate_present: bool
    owner_text: str | None = None
    owner_resolution: OwnerResolution = OwnerResolution.unknown
    deliverable_text: str | None = None
    timing_text: str | None = None
    target_text: str | None = None
    evidence_span: str | None = None
    evidence_source: EvidenceSource = EvidenceSource.unknown
    owner_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    deliverable_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    timing_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity_flags: list[str] = Field(default_factory=list)
    due_precision: DuePrecision | None = None
    rationale_short: str = ""


# ---------------------------------------------------------------------------
# Stage 4 — Deterministic routing decision
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    action: RoutingAction
    reason_code: str
    summary: str


# ---------------------------------------------------------------------------
# Stage 5 — Optional escalation resolution
# ---------------------------------------------------------------------------

class EscalationResolution(BaseModel):
    resolved: bool
    updated_gate: CandidateGateResult | None = None
    updated_speech_act: SpeechActResult | None = None
    updated_extraction: CommitmentExtractionResult | None = None
    confidence_delta: float | None = None
    rationale_short: str = ""


# ---------------------------------------------------------------------------
# Aggregate pipeline result
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    """Aggregate output of a full orchestration run."""
    run_id: str
    normalized_signal_id: str
    pipeline_version: str
    eligibility: EligibilityResult
    candidate_gate: CandidateGateResult | None = None
    speech_act: SpeechActResult | None = None
    extraction: CommitmentExtractionResult | None = None
    routing: RoutingDecision | None = None
    escalation: EscalationResolution | None = None
    final_routing: RoutingDecision | None = None
    error: str | None = None
    stage_errors: dict[str, str] = Field(default_factory=dict)
