"""Tests for observation window logic — Phase D1.

Tests cover:
- default_window_hours returns expected defaults for each source type
- get_window_hours with user config overrides defaults
- get_window_hours with partial config falls back to defaults for missing keys
- merge_with_defaults fills all 5 canonical keys
- is_observable and should_surface_early (existing behavior preserved)
- Validation: VALID_WINDOW_KEYS constant has exactly 5 keys
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.observation_window import (
    VALID_WINDOW_KEYS,
    _DEFAULT_WINDOWS,
    _WORK_TO_CALENDAR,
    default_window_hours,
    get_window_hours,
    is_observable,
    merge_with_defaults,
    should_surface_early,
)


# ---------------------------------------------------------------------------
# VALID_WINDOW_KEYS
# ---------------------------------------------------------------------------

class TestValidWindowKeys:
    def test_has_exactly_five_canonical_keys(self):
        assert VALID_WINDOW_KEYS == {
            "slack",
            "email_internal",
            "email_external",
            "meeting_internal",
            "meeting_external",
        }


# ---------------------------------------------------------------------------
# default_window_hours (existing behavior preserved)
# ---------------------------------------------------------------------------

class TestDefaultWindowHours:
    def test_slack_returns_2_working_hours(self):
        assert default_window_hours("slack") == pytest.approx(2.0 * _WORK_TO_CALENDAR)

    def test_email_internal(self):
        assert default_window_hours("email") == pytest.approx(24.0 * _WORK_TO_CALENDAR)

    def test_email_external(self):
        assert default_window_hours("email", external=True) == pytest.approx(48.0 * _WORK_TO_CALENDAR)

    def test_meeting_internal(self):
        assert default_window_hours("meeting") == pytest.approx(24.0 * _WORK_TO_CALENDAR)

    def test_meeting_external(self):
        assert default_window_hours("meeting", external=True) == pytest.approx(48.0 * _WORK_TO_CALENDAR)

    def test_unknown_source_returns_fallback(self):
        result = default_window_hours("carrier_pigeon")
        assert result == pytest.approx(24.0 * _WORK_TO_CALENDAR)


# ---------------------------------------------------------------------------
# get_window_hours (new — user config support)
# ---------------------------------------------------------------------------

class TestGetWindowHours:
    def test_no_user_config_returns_default(self):
        """Without user config, behaves identically to default_window_hours."""
        assert get_window_hours("slack", False) == default_window_hours("slack")
        assert get_window_hours("email", True) == default_window_hours("email", external=True)

    def test_user_config_overrides_default(self):
        config = {"slack": 5.0}
        assert get_window_hours("slack", False, user_config=config) == 5.0

    def test_user_config_email_external(self):
        config = {"email_external": 100.0}
        assert get_window_hours("email", True, user_config=config) == 100.0

    def test_user_config_email_internal(self):
        config = {"email_internal": 10.0}
        assert get_window_hours("email", False, user_config=config) == 10.0

    def test_user_config_meeting_internal(self):
        config = {"meeting_internal": 12.0}
        assert get_window_hours("meeting", False, user_config=config) == 12.0

    def test_user_config_meeting_external(self):
        config = {"meeting_external": 80.0}
        assert get_window_hours("meeting", True, user_config=config) == 80.0

    def test_partial_config_falls_back_for_missing_keys(self):
        """Only slack is overridden; email should use default."""
        config = {"slack": 5.0}
        assert get_window_hours("slack", False, user_config=config) == 5.0
        assert get_window_hours("email", False, user_config=config) == default_window_hours("email")

    def test_none_user_config_treated_as_no_config(self):
        assert get_window_hours("slack", False, user_config=None) == default_window_hours("slack")

    def test_empty_dict_treated_as_no_config(self):
        assert get_window_hours("slack", False, user_config={}) == default_window_hours("slack")

    def test_unknown_source_with_config_returns_fallback(self):
        """User config only has canonical keys; unknown source falls back to default."""
        config = {"slack": 5.0}
        result = get_window_hours("carrier_pigeon", False, user_config=config)
        assert result == default_window_hours("carrier_pigeon")


# ---------------------------------------------------------------------------
# merge_with_defaults
# ---------------------------------------------------------------------------

class TestMergeWithDefaults:
    def test_none_returns_all_defaults(self):
        merged = merge_with_defaults(None)
        assert set(merged.keys()) == VALID_WINDOW_KEYS
        assert merged["slack"] == pytest.approx(2.0 * _WORK_TO_CALENDAR)
        assert merged["email_external"] == pytest.approx(48.0 * _WORK_TO_CALENDAR)

    def test_empty_dict_returns_all_defaults(self):
        merged = merge_with_defaults({})
        assert set(merged.keys()) == VALID_WINDOW_KEYS

    def test_partial_override_merges_correctly(self):
        merged = merge_with_defaults({"slack": 5.0})
        assert merged["slack"] == 5.0
        # Other keys still have defaults
        assert merged["email_internal"] == pytest.approx(24.0 * _WORK_TO_CALENDAR)
        assert merged["email_external"] == pytest.approx(48.0 * _WORK_TO_CALENDAR)

    def test_full_override(self):
        config = {
            "slack": 1.0,
            "email_internal": 2.0,
            "email_external": 3.0,
            "meeting_internal": 4.0,
            "meeting_external": 5.0,
        }
        merged = merge_with_defaults(config)
        assert merged == config

    def test_extra_keys_in_config_are_ignored(self):
        """Only canonical keys appear in output."""
        config = {"slack": 5.0, "bogus_key": 99.0}
        merged = merge_with_defaults(config)
        assert "bogus_key" not in merged
        assert merged["slack"] == 5.0


# ---------------------------------------------------------------------------
# is_observable (existing behavior)
# ---------------------------------------------------------------------------

class TestIsObservable:
    def test_none_observe_until_means_not_observable(self):
        c = SimpleNamespace(observe_until=None)
        assert is_observable(c) is False

    def test_future_observe_until_means_observable(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        c = SimpleNamespace(observe_until=future)
        assert is_observable(c) is True

    def test_past_observe_until_means_not_observable(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        c = SimpleNamespace(observe_until=past)
        assert is_observable(c) is False

    def test_naive_datetime_handled(self):
        future = datetime.now() + timedelta(hours=1)
        c = SimpleNamespace(observe_until=future)
        assert is_observable(c) is True


# ---------------------------------------------------------------------------
# should_surface_early (existing behavior)
# ---------------------------------------------------------------------------

class TestShouldSurfaceEarly:
    def test_not_observable_returns_false(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        c = SimpleNamespace(
            observe_until=past,
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=0.9,
        )
        assert should_surface_early(c) is False

    def test_internal_returns_false(self):
        future = datetime.now(timezone.utc) + timedelta(hours=10)
        c = SimpleNamespace(
            observe_until=future,
            context_type="internal",
            source_type="email",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=0.9,
        )
        assert should_surface_early(c) is False

    def test_external_with_deadline_and_high_confidence(self):
        future = datetime.now(timezone.utc) + timedelta(hours=10)
        c = SimpleNamespace(
            observe_until=future,
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=0.9,
        )
        assert should_surface_early(c) is True

    def test_no_deadline_returns_false(self):
        future = datetime.now(timezone.utc) + timedelta(hours=10)
        c = SimpleNamespace(
            observe_until=future,
            context_type="external",
            resolved_deadline=None,
            confidence_commitment=0.9,
        )
        assert should_surface_early(c) is False

    def test_low_confidence_returns_false(self):
        future = datetime.now(timezone.utc) + timedelta(hours=10)
        c = SimpleNamespace(
            observe_until=future,
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=0.5,
        )
        assert should_surface_early(c) is False
