"""Tests for feedback schema ORM models (WO-RIPPLED-FEEDBACK-SCHEMA).

Verifies that all 4 feedback tables are correctly defined in the ORM layer
with expected columns, types, and constraints.
"""

from sqlalchemy import inspect

from app.models.orm import (
    SignalFeedback,
    OutcomeFeedback,
    AdhocSignal,
    LlmJudgeRun,
)


class TestSignalFeedback:
    def test_tablename(self):
        assert SignalFeedback.__tablename__ == "signal_feedback"

    def test_columns_exist(self):
        mapper = inspect(SignalFeedback)
        col_names = {c.key for c in mapper.columns}
        expected = {
            "id", "user_id", "detection_audit_id", "source_item_id",
            "reviewer_user_id", "extraction_correct", "rating",
            "missed_commitments", "false_positives", "notes",
            "reviewed_at", "created_at",
        }
        assert expected <= col_names

    def test_rating_check_constraint(self):
        """rating column should have CHECK (rating BETWEEN 1 AND 5)."""
        table = SignalFeedback.__table__
        check_constraints = [c for c in table.constraints if c.__class__.__name__ == "CheckConstraint"]
        rating_checks = [c for c in check_constraints if "rating" in str(c.sqltext)]
        assert len(rating_checks) >= 1


class TestOutcomeFeedback:
    def test_tablename(self):
        assert OutcomeFeedback.__tablename__ == "outcome_feedback"

    def test_columns_exist(self):
        mapper = inspect(OutcomeFeedback)
        col_names = {c.key for c in mapper.columns}
        expected = {
            "id", "user_id", "commitment_id", "reviewer_user_id",
            "was_useful", "usefulness_rating", "was_timely",
            "notes", "reviewed_at", "created_at",
        }
        assert expected <= col_names

    def test_usefulness_rating_check_constraint(self):
        table = OutcomeFeedback.__table__
        check_constraints = [c for c in table.constraints if c.__class__.__name__ == "CheckConstraint"]
        rating_checks = [c for c in check_constraints if "usefulness_rating" in str(c.sqltext)]
        assert len(rating_checks) >= 1


class TestAdhocSignal:
    def test_tablename(self):
        assert AdhocSignal.__tablename__ == "adhoc_signals"

    def test_columns_exist(self):
        mapper = inspect(AdhocSignal)
        col_names = {c.key for c in mapper.columns}
        expected = {
            "id", "user_id", "raw_text", "source", "received_at",
            "match_status", "matched_commitment_id", "matched_source_item_id",
            "match_checked_at", "match_confidence", "was_found",
            "notes", "created_at",
        }
        assert expected <= col_names

    def test_match_status_default(self):
        col = AdhocSignal.__table__.c.match_status
        assert col.server_default is not None


class TestLlmJudgeRun:
    def test_tablename(self):
        assert LlmJudgeRun.__tablename__ == "llm_judge_runs"

    def test_columns_exist(self):
        mapper = inspect(LlmJudgeRun)
        col_names = {c.key for c in mapper.columns}
        expected = {
            "id", "user_id", "judge_model", "student_model",
            "items_reviewed", "false_positives_found", "false_negatives_found",
            "prompt_improvement_suggestions", "raw_judge_output",
            "run_at", "created_at",
        }
        assert expected <= col_names

    def test_items_reviewed_default(self):
        col = LlmJudgeRun.__table__.c.items_reviewed
        assert col.server_default is not None
