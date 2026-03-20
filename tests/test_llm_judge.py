"""Tests for LLM Judge service (WO-RIPPLED-LLM-JUDGE).

Verifies the weekly Sonnet-reviews-Haiku sweep:
- Skips gracefully without API key or audit rows
- Evaluates detection audits via Anthropic API
- Creates LlmJudgeRun row with summary stats
- Writes per-item SignalFeedback rows (reviewer_user_id = user_id)
- Creates prompt improvement WO when thresholds breached
- Handles API errors gracefully per-item
- Parses JSON from markdown code fences
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.llm_judge import (
    _parse_judge_response,
    run_llm_judge,
    TARGET_USER_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audit(
    audit_id: str = "aud-1",
    source_item_id: str = "si-1",
    raw_prompt: str = "Subject: Q3 review\nI'll send the deck by Friday.",
    raw_response: str = '{"commitments": ["send deck by Friday"]}',
    parsed_result: dict | None = None,
) -> MagicMock:
    audit = MagicMock()
    audit.id = audit_id
    audit.source_item_id = source_item_id
    audit.user_id = TARGET_USER_ID
    audit.raw_prompt = raw_prompt
    audit.raw_response = raw_response
    audit.parsed_result = parsed_result or {"commitments": ["send deck by Friday"]}
    audit.created_at = datetime.now(timezone.utc)
    return audit


def _make_anthropic_response(
    missed: list | None = None,
    false_positives: list | None = None,
    quality_rating: int = 4,
    prompt_suggestion: str = "",
    tokens_in: int = 500,
    tokens_out: int = 200,
) -> MagicMock:
    """Build a mock Anthropic messages.create response."""
    judge_output = {
        "missed": missed or [],
        "false_positives": false_positives or [],
        "quality_rating": quality_rating,
        "prompt_suggestion": prompt_suggestion,
    }
    resp = MagicMock()
    resp.usage.input_tokens = tokens_in
    resp.usage.output_tokens = tokens_out
    resp.content = [MagicMock(text=json.dumps(judge_output))]
    return resp


def _make_user_settings(has_key: bool = True) -> MagicMock:
    settings = MagicMock()
    settings.anthropic_api_key_encrypted = "encrypted-key" if has_key else None
    return settings


# ---------------------------------------------------------------------------
# Unit tests — _parse_judge_response
# ---------------------------------------------------------------------------

class TestParseJudgeResponse:
    def test_parses_plain_json(self):
        text = '{"missed": ["X"], "false_positives": [], "quality_rating": 4, "prompt_suggestion": ""}'
        result = _parse_judge_response(text)
        assert result["missed"] == ["X"]
        assert result["quality_rating"] == 4

    def test_strips_markdown_code_fence(self):
        text = '```json\n{"missed": [], "false_positives": ["Y"], "quality_rating": 5, "prompt_suggestion": ""}\n```'
        result = _parse_judge_response(text)
        assert result["false_positives"] == ["Y"]
        assert result["quality_rating"] == 5

    def test_handles_invalid_json(self):
        result = _parse_judge_response("not valid json at all")
        assert result["quality_rating"] == 3
        assert "parse_error" in result


# ---------------------------------------------------------------------------
# Integration tests — run_llm_judge
# ---------------------------------------------------------------------------

class TestRunLlmJudge:

    def _setup_db_mock(self, db, user_settings=None, audits=None):
        """Wire up db.execute().scalar_one_or_none / .scalars().all()."""
        calls = []

        def side_effect(stmt):
            result = MagicMock()
            call_index = len(calls)
            calls.append(stmt)

            if call_index == 0:
                # First call: UserSettings lookup
                result.scalar_one_or_none.return_value = user_settings
                return result
            else:
                # Second call: DetectionAudit query
                scalars = MagicMock()
                ordered = MagicMock()
                ordered.limit.return_value = scalars
                result.scalars.return_value.all.return_value = audits or []
                return result

        db.execute.side_effect = side_effect

    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_skips_without_api_key(self, mock_decrypt):
        db = MagicMock()
        self._setup_db_mock(db, user_settings=_make_user_settings(has_key=False))

        result = run_llm_judge(db)

        assert result["status"] == "skipped"
        assert "api key" in result["reason"].lower() or "API key" in result["reason"]

    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_skips_without_audit_rows(self, mock_decrypt):
        db = MagicMock()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[])

        result = run_llm_judge(db)

        assert result["status"] == "skipped"

    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_evaluates_audits_and_creates_judge_run(self, mock_decrypt, mock_anthropic_mod):
        """Core flow: evaluates audits, creates LlmJudgeRun, returns summary."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_anthropic_response(quality_rating=4)

        result = run_llm_judge(db)

        assert result["status"] == "complete"
        assert result["items_reviewed"] == 1
        # LlmJudgeRun should have been added to session
        added_objects = [call.args[0] for call in db.add.call_args_list]
        from app.models.orm import LlmJudgeRun
        judge_runs = [o for o in added_objects if isinstance(o, LlmJudgeRun)]
        assert len(judge_runs) == 1

    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_writes_per_item_signal_feedback(self, mock_decrypt, mock_anthropic_mod):
        """AC: Per-item feedback stored in signal_feedback table."""
        db = MagicMock()
        audit = _make_audit(audit_id="aud-42", source_item_id="si-99")
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_anthropic_response(
            missed=["follow up on budget"],
            false_positives=["greeting"],
            quality_rating=3,
        )

        run_llm_judge(db)

        from app.models.orm import SignalFeedback
        added_objects = [call.args[0] for call in db.add.call_args_list]
        feedbacks = [o for o in added_objects if isinstance(o, SignalFeedback)]
        assert len(feedbacks) == 1

        fb = feedbacks[0]
        assert fb.user_id == TARGET_USER_ID
        assert fb.reviewer_user_id == TARGET_USER_ID
        assert fb.detection_audit_id == "aud-42"
        assert fb.source_item_id == "si-99"
        assert fb.rating == 3
        assert "follow up on budget" in fb.missed_commitments
        assert "greeting" in fb.false_positives

    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_handles_api_error_gracefully(self, mock_decrypt, mock_anthropic_mod):
        """API failure on one item should not crash the whole run."""
        db = MagicMock()
        audit1 = _make_audit(audit_id="aud-ok")
        audit2 = _make_audit(audit_id="aud-fail")
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit1, audit2])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_anthropic_response(quality_rating=5),
            Exception("API timeout"),
        ]

        result = run_llm_judge(db)

        assert result["status"] == "complete"
        assert result["items_reviewed"] == 1  # only the successful one

    @patch("app.services.llm_judge._create_prompt_improvement_wo")
    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_creates_wo_on_low_quality(self, mock_decrypt, mock_anthropic_mod, mock_create_wo):
        """WO auto-created when avg quality < 3.5."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_anthropic_response(quality_rating=2)

        run_llm_judge(db)

        mock_create_wo.assert_called_once()

    @patch("app.services.llm_judge._create_prompt_improvement_wo")
    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_no_wo_when_quality_good(self, mock_decrypt, mock_anthropic_mod, mock_create_wo):
        """No WO when quality is above thresholds."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_anthropic_response(quality_rating=5)

        run_llm_judge(db)

        mock_create_wo.assert_not_called()

    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_cost_estimate_logged_in_result(self, mock_decrypt, mock_anthropic_mod):
        """AC: Task logs cost estimate."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_anthropic_response(
            tokens_in=1000, tokens_out=500
        )

        result = run_llm_judge(db)

        assert result["total_cost"] > 0

    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_no_signal_feedback_on_api_error(self, mock_decrypt, mock_anthropic_mod):
        """No SignalFeedback row written for items that errored."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        run_llm_judge(db)

        from app.models.orm import SignalFeedback
        added_objects = [call.args[0] for call in db.add.call_args_list]
        feedbacks = [o for o in added_objects if isinstance(o, SignalFeedback)]
        assert len(feedbacks) == 0

    @patch("app.services.llm_judge._create_prompt_improvement_wo")
    @patch("app.services.llm_judge.anthropic")
    @patch("app.services.llm_judge.decrypt_value", return_value="sk-test-key")
    def test_no_wo_when_zero_items_reviewed(self, mock_decrypt, mock_anthropic_mod, mock_create_wo):
        """No WO when all items errored — 0 items reviewed should not trigger threshold."""
        db = MagicMock()
        audit = _make_audit()
        self._setup_db_mock(db, user_settings=_make_user_settings(), audits=[audit])

        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        result = run_llm_judge(db)

        assert result["items_reviewed"] == 0
        mock_create_wo.assert_not_called()


# ---------------------------------------------------------------------------
# WO deduplication and judge prompt hardening
# ---------------------------------------------------------------------------

class TestWODeduplication:
    """WO sample failures should not show the same audit twice."""

    def test_wo_deduplicates_sample_failures(self):
        """An audit with both missed and false_positive should appear once in WO."""
        from app.services.llm_judge import _create_prompt_improvement_wo

        _create_prompt_improvement_wo(
            judge_run_id="run-1",
            items_reviewed=1,
            avg_quality=3.0,
            false_positives=1,
            false_negatives=1,
            suggestions=[],
            judge_outputs=[
                {
                    "audit_id": "aud-42",
                    "missed": ["follow up on budget"],
                    "false_positives": ["greeting"],
                    "quality_rating": 3,
                },
            ],
        )

        from pathlib import Path
        wo_path = Path("/home/kevinbeeftink/.openclaw/workspace/workorders/WO-RIPPLED-PROMPT-IMPROVEMENT_PENDING.md")
        content = wo_path.read_text()

        # Count occurrences of "### Audit aud-42" — should be exactly 1
        assert content.count("### Audit aud-42") == 1
        # But both missed and false_positives should be present
        assert "follow up on budget" in content
        assert "greeting" in content


class TestJudgePromptClassificationLabels:
    """Judge prompt should instruct evaluator about classification labels."""

    def test_judge_prompt_mentions_classification_labels(self):
        """Judge prompt should warn that classification labels are not commitments."""
        from app.services.llm_judge import JUDGE_PROMPT

        # Judge must be aware that words like "greeting" are labels, not commitments
        assert "classification label" in JUDGE_PROMPT.lower() or "meta-reference" in JUDGE_PROMPT.lower()

    def test_judge_prompt_has_quality_rubric(self):
        """Judge prompt must have a quality rating rubric for consistent scoring."""
        from app.services.llm_judge import JUDGE_PROMPT

        lower = JUDGE_PROMPT.lower()
        # Must define what each rating level means
        assert "5:" in JUDGE_PROMPT or "5 =" in JUDGE_PROMPT or "5 —" in JUDGE_PROMPT, (
            "Judge prompt must have a quality rating rubric defining each level"
        )

    def test_judge_prompt_classifies_follow_ups_as_commitments(self):
        """Judge prompt must explicitly state follow-ups are commitments."""
        from app.services.llm_judge import JUDGE_PROMPT

        assert "follow up" in JUDGE_PROMPT.lower(), (
            "Judge prompt must mention follow-ups as commitments"
        )
