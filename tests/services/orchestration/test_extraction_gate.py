"""Tests for extraction gating logic — when should extraction run."""

import pytest

from app.services.orchestration.contracts import (
    CandidateGateResult,
    CandidateType,
    PipelineSpeechAct,
    SpeechActResult,
)
from app.services.orchestration.stages.extraction import should_run_extraction


def _gate(candidate_type="commitment_candidate", confidence=0.8):
    return CandidateGateResult(
        candidate_type=CandidateType(candidate_type),
        confidence=confidence,
        rationale_short="test",
    )


def _speech(speech_act="information", confidence=0.8):
    return SpeechActResult(
        speech_act=PipelineSpeechAct(speech_act),
        confidence=confidence,
        rationale_short="test",
    )


class TestShouldRunExtraction:
    def test_commitment_candidate_runs(self):
        assert should_run_extraction(_gate("commitment_candidate"), _speech("information")) is True

    def test_ambiguous_action_runs(self):
        assert should_run_extraction(_gate("ambiguous_action_candidate"), _speech("information")) is True

    def test_completion_candidate_with_information_skips(self):
        assert should_run_extraction(_gate("completion_candidate"), _speech("information")) is False

    def test_none_with_self_commitment_speech_act_runs(self):
        assert should_run_extraction(_gate("none"), _speech("self_commitment")) is True

    def test_none_with_acceptance_runs(self):
        assert should_run_extraction(_gate("none"), _speech("acceptance")) is True

    def test_none_with_delegation_runs(self):
        assert should_run_extraction(_gate("none"), _speech("delegation")) is True

    def test_none_with_request_runs(self):
        assert should_run_extraction(_gate("none"), _speech("request")) is True

    def test_none_with_update_skips(self):
        assert should_run_extraction(_gate("none"), _speech("update")) is False

    def test_none_with_suggestion_skips(self):
        assert should_run_extraction(_gate("none"), _speech("suggestion")) is False

    def test_none_with_unclear_skips(self):
        assert should_run_extraction(_gate("none"), _speech("unclear")) is False
