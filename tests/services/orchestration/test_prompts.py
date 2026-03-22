"""Tests for prompt template builders — verify structure and versioning."""

from app.services.orchestration.prompts import (
    candidate_gate,
    escalation,
    extraction,
    speech_act,
)


class TestPromptVersioning:
    def test_all_templates_have_ids(self):
        for module in [candidate_gate, speech_act, extraction, escalation]:
            assert hasattr(module, "TEMPLATE_ID")
            assert hasattr(module, "TEMPLATE_VERSION")
            assert module.TEMPLATE_ID
            assert module.TEMPLATE_VERSION.startswith("v")

    def test_unique_template_ids(self):
        ids = [
            candidate_gate.TEMPLATE_ID,
            speech_act.TEMPLATE_ID,
            extraction.TEMPLATE_ID,
            escalation.TEMPLATE_ID,
        ]
        assert len(ids) == len(set(ids)), f"Duplicate template IDs: {ids}"


class TestCandidateGatePrompt:
    def test_system_prompt_has_schema(self):
        assert "candidate_type" in candidate_gate.SYSTEM_PROMPT
        assert "confidence" in candidate_gate.SYSTEM_PROMPT
        assert "rationale_short" in candidate_gate.SYSTEM_PROMPT

    def test_build_user_prompt(self):
        prompt = candidate_gate.build_user_prompt(
            latest_authored_text="I'll send the report",
            prior_context_text="Previous context",
            source_type="email",
            subject="Report",
            direction="inbound",
        )
        assert "I'll send the report" in prompt
        assert "email" in prompt
        assert "Report" in prompt
        assert "inbound" in prompt
        assert "Previous context" in prompt

    def test_build_user_prompt_minimal(self):
        prompt = candidate_gate.build_user_prompt(
            latest_authored_text="Hello",
            prior_context_text=None,
            source_type="slack",
            subject=None,
            direction=None,
        )
        assert "Hello" in prompt
        assert "slack" in prompt
        assert "Prior context" not in prompt


class TestSpeechActPrompt:
    def test_system_prompt_has_all_acts(self):
        for act in ["request", "self_commitment", "acceptance", "delegation",
                     "update", "completion", "suggestion", "information", "unclear"]:
            assert act in speech_act.SYSTEM_PROMPT

    def test_build_user_prompt(self):
        prompt = speech_act.build_user_prompt(
            latest_authored_text="I'll do it",
            prior_context_text=None,
            source_type="email",
            subject="Task",
            direction="outbound",
            candidate_type="commitment_candidate",
            gate_confidence=0.85,
        )
        assert "commitment_candidate" in prompt
        assert "0.85" in prompt


class TestExtractionPrompt:
    def test_system_prompt_has_fields(self):
        for field in ["owner_text", "deliverable_text", "timing_text",
                       "evidence_span", "evidence_source"]:
            assert field in extraction.SYSTEM_PROMPT

    def test_system_prompt_has_critical_rules(self):
        assert "CRITICAL RULES" in extraction.SYSTEM_PROMPT
        assert "PRIORITIZE" in extraction.SYSTEM_PROMPT
        assert "Do NOT invent" in extraction.SYSTEM_PROMPT


class TestEscalationPrompt:
    def test_system_prompt_has_schema(self):
        assert "resolved" in escalation.SYSTEM_PROMPT
        assert "updated_gate" in escalation.SYSTEM_PROMPT
        assert "confidence_delta" in escalation.SYSTEM_PROMPT

    def test_build_user_prompt_with_questions(self):
        prompt = escalation.build_user_prompt(
            latest_authored_text="Maybe I should send it",
            prior_context_text=None,
            source_type="email",
            subject="Report",
            gate_output={"candidate_type": "ambiguous_action_candidate", "confidence": 0.45},
            speech_act_output={"speech_act": "suggestion", "confidence": 0.40},
            extraction_output=None,
            uncertainty_questions=["Is this a real commitment?"],
        )
        assert "ambiguous_action_candidate" in prompt
        assert "Is this a real commitment?" in prompt
