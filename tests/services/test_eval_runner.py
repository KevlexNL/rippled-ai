"""Unit tests for eval harness runner — WO-RIPPLED-EVAL-HARNESS.

Tests scoring logic, result classification, and eval orchestration
with mocked LLM calls.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.eval.runner import (
    compute_scores,
    classify_result,
    EvalScores,
)


class TestClassifyResult:
    """classify_result(expected_has_commitment, actual_has_commitment) -> str"""

    def test_true_positive(self):
        assert classify_result(True, True) == "tp"

    def test_false_positive(self):
        assert classify_result(False, True) == "fp"

    def test_true_negative(self):
        assert classify_result(False, False) == "tn"

    def test_false_negative(self):
        assert classify_result(True, False) == "fn"


class TestComputeScores:
    """compute_scores(tp, fp, tn, fn) -> EvalScores"""

    def test_perfect_precision_and_recall(self):
        scores = compute_scores(tp=10, fp=0, tn=5, fn=0)
        assert scores.precision == Decimal("1.0000")
        assert scores.recall == Decimal("1.0000")
        assert scores.f1 == Decimal("1.0000")

    def test_zero_predictions_yields_zero_precision(self):
        # No positives predicted at all
        scores = compute_scores(tp=0, fp=0, tn=10, fn=5)
        assert scores.precision == Decimal("0.0000")
        assert scores.recall == Decimal("0.0000")
        assert scores.f1 == Decimal("0.0000")

    def test_some_false_positives(self):
        scores = compute_scores(tp=8, fp=2, tn=5, fn=0)
        # precision = 8 / (8+2) = 0.8
        assert scores.precision == Decimal("0.8000")
        # recall = 8 / (8+0) = 1.0
        assert scores.recall == Decimal("1.0000")
        # f1 = 2 * 0.8 * 1.0 / (0.8 + 1.0) = 0.8889
        assert scores.f1 == Decimal("0.8889")

    def test_some_false_negatives(self):
        scores = compute_scores(tp=6, fp=0, tn=4, fn=4)
        # precision = 6 / (6+0) = 1.0
        assert scores.precision == Decimal("1.0000")
        # recall = 6 / (6+4) = 0.6
        assert scores.recall == Decimal("0.6000")
        # f1 = 2 * 1.0 * 0.6 / (1.0 + 0.6) = 0.75
        assert scores.f1 == Decimal("0.7500")

    def test_all_wrong(self):
        scores = compute_scores(tp=0, fp=5, tn=0, fn=5)
        # precision = 0 / 5 = 0
        assert scores.precision == Decimal("0.0000")
        # recall = 0 / 5 = 0
        assert scores.recall == Decimal("0.0000")
        assert scores.f1 == Decimal("0.0000")

    def test_returns_eval_scores_dataclass(self):
        scores = compute_scores(tp=3, fp=1, tn=2, fn=1)
        assert isinstance(scores, EvalScores)
