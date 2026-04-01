"""Tests for Phase D2 — User-Configurable Auto-Close Timing.

Strategy:
- get_auto_close_hours: unit tests via SimpleNamespace (no DB required).
  Tests resolution hierarchy: class-specific > internal/external > system default.
- API validation: pydantic model validation for auto_close_config.
- Sweep integration: run_auto_close_sweep respects user config.

All tests run without a real database.
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def make_commitment(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "lifecycle_state": "delivered",
        "priority_class": "small_commitment",
        "context_type": "internal",
        "delivered_at": _NOW - timedelta(days=3),
        "auto_close_after_hours": 48,
        "confidence_closure": 0.80,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# get_auto_close_hours — resolution hierarchy tests
# ---------------------------------------------------------------------------


class TestGetAutoCloseHours:
    """Test the resolution hierarchy: class-specific > internal/external > system default."""

    def test_system_default_no_config(self):
        """No user config → uses commitment.auto_close_after_hours (system default)."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(auto_close_after_hours=48)
        result = get_auto_close_hours(commitment, user_config=None)
        assert result == 48

    def test_internal_hours_override(self):
        """User sets internal_hours → internal commitments use it."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(context_type="internal")
        config = {"internal_hours": 24}
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 24

    def test_external_hours_override(self):
        """User sets external_hours → external commitments use it."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(context_type="external")
        config = {"external_hours": 200}
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 200

    def test_big_promise_class_override(self):
        """Class-specific big_promise_hours overrides internal/external."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(priority_class="big_promise", context_type="internal")
        config = {"internal_hours": 24, "big_promise_hours": 168}
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 168

    def test_small_commitment_class_override(self):
        """Class-specific small_commitment_hours overrides internal/external."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(priority_class="small_commitment", context_type="external")
        config = {"external_hours": 120, "small_commitment_hours": 36}
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 36

    def test_class_override_falls_through_to_internal_external(self):
        """Class key absent → falls through to internal/external."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(priority_class="big_promise", context_type="external")
        config = {"external_hours": 120}  # no big_promise_hours
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 120

    def test_partial_config_merges_with_default(self):
        """Config with only some keys → missing keys fall to system default."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(
            priority_class="small_commitment",
            context_type="internal",
            auto_close_after_hours=48,
        )
        config = {"external_hours": 200}  # no internal_hours, no small_commitment_hours
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 48  # falls back to system default

    def test_none_priority_class_skips_class_lookup(self):
        """Commitment with no priority_class → skips class, uses internal/external."""
        from app.services.auto_close_config import get_auto_close_hours

        commitment = make_commitment(priority_class=None, context_type="external")
        config = {"external_hours": 100, "big_promise_hours": 168}
        result = get_auto_close_hours(commitment, user_config=config)
        assert result == 100


# ---------------------------------------------------------------------------
# merge_auto_close_defaults — for API GET response
# ---------------------------------------------------------------------------


class TestMergeAutoCloseDefaults:
    """Test that merge returns full config with system defaults filled in."""

    def test_merge_none_returns_defaults(self):
        from app.services.auto_close_config import merge_auto_close_defaults

        result = merge_auto_close_defaults(None)
        assert result == {
            "internal_hours": 48,
            "external_hours": 120,
            "big_promise_hours": 168,
            "small_commitment_hours": 48,
        }

    def test_merge_partial_fills_gaps(self):
        from app.services.auto_close_config import merge_auto_close_defaults

        result = merge_auto_close_defaults({"internal_hours": 24})
        assert result["internal_hours"] == 24
        assert result["external_hours"] == 120  # system default
        assert result["big_promise_hours"] == 168
        assert result["small_commitment_hours"] == 48

    def test_merge_full_override(self):
        from app.services.auto_close_config import merge_auto_close_defaults

        config = {
            "internal_hours": 10,
            "external_hours": 20,
            "big_promise_hours": 30,
            "small_commitment_hours": 5,
        }
        result = merge_auto_close_defaults(config)
        assert result == config


# ---------------------------------------------------------------------------
# Validation — 1h to 720h (30 days)
# ---------------------------------------------------------------------------


class TestAutoCloseValidation:
    """Test that auto_close_config validation enforces 1-720 hour range."""

    def test_valid_config_accepted(self):
        from app.services.auto_close_config import VALID_AUTO_CLOSE_KEYS, validate_auto_close_config

        config = {"internal_hours": 24, "external_hours": 120}
        # Should not raise
        validate_auto_close_config(config)

    def test_below_minimum_rejected(self):
        from app.services.auto_close_config import validate_auto_close_config

        with pytest.raises(ValueError, match="between 1 and 720"):
            validate_auto_close_config({"internal_hours": 0.5})

    def test_above_maximum_rejected(self):
        from app.services.auto_close_config import validate_auto_close_config

        with pytest.raises(ValueError, match="between 1 and 720"):
            validate_auto_close_config({"internal_hours": 721})

    def test_unknown_key_rejected(self):
        from app.services.auto_close_config import validate_auto_close_config

        with pytest.raises(ValueError, match="Unknown auto-close config key"):
            validate_auto_close_config({"bogus_key": 48})

    def test_boundary_min_accepted(self):
        from app.services.auto_close_config import validate_auto_close_config

        validate_auto_close_config({"internal_hours": 1})  # should not raise

    def test_boundary_max_accepted(self):
        from app.services.auto_close_config import validate_auto_close_config

        validate_auto_close_config({"internal_hours": 720})  # should not raise


# ---------------------------------------------------------------------------
# Sweep integration — auto-close uses user config when available
# ---------------------------------------------------------------------------


class TestAutoCloseSweepWithConfig:
    """Test that run_auto_close_sweep respects user-configured auto-close windows."""

    def test_sweep_uses_user_config_longer_window(self):
        """User config sets longer window → commitment NOT auto-closed yet."""
        from unittest.mock import MagicMock, patch
        from app.services.completion.detector import run_auto_close_sweep

        # Commitment delivered 3 days ago, system default 48h (would close),
        # but user config says 120h (5 days), so should NOT close yet.
        commitment = make_commitment(
            delivered_at=_NOW - timedelta(days=3),
            auto_close_after_hours=48,
            confidence_closure=0.80,
            context_type="internal",
            priority_class="small_commitment",
        )

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [commitment],  # delivered commitments query
        ]

        user_settings = types.SimpleNamespace(
            auto_close_config={"internal_hours": 120},
        )

        with patch(
            "app.services.completion.detector.load_user_auto_close_config",
            return_value={"internal_hours": 120},
        ):
            result = run_auto_close_sweep(mock_db)

        assert result["auto_closed"] == 0

    def test_sweep_uses_user_config_shorter_window(self):
        """User config sets shorter window → commitment IS auto-closed."""
        from unittest.mock import MagicMock, patch
        from app.services.completion.detector import run_auto_close_sweep

        # Commitment delivered 2 days ago, system default 48h (would close),
        # user config says 24h (1 day), so should close.
        commitment = make_commitment(
            delivered_at=_NOW - timedelta(days=2),
            auto_close_after_hours=48,
            confidence_closure=0.80,
            context_type="internal",
            priority_class="small_commitment",
        )

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [commitment],
        ]

        with patch(
            "app.services.completion.detector.load_user_auto_close_config",
            return_value={"internal_hours": 24},
        ), patch(
            "app.services.completion.detector.apply_auto_close",
        ) as mock_apply:
            result = run_auto_close_sweep(mock_db)

        assert result["auto_closed"] == 1
