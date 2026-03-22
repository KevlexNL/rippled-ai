"""Orchestration pipeline configuration — model routing, thresholds, versions.

All policy thresholds and model selections live here, not in prompts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

PIPELINE_VERSION = "v1.0.0"


class ModelConfig(BaseModel):
    """Model selection for a single stage."""
    primary: str = "gpt-4.1-mini"
    fallback: str | None = None


class ModelRoutingConfig(BaseModel):
    """Per-stage model routing. Configurable via env or code."""
    candidate_gate: ModelConfig = Field(default_factory=lambda: ModelConfig(primary="gpt-4.1-mini"))
    speech_act: ModelConfig = Field(default_factory=lambda: ModelConfig(primary="gpt-4.1-mini"))
    extraction: ModelConfig = Field(default_factory=lambda: ModelConfig(primary="gpt-4.1-mini"))
    escalation: ModelConfig = Field(default_factory=lambda: ModelConfig(primary="gpt-4.1"))


class GateThresholds(BaseModel):
    """Candidate gate confidence thresholds."""
    discard_below: float = 0.30
    ambiguous_below: float = 0.60
    continue_above: float = 0.60


class EscalationThresholds(BaseModel):
    """Thresholds that trigger escalation to a stronger model."""
    gate_confidence_floor: float = 0.30
    gate_confidence_ceiling: float = 0.60
    speech_act_confidence_floor: float = 0.50
    extraction_owner_confidence_floor: float = 0.40
    extraction_deliverable_confidence_floor: float = 0.40


class StructuralSufficiencyConfig(BaseModel):
    """Minimum confidence for structural sufficiency (create_candidate_record)."""
    owner_confidence_min: float = 0.50
    deliverable_confidence_min: float = 0.50


class OrchestrationConfig(BaseModel):
    """Top-level orchestration configuration."""
    pipeline_version: str = PIPELINE_VERSION
    supported_source_types: list[str] = Field(default_factory=lambda: ["email", "slack", "meeting"])
    model_routing: ModelRoutingConfig = Field(default_factory=ModelRoutingConfig)
    gate_thresholds: GateThresholds = Field(default_factory=GateThresholds)
    escalation_thresholds: EscalationThresholds = Field(default_factory=EscalationThresholds)
    structural_sufficiency: StructuralSufficiencyConfig = Field(default_factory=StructuralSufficiencyConfig)
    max_llm_retries: int = 1


_default_config: OrchestrationConfig | None = None


def get_orchestration_config() -> OrchestrationConfig:
    """Return the singleton orchestration config."""
    global _default_config
    if _default_config is None:
        _default_config = OrchestrationConfig()
    return _default_config


def set_orchestration_config(config: OrchestrationConfig) -> None:
    """Override the orchestration config (useful for tests)."""
    global _default_config
    _default_config = config
