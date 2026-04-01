"""Tests for Phase D2 — auto-close config API validation via Pydantic models.

Tests the UserSettingsPatch validation for auto_close_config without
requiring a running server. Pure Pydantic model tests.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestAutoCloseConfigPydanticValidation:
    """Test auto_close_config validation on UserSettingsPatch."""

    def test_valid_config_accepted(self):
        from app.api.routes.user_settings import UserSettingsPatch

        body = UserSettingsPatch(auto_close_config={"internal_hours": 24, "external_hours": 120})
        assert body.auto_close_config == {"internal_hours": 24, "external_hours": 120}

    def test_below_minimum_rejected(self):
        from app.api.routes.user_settings import UserSettingsPatch

        with pytest.raises(ValidationError, match="between 1 and 720"):
            UserSettingsPatch(auto_close_config={"internal_hours": 0.5})

    def test_above_maximum_rejected(self):
        from app.api.routes.user_settings import UserSettingsPatch

        with pytest.raises(ValidationError, match="between 1 and 720"):
            UserSettingsPatch(auto_close_config={"internal_hours": 721})

    def test_unknown_key_rejected(self):
        from app.api.routes.user_settings import UserSettingsPatch

        with pytest.raises(ValidationError, match="Unknown auto-close config key"):
            UserSettingsPatch(auto_close_config={"bogus_key": 48})

    def test_none_clears_config(self):
        from app.api.routes.user_settings import UserSettingsPatch

        body = UserSettingsPatch(auto_close_config=None)
        assert body.auto_close_config is None

    def test_partial_config_accepted(self):
        from app.api.routes.user_settings import UserSettingsPatch

        body = UserSettingsPatch(auto_close_config={"big_promise_hours": 168})
        assert body.auto_close_config == {"big_promise_hours": 168}


class TestAutoCloseConfigInReadModel:
    """Test auto_close_config appears in UserSettingsRead."""

    def test_read_model_has_auto_close_config(self):
        from app.api.routes.user_settings import UserSettingsRead

        data = UserSettingsRead(
            digest_enabled=True,
            digest_to_email=None,
            google_connected=False,
            anthropic_key_connected=False,
            openai_key_connected=False,
            observation_window_config={"slack": 2.8},
            auto_close_config={
                "internal_hours": 48,
                "external_hours": 120,
                "big_promise_hours": 168,
                "small_commitment_hours": 48,
            },
        )
        assert data.auto_close_config["internal_hours"] == 48
        assert data.auto_close_config["external_hours"] == 120
