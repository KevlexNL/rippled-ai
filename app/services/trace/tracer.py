"""Core trace logic — inspect a source_item through each pipeline stage.

Public API:
    trace_source_item(source_item_id: str, db: Session) -> dict
    fetch_samples(source_type: str, count: int, db: Session) -> list[dict]
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import (
    CandidateCommitment,
    Clarification,
    Commitment,
    CommitmentCandidate,
    CommitmentSignal,
    DetectionAudit,
    SourceItem,
)
from app.services.detection.patterns import (
    get_patterns_for_source,
    get_suppression_patterns_for_source,
)

logger = logging.getLogger(__name__)


def _json_safe(val: Any) -> Any:
    """Make a value JSON-serializable."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def _row_to_dict(row: Any, fields: list[str]) -> dict:
    """Extract selected fields from an ORM row into a JSON-safe dict."""
    return {f: _json_safe(getattr(row, f, None)) for f in fields}


# ---------------------------------------------------------------------------
# Stage 1: Raw content
# ---------------------------------------------------------------------------

def _trace_raw(item: SourceItem) -> dict:
    return {
        "stage": "raw",
        "status": "loaded",
        "data": {
            "id": str(item.id),
            "source_type": item.source_type,
            "sender_name": item.sender_name,
            "sender_email": item.sender_email,
            "direction": item.direction,
            "occurred_at": _json_safe(item.occurred_at),
            "content_length": len(item.content or ""),
            "content_preview": (item.content or "")[:500],
            "has_attachment": item.has_attachment,
            "is_external": item.is_external_participant or False,
            "is_quoted_content": item.is_quoted_content,
            "seed_processed_at": _json_safe(item.seed_processed_at),
        },
    }


# ---------------------------------------------------------------------------
# Stage 2: Normalization
# ---------------------------------------------------------------------------

def _trace_normalization(item: SourceItem) -> dict:
    source_type = item.source_type
    content = item.content_normalized or item.content or ""
    raw_content = item.content or ""

    # Apply suppression to show what gets stripped
    suppression_patterns = get_suppression_patterns_for_source(source_type)
    suppressed_spans: list[dict] = []
    normalized = content
    for sp in suppression_patterns:
        for m in sp.pattern.finditer(normalized):
            suppressed_spans.append({
                "pattern": sp.name,
                "matched_text": m.group(0)[:100],
                "start": m.start(),
                "end": m.end(),
            })
        normalized = sp.pattern.sub(" ", normalized)

    return {
        "stage": "normalization",
        "status": "complete",
        "data": {
            "has_content_normalized": item.content_normalized is not None,
            "raw_length": len(raw_content),
            "normalized_length": len(normalized),
            "suppression_patterns_applied": len(suppression_patterns),
            "suppressed_spans": suppressed_spans[:20],
            "normalized_preview": normalized[:500],
        },
    }


# ---------------------------------------------------------------------------
# Stage 3: Pattern detection
# ---------------------------------------------------------------------------

def _trace_patterns(item: SourceItem) -> dict:
    source_type = item.source_type
    content = item.content_normalized or item.content or ""

    # Apply suppression first (same as detector.py)
    suppression_patterns = get_suppression_patterns_for_source(source_type)
    for sp in suppression_patterns:
        content = sp.pattern.sub(" ", content)

    patterns = get_patterns_for_source(source_type)
    matches: list[dict] = []
    for pattern in patterns:
        for m in pattern.pattern.finditer(content):
            trigger_text = m.group(0).strip()
            if not trigger_text:
                continue
            matches.append({
                "pattern_name": pattern.name,
                "trigger_class": pattern.trigger_class,
                "is_explicit": pattern.is_explicit,
                "base_confidence": pattern.base_confidence,
                "matched_text": trigger_text[:200],
                "position": m.start(),
            })

    return {
        "stage": "pattern_detection",
        "status": "matched" if matches else "no_match",
        "data": {
            "patterns_checked": len(patterns),
            "matches_found": len(matches),
            "matches": matches[:50],
        },
    }


# ---------------------------------------------------------------------------
# Stage 4: LLM detection (from audit records)
# ---------------------------------------------------------------------------

def _trace_llm_detection(item: SourceItem, db: Session) -> dict:
    audits = db.execute(
        select(DetectionAudit)
        .where(DetectionAudit.source_item_id == item.id)
        .order_by(DetectionAudit.created_at.desc())
    ).scalars().all()

    if not audits:
        return {
            "stage": "llm_detection",
            "status": "no_audit_records",
            "data": {"audits": []},
        }

    audit_data = []
    for a in audits:
        audit_data.append({
            "id": str(a.id),
            "tier_used": a.tier_used,
            "matched_phrase": a.matched_phrase,
            "confidence": _json_safe(a.confidence),
            "commitment_created": a.commitment_created,
            "prompt_version": a.prompt_version,
            "raw_prompt": a.raw_prompt,
            "raw_response": a.raw_response,
            "parsed_result": a.parsed_result,
            "model": a.model,
            "tokens_in": a.tokens_in,
            "tokens_out": a.tokens_out,
            "cost_estimate": _json_safe(a.cost_estimate),
            "duration_ms": a.duration_ms,
            "error_detail": a.error_detail,
            "created_at": _json_safe(a.created_at),
        })

    return {
        "stage": "llm_detection",
        "status": "found",
        "data": {"audits": audit_data},
    }


# ---------------------------------------------------------------------------
# Stage 5: Signal extraction (candidates)
# ---------------------------------------------------------------------------

_CANDIDATE_FIELDS = [
    "id", "source_type", "raw_text", "trigger_class", "is_explicit",
    "detection_explanation", "confidence_score", "priority_hint",
    "commitment_class_hint", "context_window", "linked_entities",
    "observe_until", "flag_reanalysis", "was_promoted", "was_discarded",
    "discard_reason", "model_confidence", "model_classification",
    "model_explanation", "detection_method", "created_at",
]


def _trace_extraction(item: SourceItem, db: Session) -> dict:
    candidates = db.execute(
        select(CommitmentCandidate)
        .where(CommitmentCandidate.originating_item_id == item.id)
        .order_by(CommitmentCandidate.created_at.asc())
    ).scalars().all()

    if not candidates:
        return {
            "stage": "extraction",
            "status": "no_candidates",
            "data": {"candidates": []},
        }

    return {
        "stage": "extraction",
        "status": "found",
        "data": {
            "candidate_count": len(candidates),
            "candidates": [
                _row_to_dict(c, _CANDIDATE_FIELDS) for c in candidates
            ],
        },
    }


# ---------------------------------------------------------------------------
# Stage 6: Candidate decision
# ---------------------------------------------------------------------------

def _trace_candidate_decision(item: SourceItem, db: Session) -> dict:
    candidates = db.execute(
        select(CommitmentCandidate)
        .where(CommitmentCandidate.originating_item_id == item.id)
    ).scalars().all()

    if not candidates:
        return {
            "stage": "candidate_decision",
            "status": "no_candidates",
            "data": {},
        }

    decisions = []
    for c in candidates:
        decision = "pending"
        reason = "not yet processed"
        if c.was_promoted:
            decision = "promoted"
            reason = f"confidence={_json_safe(c.confidence_score)}"
        elif c.was_discarded:
            decision = "discarded"
            reason = c.discard_reason or "unknown"

        decisions.append({
            "candidate_id": str(c.id),
            "decision": decision,
            "reason": reason,
            "confidence": _json_safe(c.confidence_score),
            "observe_until": _json_safe(c.observe_until),
        })

    promoted_count = sum(1 for d in decisions if d["decision"] == "promoted")
    return {
        "stage": "candidate_decision",
        "status": "promoted" if promoted_count > 0 else "not_promoted",
        "data": {
            "promoted_count": promoted_count,
            "decisions": decisions,
        },
    }


# ---------------------------------------------------------------------------
# Stage 7: Clarification
# ---------------------------------------------------------------------------

def _trace_clarification(item: SourceItem, db: Session) -> dict:
    # Find commitments linked to this item via candidates
    candidate_ids = db.execute(
        select(CommitmentCandidate.id)
        .where(CommitmentCandidate.originating_item_id == item.id)
    ).scalars().all()

    if not candidate_ids:
        return {
            "stage": "clarification",
            "status": "no_candidates",
            "data": {},
        }

    # Find commitment IDs linked to these candidates
    commitment_ids = db.execute(
        select(CandidateCommitment.commitment_id)
        .where(CandidateCommitment.candidate_id.in_(candidate_ids))
    ).scalars().all()

    if not commitment_ids:
        # Also check via commitment signals
        commitment_ids = db.execute(
            select(CommitmentSignal.commitment_id)
            .where(CommitmentSignal.source_item_id == item.id)
        ).scalars().all()

    if not commitment_ids:
        return {
            "stage": "clarification",
            "status": "no_commitments",
            "data": {},
        }

    clarifications = db.execute(
        select(Clarification)
        .where(Clarification.commitment_id.in_(commitment_ids))
        .order_by(Clarification.created_at.desc())
    ).scalars().all()

    if not clarifications:
        return {
            "stage": "clarification",
            "status": "no_clarification_records",
            "data": {},
        }

    clari_data = []
    for cl in clarifications:
        clari_data.append({
            "id": str(cl.id),
            "commitment_id": str(cl.commitment_id),
            "issue_types": cl.issue_types,
            "issue_severity": cl.issue_severity,
            "why_this_matters": cl.why_this_matters,
            "observation_window_status": cl.observation_window_status,
            "suggested_values": cl.suggested_values,
            "surface_recommendation": cl.surface_recommendation,
            "resolved_at": _json_safe(cl.resolved_at),
        })

    return {
        "stage": "clarification",
        "status": "found",
        "data": {"clarifications": clari_data},
    }


# ---------------------------------------------------------------------------
# Stage 8: Final state (commitment)
# ---------------------------------------------------------------------------

_COMMITMENT_FIELDS = [
    "id", "title", "description", "commitment_text", "commitment_type",
    "priority_class", "lifecycle_state", "resolved_owner", "resolved_deadline",
    "deliverable", "confidence_commitment", "confidence_owner",
    "confidence_deadline", "is_surfaced", "surfaced_as", "priority_score",
    "requester_name", "beneficiary_name", "user_relationship",
    "created_at", "state_changed_at",
]


def _trace_final_state(item: SourceItem, db: Session) -> dict:
    # Find commitments from candidates
    candidate_ids = db.execute(
        select(CommitmentCandidate.id)
        .where(CommitmentCandidate.originating_item_id == item.id)
    ).scalars().all()

    commitment_ids = set()
    if candidate_ids:
        cc_ids = db.execute(
            select(CandidateCommitment.commitment_id)
            .where(CandidateCommitment.candidate_id.in_(candidate_ids))
        ).scalars().all()
        commitment_ids.update(cc_ids)

    # Also check commitment_signals
    signal_ids = db.execute(
        select(CommitmentSignal.commitment_id)
        .where(CommitmentSignal.source_item_id == item.id)
    ).scalars().all()
    commitment_ids.update(signal_ids)

    if not commitment_ids:
        return {
            "stage": "final_state",
            "status": "no_commitment",
            "data": {},
        }

    commitments = db.execute(
        select(Commitment)
        .where(Commitment.id.in_(list(commitment_ids)))
    ).scalars().all()

    return {
        "stage": "final_state",
        "status": "commitment_created",
        "data": {
            "commitment_count": len(commitments),
            "commitments": [
                _row_to_dict(c, _COMMITMENT_FIELDS) for c in commitments
            ],
        },
    }


# ---------------------------------------------------------------------------
# Overall verdict
# ---------------------------------------------------------------------------

def _compute_verdict(stages: list[dict]) -> str:
    """Derive an overall verdict from stage results."""
    # Check not_processed first — if seed_processed_at is None, nothing ran
    raw = next((s for s in stages if s["stage"] == "raw"), None)
    if raw:
        processed = raw.get("data", {}).get("seed_processed_at")
        if not processed:
            return "not_processed"

    final = next((s for s in stages if s["stage"] == "final_state"), None)
    if final and final["status"] == "commitment_created":
        return "commitment_created"

    candidate = next((s for s in stages if s["stage"] == "candidate_decision"), None)
    if candidate:
        if candidate["status"] == "promoted":
            return "candidate_promoted"
        decisions = candidate.get("data", {}).get("decisions", [])
        if any(d["decision"] == "pending" for d in decisions):
            return "candidate_pending"
        if any(d["decision"] == "discarded" for d in decisions):
            return "rejected_as_noise"

    extraction = next((s for s in stages if s["stage"] == "extraction"), None)
    if extraction and extraction["status"] == "no_candidates":
        return "no_candidates_created"

    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trace_source_item(source_item_id: str, db: Session) -> dict:
    """Trace a source item through all pipeline stages.

    Returns a dict with:
        - source_item_id
        - verdict: overall outcome
        - stages: list of stage dicts with stage name, status, and data
    """
    item: SourceItem | None = db.get(SourceItem, source_item_id)
    if item is None:
        raise ValueError(f"SourceItem {source_item_id!r} not found")

    stages = [
        _trace_raw(item),
        _trace_normalization(item),
        _trace_patterns(item),
        _trace_llm_detection(item, db),
        _trace_extraction(item, db),
        _trace_candidate_decision(item, db),
        _trace_clarification(item, db),
        _trace_final_state(item, db),
    ]

    verdict = _compute_verdict(stages)

    return {
        "source_item_id": source_item_id,
        "verdict": verdict,
        "stages": stages,
    }


def fetch_samples(
    source_type: str | None,
    count: int,
    db: Session,
) -> list[dict]:
    """Fetch recent source items for sampling.

    Args:
        source_type: Filter by type (email, slack, meeting) or None for all.
        count: Max items to return.
        db: Sync SQLAlchemy session.

    Returns:
        List of dicts with id, source_type, sender, date, content preview, status.
    """
    q = select(SourceItem).where(
        SourceItem.is_quoted_content.is_(False),
    )
    if source_type:
        q = q.where(SourceItem.source_type == source_type)
    q = q.order_by(SourceItem.occurred_at.desc()).limit(count)

    items = db.execute(q).scalars().all()

    results = []
    for item in items:
        # Check processing status
        has_candidates = db.execute(
            select(CommitmentCandidate.id)
            .where(CommitmentCandidate.originating_item_id == item.id)
            .limit(1)
        ).scalar_one_or_none()

        status = "unprocessed"
        if item.seed_processed_at:
            status = "candidate_created" if has_candidates else "processed_no_match"

        results.append({
            "id": str(item.id),
            "source_type": item.source_type,
            "sender_name": item.sender_name,
            "sender_email": item.sender_email,
            "occurred_at": _json_safe(item.occurred_at),
            "content_preview": (item.content or "")[:200],
            "status": status,
        })

    return results
