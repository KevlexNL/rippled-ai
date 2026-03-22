"""Stage 6 — Persistence and logging.

Stores every stage run for auditing, debugging, replay, and iteration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.orm import (
    CandidateSignalRecord,
    SignalProcessingRun,
    SignalProcessingStageRun,
)
from app.services.orchestration.contracts import (
    PipelineResult,
    RoutingAction,
    RoutingDecision,
)

logger = logging.getLogger(__name__)


class StageLogger:
    """Persists orchestration pipeline runs and stage results."""

    def __init__(self, db: Session):
        self._db = db

    def create_run(
        self,
        normalized_signal_id: str,
        pipeline_version: str,
    ) -> SignalProcessingRun:
        """Create a new processing run record."""
        run = SignalProcessingRun(
            normalized_signal_id=normalized_signal_id,
            pipeline_version=pipeline_version,
            status="running",
        )
        self._db.add(run)
        self._db.flush()  # Get the ID
        return run

    def log_stage(
        self,
        run_id: str,
        stage_name: str,
        stage_order: int,
        status: str,
        input_data: dict,
        output_data: dict | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        prompt_template_id: str | None = None,
        prompt_version: str | None = None,
        duration_ms: int | None = None,
        token_usage: dict | None = None,
        error: dict | None = None,
    ) -> SignalProcessingStageRun:
        """Log a single stage execution."""
        stage_run = SignalProcessingStageRun(
            signal_processing_run_id=run_id,
            stage_name=stage_name,
            stage_order=stage_order,
            status=status,
            input_json=input_data,
            output_json=output_data,
            model_provider=model_provider,
            model_name=model_name,
            prompt_template_id=prompt_template_id,
            prompt_version=prompt_version,
            duration_ms=duration_ms,
            token_usage_json=token_usage,
            error_json=error,
        )
        self._db.add(stage_run)
        self._db.flush()
        return stage_run

    def complete_run(
        self,
        run: SignalProcessingRun,
        status: str,
        routing_decision: RoutingDecision | None = None,
        error: dict | None = None,
    ) -> None:
        """Mark a processing run as complete."""
        run.status = status
        run.completed_at = datetime.now(timezone.utc)
        if routing_decision:
            run.final_routing_action = routing_decision.action.value
            run.final_routing_reason = routing_decision.reason_code
        if error:
            run.error_json = error
        self._db.flush()

    def create_candidate_record(
        self,
        normalized_signal_id: str,
        run_id: str,
        pipeline_result: PipelineResult,
    ) -> CandidateSignalRecord | None:
        """Create a CandidateSignalRecord from pipeline outputs if routing warrants it."""
        final = pipeline_result.final_routing or pipeline_result.routing
        if not final:
            return None

        actionable = {
            RoutingAction.create_candidate_record,
            RoutingAction.create_completion_candidate,
        }
        if final.action not in actionable:
            return None

        extraction = pipeline_result.extraction
        speech_act = pipeline_result.speech_act
        gate = pipeline_result.candidate_gate

        record = CandidateSignalRecord(
            normalized_signal_id=normalized_signal_id,
            signal_processing_run_id=run_id,
            candidate_type=gate.candidate_type.value if gate else final.action.value,
            speech_act=speech_act.speech_act.value if speech_act else None,
            owner_resolution=extraction.owner_resolution.value if extraction else None,
            owner_text=extraction.owner_text if extraction else None,
            deliverable_text=extraction.deliverable_text if extraction else None,
            timing_text=extraction.timing_text if extraction else None,
            target_text=extraction.target_text if extraction else None,
            evidence_span=extraction.evidence_span if extraction else None,
            evidence_source=extraction.evidence_source.value if extraction else None,
            field_confidence_json={
                "owner": extraction.owner_confidence,
                "deliverable": extraction.deliverable_confidence,
                "timing": extraction.timing_confidence,
                "target": extraction.target_confidence,
            } if extraction else None,
            routing_action=final.action.value,
        )
        self._db.add(record)
        self._db.flush()

        logger.info(
            "Created candidate record: signal=%s type=%s action=%s",
            normalized_signal_id,
            record.candidate_type,
            record.routing_action,
        )
        return record
