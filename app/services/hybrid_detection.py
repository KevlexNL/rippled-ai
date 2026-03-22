"""Hybrid Detection Service — Phase C1.

Combines deterministic detection results with model-assisted classification.
The deterministic pipeline runs first (in app/services/detection/detector.py).
This service processes candidates afterwards, adding model analysis for the
ambiguous confidence zone.

Decision thresholds (from WO):
    - confidence >= 0.75: skip model (high-confidence deterministic accept)
    - confidence < 0.35: skip model (clearly not a commitment)
    - 0.35 <= confidence < 0.75: call model (ambiguous zone)

Model decision rules:
    - Model says commitment, confidence > 0.6: promote (model-assisted)
    - Model says not-commitment, confidence > 0.7: demote (model-overridden)
    - Otherwise: keep deterministic result

Public API:
    service = HybridDetectionService(model_service=ModelDetectionService(...))
    result = service.process(candidate)
    # Apply result dict to DB: candidate.model_confidence = result["model_confidence"], etc.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.services.model_detection import ModelDetectionService, ModelDetectionResult

logger = logging.getLogger(__name__)

# Confidence zone boundaries
AMBIGUOUS_LOWER = Decimal("0.35")
AMBIGUOUS_UPPER = Decimal("0.75")

# Model decision thresholds
MODEL_PROMOTE_THRESHOLD = 0.6
MODEL_DEMOTE_THRESHOLD = 0.7


def _empty_result() -> dict[str, Any]:
    return {
        "detection_method": "deterministic",
        "model_called": False,
        "was_discarded": False,
        "discard_reason": None,
        "model_confidence": None,
        "model_classification": None,
        "model_explanation": None,
        "model_called_at": None,
    }


class HybridDetectionService:
    """Applies model-assisted detection on top of deterministic candidates.

    Args:
        model_service: ModelDetectionService instance. Pass None to disable
                       model calls (all candidates fall through deterministically).
    """

    def __init__(self, model_service: ModelDetectionService | None) -> None:
        self._model = model_service

    def process(self, candidate: Any, user_name: str | None = None, user_email: str | None = None) -> dict[str, Any]:
        """Process a candidate through the hybrid pipeline.

        Args:
            candidate: CommitmentCandidate ORM object with .confidence_score.
            user_name: Display name of the logged-in user (for relationship detection).
            user_email: Email of the logged-in user (for relationship detection).

        Returns:
            Dict with keys to update on the candidate DB record:
                detection_method, model_called, was_discarded, discard_reason,
                model_confidence, model_classification, model_explanation, model_called_at,
                deliverable, counterparty, user_relationship, structure_complete
        """
        result = _empty_result()

        confidence: Decimal = candidate.confidence_score or Decimal("0")

        # Skip model for clear cases
        if confidence >= AMBIGUOUS_UPPER or confidence < AMBIGUOUS_LOWER:
            logger.debug(
                "Candidate %s confidence=%s — skipping model (outside ambiguous zone)",
                getattr(candidate, "id", "?"), confidence,
            )
            return result

        # No model service configured
        if self._model is None:
            logger.debug(
                "Candidate %s in ambiguous zone but model_service not configured",
                getattr(candidate, "id", "?"),
            )
            return result

        # Call model
        result["model_called"] = True
        try:
            model_result: ModelDetectionResult | None = self._model.classify(candidate, user_name=user_name, user_email=user_email)
        except Exception as exc:
            logger.error(
                "HybridDetectionService: unexpected error from model for candidate %s: %s",
                getattr(candidate, "id", "?"), exc,
            )
            model_result = None

        if model_result is None:
            logger.warning(
                "Model returned None for candidate %s — keeping deterministic result",
                getattr(candidate, "id", "?"),
            )
            return result

        result["model_called_at"] = datetime.now(timezone.utc)
        result["model_confidence"] = model_result.confidence
        result["model_explanation"] = model_result.explanation

        # Pass through audit metadata from model result
        result["audit_raw_prompt"] = model_result.raw_prompt
        result["audit_raw_response"] = model_result.raw_response
        result["audit_parsed_result"] = model_result.parsed_result
        result["audit_tokens_in"] = model_result.tokens_in
        result["audit_tokens_out"] = model_result.tokens_out
        result["audit_model"] = model_result.model
        result["audit_duration_ms"] = model_result.duration_ms
        result["audit_prompt_version"] = model_result.prompt_version
        result["audit_error_detail"] = model_result.error_detail

        # v3: Pass through commitment structure fields
        result["deliverable"] = model_result.deliverable
        result["counterparty"] = model_result.counterparty
        result["user_relationship"] = model_result.user_relationship
        result["structure_complete"] = model_result.structure_complete
        # v4: Pass through requester + beneficiary
        result["requester"] = model_result.requester
        result["beneficiary"] = model_result.beneficiary

        # Apply decision rules
        if model_result.is_commitment and model_result.confidence > MODEL_PROMOTE_THRESHOLD:
            result["detection_method"] = "model-assisted"
            result["model_classification"] = "commitment"

        elif not model_result.is_commitment and model_result.confidence > MODEL_DEMOTE_THRESHOLD:
            result["detection_method"] = "model-overridden"
            result["model_classification"] = "not-commitment"
            result["was_discarded"] = True
            result["discard_reason"] = "model-overridden"

        else:
            # Model uncertain — keep deterministic result
            result["detection_method"] = "deterministic"
            result["model_classification"] = "uncertain"

        logger.info(
            "Hybrid detection candidate=%s confidence=%s model_confidence=%.2f detection_method=%s",
            getattr(candidate, "id", "?"),
            confidence,
            model_result.confidence,
            result["detection_method"],
        )

        return result
