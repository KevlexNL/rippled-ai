"""Detection audit — log which tier handled each detection.

Tracks tier_1 / tier_2 / tier_3 / pattern usage per source item
for cost analysis and funnel optimization.

Public API:
    create_audit_entry(...) -> dict
    write_audit_entry(db, ...) -> DetectionAudit
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.orm import DetectionAudit

# Cost per million tokens (USD) — update as pricing changes.
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5-20250514": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "gpt-4.1-mini": (0.40, 1.60),
}


def estimate_cost(
    model: str, tokens_in: int | None, tokens_out: int | None
) -> Decimal | None:
    """Estimate USD cost from token counts and model pricing."""
    if tokens_in is None or tokens_out is None:
        return None
    pricing = _MODEL_PRICING.get(model)
    if pricing is None:
        return None
    in_cost = (tokens_in / 1_000_000) * pricing[0]
    out_cost = (tokens_out / 1_000_000) * pricing[1]
    return Decimal(str(round(in_cost + out_cost, 6)))


def create_audit_entry(
    source_item_id: str,
    user_id: str,
    tier_used: str,
    matched_phrase: str | None = None,
    matched_sender: str | None = None,
    confidence: Decimal | None = None,
    commitment_created: bool = False,
    *,
    prompt_version: str | None = None,
    raw_prompt: str | None = None,
    raw_response: str | None = None,
    parsed_result: dict | list | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_estimate: Decimal | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    error_detail: str | None = None,
) -> dict:
    """Create an audit entry dict (for use without DB or for deferred write)."""
    return {
        "source_item_id": source_item_id,
        "user_id": user_id,
        "tier_used": tier_used,
        "matched_phrase": matched_phrase,
        "matched_sender": matched_sender,
        "confidence": confidence,
        "commitment_created": commitment_created,
        "prompt_version": prompt_version,
        "raw_prompt": raw_prompt,
        "raw_response": raw_response,
        "parsed_result": parsed_result,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_estimate": cost_estimate,
        "model": model,
        "duration_ms": duration_ms,
        "error_detail": error_detail,
    }


def write_audit_entry(
    db: Session,
    source_item_id: str,
    user_id: str,
    tier_used: str,
    matched_phrase: str | None = None,
    matched_sender: str | None = None,
    confidence: Decimal | None = None,
    commitment_created: bool = False,
    *,
    prompt_version: str | None = None,
    raw_prompt: str | None = None,
    raw_response: str | None = None,
    parsed_result: dict | list | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_estimate: Decimal | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    error_detail: str | None = None,
) -> DetectionAudit:
    """Write an audit row to the database."""
    entry = DetectionAudit(
        source_item_id=source_item_id,
        user_id=user_id,
        tier_used=tier_used,
        matched_phrase=matched_phrase,
        matched_sender=matched_sender,
        confidence=confidence,
        commitment_created=commitment_created,
        prompt_version=prompt_version,
        raw_prompt=raw_prompt,
        raw_response=raw_response,
        parsed_result=parsed_result,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=cost_estimate,
        model=model,
        duration_ms=duration_ms,
        error_detail=error_detail,
    )
    db.add(entry)
    db.flush()
    return entry
