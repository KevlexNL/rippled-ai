"""Tests for owner resolution matching logic.

Tests verify:
- Exact match: suggested_owner matches identity_value
- Case-insensitive match
- Substring match (either direction)
- Fuzzy match above threshold
- No match returns False
"""
import pytest

from app.services.identity.owner_resolver import _is_match


class TestIsMatch:
    def test_exact_match(self):
        assert _is_match("Kevin Beeftink", "Kevin Beeftink") is True

    def test_case_insensitive_match(self):
        assert _is_match("kevin beeftink", "Kevin Beeftink") is True

    def test_substring_suggested_in_identity(self):
        assert _is_match("Kevin", "Kevin Beeftink") is True

    def test_substring_identity_in_suggested(self):
        assert _is_match("Kevin Beeftink will handle this", "Kevin Beeftink") is True

    def test_email_match(self):
        assert _is_match("kevin@kevlex.digital", "kevin@kevlex.digital") is True

    def test_no_match(self):
        assert _is_match("Alice Smith", "Kevin Beeftink") is False

    def test_empty_suggested(self):
        assert _is_match("", "Kevin Beeftink") is False

    def test_empty_identity(self):
        assert _is_match("Kevin Beeftink", "") is False

    def test_fuzzy_match_close_spelling(self):
        # "Kevin Beeftink" vs "Kevin Beeftnik" — close enough for fuzzy (ratio ~0.86)
        assert _is_match("Kevin Beeftnik", "Kevin Beeftink") is True

    def test_fuzzy_match_below_threshold(self):
        assert _is_match("xyz", "Kevin Beeftink") is False

    def test_first_name_substring(self):
        # "Kevin B" (no period) is a substring of "Kevin Beeftink"
        assert _is_match("Kevin B", "Kevin Beeftink") is True
