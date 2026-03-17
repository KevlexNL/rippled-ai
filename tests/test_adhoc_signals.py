"""Unit tests for ad-hoc signal match logic (WO-RIPPLED-ADHOC-SIGNAL).

Pure unit tests — no DB or HTTP fixtures needed.
"""
from __future__ import annotations


class TestMatchLogic:
    """Unit tests for the text similarity matching logic."""

    def test_keyword_overlap_high(self):
        from app.services.adhoc_matcher import compute_keyword_similarity
        score = compute_keyword_similarity(
            "send Matt the RevEngine report by Friday",
            "Send Matt the RevEngine report before end of week",
        )
        assert score >= 0.5

    def test_keyword_overlap_low(self):
        from app.services.adhoc_matcher import compute_keyword_similarity
        score = compute_keyword_similarity(
            "send Matt the RevEngine report by Friday",
            "Team standup agenda for Monday morning",
        )
        assert score < 0.3

    def test_substring_match(self):
        from app.services.adhoc_matcher import has_substring_match
        assert has_substring_match(
            "RevEngine report",
            "I committed to sending the RevEngine report to Matt by Friday",
        )

    def test_substring_no_match(self):
        from app.services.adhoc_matcher import has_substring_match
        assert not has_substring_match(
            "RevEngine report",
            "Team standup agenda for Monday morning",
        )

    def test_best_match_scoring(self):
        from app.services.adhoc_matcher import score_match
        score = score_match(
            "committed to sending Matt the RevEngine report by Friday",
            "Send the RevEngine report to Matt by end of week",
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.4

    def test_best_match_scoring_no_match(self):
        from app.services.adhoc_matcher import score_match
        score = score_match(
            "committed to sending Matt the RevEngine report by Friday",
            "Weekly team standup notes from Monday",
        )
        assert score < 0.3
