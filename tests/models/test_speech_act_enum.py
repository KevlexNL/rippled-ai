"""Tests for SpeechAct enum — WO-RIPPLED-SPEECH-ACT-CLASSIFICATION."""

from app.models.enums import SpeechAct


class TestSpeechActEnum:
    def test_all_nine_values_exist(self):
        expected = {
            "request",
            "self_commitment",
            "acceptance",
            "status_update",
            "completion",
            "cancellation",
            "decline",
            "reassignment",
            "informational",
        }
        actual = {member.value for member in SpeechAct}
        assert actual == expected

    def test_is_string_enum(self):
        assert isinstance(SpeechAct.request, str)
        assert SpeechAct.request == "request"

    def test_self_commitment_value(self):
        assert SpeechAct.self_commitment == "self_commitment"

    def test_lookup_from_string(self):
        assert SpeechAct("request") == SpeechAct.request
        assert SpeechAct("informational") == SpeechAct.informational
