"""SignalOrchestrator — runs the staged pipeline in order.

Enforces preconditions between stages, manages escalation,
and delegates persistence to StageLogger.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.config import get_orchestration_config
from app.services.orchestration.contracts import (
    CandidateGateResult,
    CommitmentExtractionResult,
    EligibilityResult,
    EscalationResolution,
    PipelineResult,
    RoutingAction,
    RoutingDecision,
    SpeechActResult,
)
from app.services.orchestration.stage_logger import StageLogger
from app.services.orchestration.stages import candidate_gate as gate_executor
from app.services.orchestration.stages import escalation as escalation_executor
from app.services.orchestration.stages import extraction as extraction_executor
from app.services.orchestration.stages import speech_act as speech_act_executor
from app.services.orchestration.stages.eligibility import check_eligibility
from app.services.orchestration.stages.extraction import should_run_extraction
from app.services.orchestration.stages.llm_caller import LLMCallResult
from app.services.orchestration.stages.routing import compute_routing_decision

logger = logging.getLogger(__name__)


class _NullStageLogger:
    """No-op logger for dry-run mode — skips all DB persistence."""

    def create_run(self, **kwargs):
        return None

    def log_stage(self, **kwargs):
        return None

    def complete_run(self, *args, **kwargs):
        return None

    def create_candidate_record(self, *args, **kwargs):
        return None


class SignalOrchestrator:
    """Runs the staged orchestration pipeline on a NormalizedSignal."""

    def __init__(self, db: Session | None, dry_run: bool = False):
        self._db = db
        self._dry_run = dry_run
        self._logger = _NullStageLogger() if dry_run else StageLogger(db)
        self._config = get_orchestration_config()

    def process(self, signal: NormalizedSignal) -> PipelineResult:
        """Execute the full pipeline. Returns PipelineResult with all stage outputs."""
        signal_id = signal.id or signal.signal_id

        run = self._logger.create_run(
            normalized_signal_id=signal_id,
            pipeline_version=self._config.pipeline_version,
        )
        run_id = f"dry-run-{uuid.uuid4()}" if run is None else (run.id or str(uuid.uuid4()))

        result = PipelineResult(
            run_id=run_id,
            normalized_signal_id=signal_id,
            pipeline_version=self._config.pipeline_version,
            eligibility=EligibilityResult(eligible=False, reason="ok"),  # placeholder
        )

        try:
            # ── Stage 0: Eligibility ──
            eligibility = self._run_eligibility(run_id, signal)
            result.eligibility = eligibility

            if not eligibility.eligible:
                routing = RoutingDecision(
                    action=RoutingAction.discard,
                    reason_code=f"ineligible:{eligibility.reason.value}",
                    summary=f"Signal ineligible: {eligibility.reason.value}",
                )
                result.routing = routing
                result.final_routing = routing
                self._logger.complete_run(run, "success", routing)
                return result

            # ── Stage 1: Candidate gate ──
            gate_result, gate_error = self._run_candidate_gate(run_id, signal)
            result.candidate_gate = gate_result

            if gate_result is None:
                detail = gate_error or "unknown"
                result.error = f"Candidate gate stage failed: {detail}"
                result.stage_errors["candidate_gate"] = detail
                self._logger.complete_run(run, "failed", error={"stage": "candidate_gate", "error": result.error})
                return result

            # ── Stage 2: Speech-act classification ──
            speech_act_result, speech_error = self._run_speech_act(run_id, signal, gate_result)
            result.speech_act = speech_act_result
            if speech_error:
                result.stage_errors["speech_act"] = speech_error

            # ── Stage 3: Commitment extraction (conditional) ──
            extraction_result = None
            if speech_act_result and should_run_extraction(gate_result, speech_act_result):
                extraction_result, extraction_error = self._run_extraction(run_id, signal, gate_result, speech_act_result)
                result.extraction = extraction_result
                if extraction_error:
                    result.stage_errors["extraction"] = extraction_error

            # ── Stage 4: Deterministic routing ──
            routing = compute_routing_decision(gate_result, speech_act_result, extraction_result)
            result.routing = routing

            self._logger.log_stage(
                run_id=run_id,
                stage_name="routing",
                stage_order=4,
                status="success",
                input_data={
                    "gate": gate_result.model_dump(),
                    "speech_act": speech_act_result.model_dump() if speech_act_result else None,
                    "extraction": extraction_result.model_dump() if extraction_result else None,
                },
                output_data=routing.model_dump(),
            )

            # ── Stage 5: Escalation (if routing says so) ──
            final_routing = routing
            if routing.action == RoutingAction.escalate_model:
                escalation, escalation_error = self._run_escalation(
                    run_id, signal, gate_result, speech_act_result, extraction_result,
                )
                result.escalation = escalation
                if escalation_error:
                    result.stage_errors["escalation"] = escalation_error

                if escalation and escalation.resolved:
                    # Apply overrides
                    effective_gate = escalation.updated_gate or gate_result
                    effective_speech = escalation.updated_speech_act or speech_act_result
                    effective_extraction = escalation.updated_extraction or extraction_result

                    result.candidate_gate = effective_gate
                    result.speech_act = effective_speech
                    result.extraction = effective_extraction

                    # Re-route with updated data
                    final_routing = compute_routing_decision(
                        effective_gate, effective_speech, effective_extraction,
                    )
                else:
                    # Escalation didn't resolve — observe quietly
                    final_routing = RoutingDecision(
                        action=RoutingAction.observe_quietly,
                        reason_code="escalation_unresolved",
                        summary="Escalation could not resolve ambiguity, observing quietly",
                    )

            result.final_routing = final_routing

            # ── Stage 6: Persistence ──
            self._logger.create_candidate_record(signal_id, run_id, result)
            self._logger.complete_run(run, "success", final_routing)

            logger.info(
                "Pipeline complete: signal=%s action=%s reason=%s",
                signal_id,
                final_routing.action.value,
                final_routing.reason_code,
            )

        except Exception as exc:
            logger.exception("Pipeline error: signal=%s error=%s", signal_id, exc)
            result.error = str(exc)
            self._logger.complete_run(run, "failed", error={"error": str(exc)})

        return result

    # ── Private stage runners ──

    def _run_eligibility(self, run_id: str, signal: NormalizedSignal) -> EligibilityResult:
        eligibility = check_eligibility(signal)
        self._logger.log_stage(
            run_id=run_id,
            stage_name="eligibility",
            stage_order=0,
            status="success",
            input_data={"signal_id": signal.signal_id, "source_type": signal.source_type},
            output_data=eligibility.model_dump(),
        )
        return eligibility

    def _run_candidate_gate(
        self, run_id: str, signal: NormalizedSignal,
    ) -> tuple[CandidateGateResult | None, str | None]:
        llm_result: LLMCallResult = gate_executor.execute_candidate_gate(signal)
        prompt_meta = gate_executor.get_prompt_metadata()

        self._logger.log_stage(
            run_id=run_id,
            stage_name="candidate_gate",
            stage_order=1,
            status="success" if llm_result.success else "failed",
            input_data={"latest_authored_text": signal.latest_authored_text[:200]},
            output_data=llm_result.parsed.model_dump() if llm_result.parsed else None,
            model_provider=llm_result.model_provider,
            model_name=llm_result.model_name,
            prompt_template_id=prompt_meta["template_id"],
            prompt_version=prompt_meta["version"],
            duration_ms=llm_result.duration_ms,
            token_usage={"in": llm_result.tokens_in, "out": llm_result.tokens_out},
            error={"error": llm_result.error} if llm_result.error else None,
        )

        if llm_result.success:
            return llm_result.parsed, None
        return None, llm_result.error

    def _run_speech_act(
        self,
        run_id: str,
        signal: NormalizedSignal,
        gate_result: CandidateGateResult,
    ) -> tuple[SpeechActResult | None, str | None]:
        llm_result = speech_act_executor.execute_speech_act(signal, gate_result)
        prompt_meta = speech_act_executor.get_prompt_metadata()

        self._logger.log_stage(
            run_id=run_id,
            stage_name="speech_act",
            stage_order=2,
            status="success" if llm_result.success else "failed",
            input_data={"gate_result": gate_result.model_dump()},
            output_data=llm_result.parsed.model_dump() if llm_result.parsed else None,
            model_provider=llm_result.model_provider,
            model_name=llm_result.model_name,
            prompt_template_id=prompt_meta["template_id"],
            prompt_version=prompt_meta["version"],
            duration_ms=llm_result.duration_ms,
            token_usage={"in": llm_result.tokens_in, "out": llm_result.tokens_out},
            error={"error": llm_result.error} if llm_result.error else None,
        )

        if llm_result.success:
            return llm_result.parsed, None
        return None, llm_result.error

    def _run_extraction(
        self,
        run_id: str,
        signal: NormalizedSignal,
        gate_result: CandidateGateResult,
        speech_act_result: SpeechActResult,
    ) -> tuple[CommitmentExtractionResult | None, str | None]:
        llm_result = extraction_executor.execute_extraction(signal, gate_result, speech_act_result)
        prompt_meta = extraction_executor.get_prompt_metadata()

        self._logger.log_stage(
            run_id=run_id,
            stage_name="extraction",
            stage_order=3,
            status="success" if llm_result.success else "failed",
            input_data={
                "speech_act": speech_act_result.model_dump(),
                "gate": gate_result.model_dump(),
            },
            output_data=llm_result.parsed.model_dump() if llm_result.parsed else None,
            model_provider=llm_result.model_provider,
            model_name=llm_result.model_name,
            prompt_template_id=prompt_meta["template_id"],
            prompt_version=prompt_meta["version"],
            duration_ms=llm_result.duration_ms,
            token_usage={"in": llm_result.tokens_in, "out": llm_result.tokens_out},
            error={"error": llm_result.error} if llm_result.error else None,
        )

        if llm_result.success:
            return llm_result.parsed, None
        return None, llm_result.error

    def _run_escalation(
        self,
        run_id: str,
        signal: NormalizedSignal,
        gate_result: CandidateGateResult,
        speech_act_result: SpeechActResult | None,
        extraction_result: CommitmentExtractionResult | None,
    ) -> tuple[EscalationResolution | None, str | None]:
        llm_result = escalation_executor.execute_escalation(
            signal, gate_result, speech_act_result, extraction_result,
        )
        prompt_meta = escalation_executor.get_prompt_metadata()

        self._logger.log_stage(
            run_id=run_id,
            stage_name="escalation",
            stage_order=5,
            status="success" if llm_result.success else "failed",
            input_data={
                "gate": gate_result.model_dump(),
                "speech_act": speech_act_result.model_dump() if speech_act_result else None,
                "extraction": extraction_result.model_dump() if extraction_result else None,
            },
            output_data=llm_result.parsed.model_dump() if llm_result.parsed else None,
            model_provider=llm_result.model_provider,
            model_name=llm_result.model_name,
            prompt_template_id=prompt_meta["template_id"],
            prompt_version=prompt_meta["version"],
            duration_ms=llm_result.duration_ms,
            token_usage={"in": llm_result.tokens_in, "out": llm_result.tokens_out},
            error={"error": llm_result.error} if llm_result.error else None,
        )

        if llm_result.success:
            return llm_result.parsed, None
        return None, llm_result.error
