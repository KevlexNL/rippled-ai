"""Replay runner — reprocess signals through the orchestration pipeline.

Implements WO Deliverable C: Replay/debug support for orchestration.
Reloads normalized signals, reruns the current pipeline, and compares
outputs to prior runs for debugging and iteration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.models.enums import Direction
from app.models.orm import (
    NormalizedSignalORM,
    SignalProcessingRun,
    SignalProcessingStageRun,
)
from app.services.orchestration.contracts import PipelineResult
from app.services.orchestration.orchestrator import SignalOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class ReplayDiffField:
    field_name: str
    previous_value: str | None
    new_value: str | None

    @property
    def changed(self) -> bool:
        return self.previous_value != self.new_value


@dataclass
class ReplayComparison:
    """Stage-by-stage comparison between a prior run and a replay run."""
    normalized_signal_id: str
    prior_run_id: str | None
    replay_run_id: str
    diffs: list[ReplayDiffField] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(d.changed for d in self.diffs)

    def summary(self) -> str:
        if not self.has_changes:
            return "No differences"
        changed = [d for d in self.diffs if d.changed]
        lines = [f"  {d.field_name}: {d.previous_value!r} → {d.new_value!r}" for d in changed]
        return f"{len(changed)} field(s) changed:\n" + "\n".join(lines)


def _signal_orm_to_pydantic(orm: NormalizedSignalORM) -> NormalizedSignal:
    """Convert ORM NormalizedSignal to the Pydantic contract."""
    direction = None
    if orm.direction:
        try:
            direction = Direction(orm.direction)
        except ValueError:
            pass

    return NormalizedSignal(
        signal_id=orm.id,
        id=orm.id,
        raw_signal_ingest_id=orm.raw_signal_ingest_id,
        source_type=orm.source_type,
        source_subtype=orm.source_subtype,
        provider=orm.provider,
        provider_message_id=orm.provider_message_id,
        provider_thread_id=orm.provider_thread_id,
        provider_account_id=orm.provider_account_id,
        signal_timestamp=orm.signal_timestamp,
        authored_at=orm.authored_at,
        occurred_at=orm.signal_timestamp,
        direction=direction,
        is_inbound=orm.is_inbound,
        is_outbound=orm.is_outbound,
        subject=orm.subject,
        latest_authored_text=orm.latest_authored_text or "",
        prior_context_text=orm.prior_context_text,
        full_visible_text=orm.full_visible_text,
        html_present=orm.html_present,
        text_present=orm.text_present,
        normalization_version=orm.normalization_version,
    )


class OrchestrationReplayRunner:
    """Replay normalized signals through the current orchestration pipeline."""

    def __init__(self, db: Session):
        self._db = db
        self._orchestrator = SignalOrchestrator(db)

    def replay_by_signal_id(self, normalized_signal_id: str) -> tuple[PipelineResult, ReplayComparison]:
        """Replay a single normalized signal and compare with prior run."""
        orm_signal = self._db.get(NormalizedSignalORM, normalized_signal_id)
        if not orm_signal:
            raise ValueError(f"NormalizedSignal {normalized_signal_id} not found")

        signal = _signal_orm_to_pydantic(orm_signal)

        # Find the most recent prior run
        prior_run = self._db.execute(
            select(SignalProcessingRun)
            .where(SignalProcessingRun.normalized_signal_id == normalized_signal_id)
            .order_by(SignalProcessingRun.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Run current pipeline
        new_result = self._orchestrator.process(signal)

        # Build comparison
        comparison = self._build_comparison(
            normalized_signal_id,
            prior_run,
            new_result,
        )

        logger.info(
            "Replay complete: signal=%s prior_run=%s replay_run=%s changes=%s",
            normalized_signal_id,
            prior_run.id if prior_run else "none",
            new_result.run_id,
            comparison.has_changes,
        )

        return new_result, comparison

    def replay_by_raw_ingest_id(self, raw_ingest_id: str) -> list[tuple[PipelineResult, ReplayComparison]]:
        """Replay all normalized signals derived from a raw ingest."""
        signals = self._db.execute(
            select(NormalizedSignalORM)
            .where(NormalizedSignalORM.raw_signal_ingest_id == raw_ingest_id)
        ).scalars().all()

        if not signals:
            raise ValueError(f"No normalized signals found for raw_ingest_id {raw_ingest_id}")

        results = []
        for orm_signal in signals:
            result, comparison = self.replay_by_signal_id(orm_signal.id)
            results.append((result, comparison))

        return results

    def replay_recent(self, limit: int = 20) -> list[tuple[PipelineResult, ReplayComparison]]:
        """Replay the most recent normalized signals."""
        signals = self._db.execute(
            select(NormalizedSignalORM)
            .order_by(NormalizedSignalORM.created_at.desc())
            .limit(limit)
        ).scalars().all()

        results = []
        for orm_signal in signals:
            try:
                result, comparison = self.replay_by_signal_id(orm_signal.id)
                results.append((result, comparison))
            except Exception as exc:
                logger.error("Replay failed for signal %s: %s", orm_signal.id, exc)

        return results

    def _build_comparison(
        self,
        normalized_signal_id: str,
        prior_run: SignalProcessingRun | None,
        new_result: PipelineResult,
    ) -> ReplayComparison:
        """Compare prior run outputs with new pipeline result."""
        prior_stages: dict[str, dict] = {}

        if prior_run:
            stage_rows = self._db.execute(
                select(SignalProcessingStageRun)
                .where(SignalProcessingStageRun.signal_processing_run_id == prior_run.id)
                .order_by(SignalProcessingStageRun.stage_order)
            ).scalars().all()

            for stage in stage_rows:
                if stage.output_json:
                    prior_stages[stage.stage_name] = stage.output_json

        diffs = []

        # Compare key fields
        _diff_field(diffs, "candidate_type",
                    prior_stages.get("candidate_gate", {}).get("candidate_type"),
                    new_result.candidate_gate.candidate_type.value if new_result.candidate_gate else None)

        _diff_field(diffs, "speech_act",
                    prior_stages.get("speech_act", {}).get("speech_act"),
                    new_result.speech_act.speech_act.value if new_result.speech_act else None)

        _diff_field(diffs, "owner_resolution",
                    prior_stages.get("extraction", {}).get("owner_resolution"),
                    new_result.extraction.owner_resolution.value if new_result.extraction else None)

        _diff_field(diffs, "deliverable_text",
                    prior_stages.get("extraction", {}).get("deliverable_text"),
                    new_result.extraction.deliverable_text if new_result.extraction else None)

        _diff_field(diffs, "timing_text",
                    prior_stages.get("extraction", {}).get("timing_text"),
                    new_result.extraction.timing_text if new_result.extraction else None)

        _diff_field(diffs, "routing_action",
                    prior_run.final_routing_action if prior_run else None,
                    new_result.final_routing.action.value if new_result.final_routing else None)

        return ReplayComparison(
            normalized_signal_id=normalized_signal_id,
            prior_run_id=prior_run.id if prior_run else None,
            replay_run_id=new_result.run_id,
            diffs=diffs,
        )


def _diff_field(
    diffs: list[ReplayDiffField],
    name: str,
    old: str | None,
    new: str | None,
) -> None:
    diffs.append(ReplayDiffField(field_name=name, previous_value=old, new_value=new))
