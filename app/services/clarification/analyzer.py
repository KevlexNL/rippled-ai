"""Commitment candidate analyzer — Phase 04.

Inspects a CommitmentCandidate and produces an AnalysisResult describing:
- Which ambiguity issue types apply
- The overall severity
- Why this matters
- Observation window status
- Surface recommendation

Public API:
    analyze_candidate(candidate) -> AnalysisResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.models.enums import AmbiguityType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CRITICAL_ISSUES = {
    AmbiguityType.commitment_unclear,
    AmbiguityType.owner_missing,
    AmbiguityType.owner_vague_collective,
}

_VAGUE_TIME_PHRASES = ["soon", "later", "this week", "end of month", "after the"]

_DELIVERABLE_UNCLEAR_PHRASES = ["handle it", "sort it", "take care of it", "sort that"]

_TARGET_UNCLEAR_PHRASES = ["send that", "forward it", "update the doc", "update that"]

# Trigger classes that suggest implicit/unresolved commitments (commitment_unclear)
_IMPLICIT_TRIGGER_CLASSES = {
    "implicit_next_step",
    "implicit_unresolved_obligation",
    "pending_obligation",
}

_GENERIC_SPEAKER_PATTERN = re.compile(r"^Speaker\s+\d+$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    issue_types: list[AmbiguityType] = field(default_factory=list)
    issue_severity: str = "medium"
    why_this_matters: str = ""
    observation_window_status: str = "open"
    surface_recommendation: str = "do_nothing"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_critical(issue: AmbiguityType) -> bool:
    return issue in _CRITICAL_ISSUES


def _derive_context_type(candidate: Any) -> str:
    """Derive context_type from the candidate's context_window metadata."""
    ctx = candidate.context_window or {}
    if ctx.get("has_external_recipient"):
        return "external"
    return "internal"


def _has_named_speaker(candidate: Any) -> bool:
    """Return True if context_window contains a named (non-generic) speaker."""
    ctx = candidate.context_window or {}
    for turn in ctx.get("speaker_turns") or []:
        speaker = turn.get("speaker")
        if speaker and not _GENERIC_SPEAKER_PATTERN.match(speaker):
            return True
    return False


# ---------------------------------------------------------------------------
# Issue inference
# ---------------------------------------------------------------------------

def _infer_issues(candidate: Any) -> list[AmbiguityType]:
    issues: list[AmbiguityType] = []
    raw_text = (candidate.raw_text or "").lower()
    trigger_class = candidate.trigger_class or ""
    linked_entities = candidate.linked_entities or {}
    people: list = linked_entities.get("people", [])
    dates: list = linked_entities.get("dates", [])
    confidence = candidate.confidence_score or Decimal("0")

    # 1. commitment_unclear
    if (
        (candidate.is_explicit is False and confidence < Decimal("0.55"))
        or candidate.flag_reanalysis
        or trigger_class in _IMPLICIT_TRIGGER_CLASSES
    ):
        issues.append(AmbiguityType.commitment_unclear)

    # 2. owner_missing
    if "unresolved_obligation" in trigger_class:
        issues.append(AmbiguityType.owner_missing)
    elif not people and not _has_named_speaker(candidate):
        issues.append(AmbiguityType.owner_missing)

    # 3. owner_vague_collective
    collective_words = ["we'll", "we will", "we ", " us ", "team", "someone"]
    if (
        "collective_commitment" in trigger_class
        or any(w in raw_text for w in collective_words)
    ):
        issues.append(AmbiguityType.owner_vague_collective)

    # 4. timing_missing — no dates AND no vague time phrase
    if not dates and not any(vp in raw_text for vp in _VAGUE_TIME_PHRASES):
        issues.append(AmbiguityType.timing_missing)

    # 5. timing_vague
    if any(vp in raw_text for vp in _VAGUE_TIME_PHRASES):
        issues.append(AmbiguityType.timing_vague)

    # 6. deliverable_unclear
    if any(p in raw_text for p in _DELIVERABLE_UNCLEAR_PHRASES):
        issues.append(AmbiguityType.deliverable_unclear)

    # 7. target_unclear
    if any(p in raw_text for p in _TARGET_UNCLEAR_PHRASES):
        issues.append(AmbiguityType.target_unclear)

    # 8. timing_conflicting
    if trigger_class == "deadline_change":
        issues.append(AmbiguityType.timing_conflicting)

    # 9. status_unclear — delivery/blocker patterns signal uncertain completion state
    # TODO(signals-conflicting): add signals_conflicting AmbiguityType when multiple
    # contradictory delivery signals are detected in the same thread window.
    if trigger_class in ("delivery_signal", "blocker_signal"):
        issues.append(AmbiguityType.status_unclear)

    return issues


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

def _compute_severity(
    issue_types: list[AmbiguityType],
    context_type: str,
) -> str:
    critical = [i for i in issue_types if _is_critical(i)]
    if critical or len(issue_types) >= 3:
        severity = "high"
    else:
        severity = "medium"

    # Escalate to high if external + critical
    if context_type == "external" and critical:
        severity = "high"

    return severity


# ---------------------------------------------------------------------------
# Observation window status
# ---------------------------------------------------------------------------

def _compute_obs_status(
    candidate: Any,
    issue_types: list[AmbiguityType],
    context_type: str,
) -> str:
    critical = [i for i in issue_types if _is_critical(i)]

    # skipped: external + critical, OR priority_hint == high
    if (context_type == "external" and critical) or candidate.priority_hint == "high":
        return "skipped"

    # expired: observe_until is None or in the past
    observe_until = candidate.observe_until
    if observe_until is None or observe_until <= datetime.now(timezone.utc):
        return "expired"

    return "open"


# ---------------------------------------------------------------------------
# Surface recommendation
# ---------------------------------------------------------------------------

def _compute_surface_recommendation(
    issue_types: list[AmbiguityType],
    issue_severity: str,
    obs_status: str,
    context_type: str,
) -> str:
    critical = [i for i in issue_types if _is_critical(i)]

    # Override: all low severity → do_nothing (no low severity defined yet, but guard)
    if issue_severity == "low":
        return "do_nothing"

    if critical and context_type == "external":
        recommendation = "escalate"
    elif critical and obs_status == "expired":
        recommendation = "clarifications_view"
    elif critical and obs_status in ("open", "skipped"):
        recommendation = "do_nothing"
    elif not critical and obs_status == "expired":
        recommendation = "internal_only"
    else:
        recommendation = "do_nothing"

    # Override: non-critical + external → max clarifications_view
    if not critical and context_type == "external":
        if recommendation == "do_nothing":
            recommendation = "clarifications_view"

    return recommendation


# ---------------------------------------------------------------------------
# why_this_matters generation
# ---------------------------------------------------------------------------

def _build_why_this_matters(issue_types: list[AmbiguityType]) -> str:
    if not issue_types:
        return "No ambiguities detected."
    labels = [i.value.replace("_", " ") for i in issue_types]
    return f"Ambiguities detected: {', '.join(labels)}."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_candidate(candidate: Any) -> AnalysisResult:
    """Analyze a CommitmentCandidate for ambiguity issues.

    Args:
        candidate: A CommitmentCandidate ORM object (or compatible namespace).

    Returns:
        AnalysisResult with issue_types, severity, obs_status, recommendation.
    """
    context_type = _derive_context_type(candidate)
    issue_types = _infer_issues(candidate)
    issue_severity = _compute_severity(issue_types, context_type)
    obs_status = _compute_obs_status(candidate, issue_types, context_type)
    surface_recommendation = _compute_surface_recommendation(
        issue_types, issue_severity, obs_status, context_type
    )
    why_this_matters = _build_why_this_matters(issue_types)

    return AnalysisResult(
        issue_types=issue_types,
        issue_severity=issue_severity,
        why_this_matters=why_this_matters,
        observation_window_status=obs_status,
        surface_recommendation=surface_recommendation,
    )
