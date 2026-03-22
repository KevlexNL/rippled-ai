"""Tests for orchestration config."""

from app.services.orchestration.config import (
    GateThresholds,
    ModelConfig,
    ModelRoutingConfig,
    OrchestrationConfig,
    get_orchestration_config,
    set_orchestration_config,
)


class TestOrchestrationConfig:
    def test_defaults(self):
        config = OrchestrationConfig()
        assert config.pipeline_version == "v1.0.0"
        assert "email" in config.supported_source_types
        assert "slack" in config.supported_source_types
        assert "meeting" in config.supported_source_types

    def test_gate_thresholds(self):
        config = OrchestrationConfig()
        assert config.gate_thresholds.discard_below == 0.30
        assert config.gate_thresholds.ambiguous_below == 0.60
        assert config.gate_thresholds.continue_above == 0.60

    def test_model_routing_defaults(self):
        config = OrchestrationConfig()
        assert config.model_routing.candidate_gate.primary == "gpt-4.1-mini"
        assert config.model_routing.escalation.primary == "gpt-4.1"

    def test_custom_config(self):
        config = OrchestrationConfig(
            gate_thresholds=GateThresholds(discard_below=0.20),
            model_routing=ModelRoutingConfig(
                candidate_gate=ModelConfig(primary="gpt-4o-mini"),
            ),
        )
        assert config.gate_thresholds.discard_below == 0.20
        assert config.model_routing.candidate_gate.primary == "gpt-4o-mini"

    def test_singleton_override(self):
        original = get_orchestration_config()
        custom = OrchestrationConfig(pipeline_version="v2.0.0")
        set_orchestration_config(custom)

        assert get_orchestration_config().pipeline_version == "v2.0.0"

        # Reset
        set_orchestration_config(original)
