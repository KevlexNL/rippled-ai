"""Tests for Celery worker readiness signal — WO-RIPPLED-PIPELINE-RACE-FIX.

Verifies that:
1. worker_ready signal handler creates the readiness marker file
2. The marker file path is consistent (/tmp/celery_ready)
"""
from __future__ import annotations

import os
from unittest.mock import patch


READINESS_FILE = "/tmp/celery_ready"


class TestCeleryReadinessSignal:
    """Test that worker_ready signal creates readiness marker."""

    def setup_method(self):
        """Clean up readiness file before each test."""
        if os.path.exists(READINESS_FILE):
            os.remove(READINESS_FILE)

    def teardown_method(self):
        """Clean up readiness file after each test."""
        if os.path.exists(READINESS_FILE):
            os.remove(READINESS_FILE)

    def test_worker_ready_creates_marker_file(self):
        """worker_ready signal handler should touch /tmp/celery_ready."""
        from app.tasks import _mark_celery_ready

        assert not os.path.exists(READINESS_FILE)
        _mark_celery_ready(sender=None)
        assert os.path.exists(READINESS_FILE)

    def test_worker_ready_is_idempotent(self):
        """Calling the handler twice should not raise."""
        from app.tasks import _mark_celery_ready

        _mark_celery_ready(sender=None)
        _mark_celery_ready(sender=None)
        assert os.path.exists(READINESS_FILE)
