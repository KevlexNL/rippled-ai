"""Tests for observation window config in user settings API — Phase D1.

Tests verify:
- GET returns merged defaults when no user config exists
- PATCH stores valid observation window config
- PATCH rejects out-of-range values (< 0.5 or > 168)
- PATCH rejects negative values
- PATCH with null resets config to defaults
- Partial config merges correctly on GET
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.deps import get_db
from app.core.dependencies import get_current_user_id
from app.services.observation_window import VALID_WINDOW_KEYS, merge_with_defaults

client = TestClient(app)
URL = "/api/v1/user/settings"
USER_HEADERS = {"X-User-ID": "user-001"}


def _make_user_settings(**overrides):
    """Create a mock UserSettings object with defaults."""
    us = MagicMock()
    us.digest_enabled = True
    us.digest_to_email = None
    us.google_refresh_token = None
    us.anthropic_api_key_encrypted = None
    us.openai_api_key_encrypted = None
    us.observation_window_config = None
    for k, v in overrides.items():
        setattr(us, k, v)
    return us


def _make_mock_db(user_settings):
    """Return an async mock DB session with pre-existing UserSettings."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user_settings
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


def _setup_overrides(us):
    """Set up FastAPI dependency overrides and return the mock db."""
    mock_db = _make_mock_db(us)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user_id] = lambda: "user-001"
    return mock_db


def _cleanup():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET — merged defaults
# ---------------------------------------------------------------------------

class TestGetObservationWindowConfig:
    def test_returns_merged_defaults_when_no_config(self):
        us = _make_user_settings(observation_window_config=None)
        _setup_overrides(us)
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert "observation_window_config" in data
            config = data["observation_window_config"]
            assert set(config.keys()) == VALID_WINDOW_KEYS
            defaults = merge_with_defaults(None)
            for key in VALID_WINDOW_KEYS:
                assert config[key] == pytest.approx(defaults[key], rel=1e-3)
        finally:
            _cleanup()

    def test_returns_merged_config_with_partial_override(self):
        us = _make_user_settings(observation_window_config={"slack": 5.0})
        _setup_overrides(us)
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            assert resp.status_code == 200
            config = resp.json()["observation_window_config"]
            assert config["slack"] == 5.0
            defaults = merge_with_defaults(None)
            assert config["email_internal"] == pytest.approx(defaults["email_internal"], rel=1e-3)
        finally:
            _cleanup()


# ---------------------------------------------------------------------------
# PATCH — valid config
# ---------------------------------------------------------------------------

class TestPatchObservationWindowConfig:
    def test_stores_valid_config(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": 5.0, "email_internal": 20.0}},
            )
            assert resp.status_code == 200
            assert us.observation_window_config == {"slack": 5.0, "email_internal": 20.0}
        finally:
            _cleanup()

    def test_null_resets_to_defaults(self):
        us = _make_user_settings(observation_window_config={"slack": 5.0})
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": None},
            )
            assert resp.status_code == 200
            assert us.observation_window_config is None
        finally:
            _cleanup()


# ---------------------------------------------------------------------------
# PATCH — validation rejects bad input
# ---------------------------------------------------------------------------

class TestPatchObservationWindowValidation:
    def test_rejects_value_below_minimum(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": 0.1}},
            )
            assert resp.status_code == 422
        finally:
            _cleanup()

    def test_rejects_negative_value(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": -1.0}},
            )
            assert resp.status_code == 422
        finally:
            _cleanup()

    def test_rejects_value_above_maximum(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": 200.0}},
            )
            assert resp.status_code == 422
        finally:
            _cleanup()

    def test_rejects_unknown_key(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"carrier_pigeon": 5.0}},
            )
            assert resp.status_code == 422
        finally:
            _cleanup()

    def test_accepts_boundary_minimum(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": 0.5}},
            )
            assert resp.status_code == 200
        finally:
            _cleanup()

    def test_accepts_boundary_maximum(self):
        us = _make_user_settings()
        _setup_overrides(us)
        try:
            resp = client.patch(
                URL,
                headers=USER_HEADERS,
                json={"observation_window_config": {"slack": 168.0}},
            )
            assert resp.status_code == 200
        finally:
            _cleanup()
