"""Tests for StageLogger — persistence of pipeline runs and stage results."""

import pytest
from unittest.mock import MagicMock, call

from app.services.orchestration.contracts import (
    CandidateGateResult,
    CandidateType,
    CommitmentExtractionResult,
    EligibilityReason,
    EligibilityResult,
    EvidenceSource,
    OwnerResolution,
    PipelineResult,
    PipelineSpeechAct,
    RoutingAction,
    RoutingDecision,
    SpeechActResult,
)
from app.services.orchestration.stage_logger import StageLogger


class TestStageLoggerCreateRun:
    def test_creates_run_record(self):
        db = MagicMock()
        logger = StageLogger(db)

        run = logger.create_run("sig-001", "v1.0.0")

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert run.normalized_signal_id == "sig-001"
        assert run.pipeline_version == "v1.0.0"
        assert run.status == "running"


class TestStageLoggerLogStage:
    def test_logs_successful_stage(self):
        db = MagicMock()
        logger = StageLogger(db)

        stage = logger.log_stage(
            run_id="run-001",
            stage_name="eligibility",
            stage_order=0,
            status="success",
            input_data={"signal_id": "sig-001"},
            output_data={"eligible": True, "reason": "ok"},
        )

        db.add.assert_called_once()
        assert stage.stage_name == "eligibility"
        assert stage.stage_order == 0
        assert stage.status == "success"
        assert stage.input_json == {"signal_id": "sig-001"}
        assert stage.output_json == {"eligible": True, "reason": "ok"}

    def test_logs_failed_stage_with_error(self):
        db = MagicMock()
        logger = StageLogger(db)

        stage = logger.log_stage(
            run_id="run-001",
            stage_name="candidate_gate",
            stage_order=1,
            status="failed",
            input_data={"text": "hello"},
            error={"error": "API timeout"},
            model_name="gpt-4.1-mini",
            model_provider="openai",
        )

        assert stage.status == "failed"
        assert stage.error_json == {"error": "API timeout"}
        assert stage.model_name == "gpt-4.1-mini"


class TestStageLoggerCompleteRun:
    def test_completes_with_routing(self):
        db = MagicMock()
        logger = StageLogger(db)

        run = MagicMock()
        routing = RoutingDecision(
            action=RoutingAction.create_candidate_record,
            reason_code="strong_extraction",
            summary="test",
        )

        logger.complete_run(run, "success", routing)

        assert run.status == "success"
        assert run.final_routing_action == "create_candidate_record"
        assert run.final_routing_reason == "strong_extraction"
        assert run.completed_at is not None


class TestStageLoggerCandidateRecord:
    def test_creates_record_for_candidate_action(self):
        db = MagicMock()
        logger = StageLogger(db)

        pipeline_result = PipelineResult(
            run_id="run-001",
            normalized_signal_id="sig-001",
            pipeline_version="v1.0.0",
            eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
            candidate_gate=CandidateGateResult(
                candidate_type=CandidateType.commitment_candidate,
                confidence=0.85,
                rationale_short="test",
            ),
            speech_act=SpeechActResult(
                speech_act=PipelineSpeechAct.self_commitment,
                confidence=0.9,
                rationale_short="test",
            ),
            extraction=CommitmentExtractionResult(
                candidate_present=True,
                owner_text="Alice",
                owner_resolution=OwnerResolution.sender,
                deliverable_text="report",
                evidence_source=EvidenceSource.latest_authored_text,
                owner_confidence=0.9,
                deliverable_confidence=0.85,
                timing_confidence=0.5,
                target_confidence=0.5,
            ),
            final_routing=RoutingDecision(
                action=RoutingAction.create_candidate_record,
                reason_code="strong",
                summary="test",
            ),
        )

        record = logger.create_candidate_record("sig-001", "run-001", pipeline_result)

        assert record is not None
        db.add.assert_called_once()
        assert record.candidate_type == "commitment_candidate"
        assert record.speech_act == "self_commitment"
        assert record.owner_text == "Alice"
        assert record.routing_action == "create_candidate_record"

    def test_skips_record_for_discard_action(self):
        db = MagicMock()
        logger = StageLogger(db)

        pipeline_result = PipelineResult(
            run_id="run-001",
            normalized_signal_id="sig-001",
            pipeline_version="v1.0.0",
            eligibility=EligibilityResult(eligible=True, reason=EligibilityReason.ok),
            final_routing=RoutingDecision(
                action=RoutingAction.discard,
                reason_code="gate_none",
                summary="test",
            ),
        )

        record = logger.create_candidate_record("sig-001", "run-001", pipeline_result)
        assert record is None
        db.add.assert_not_called()
