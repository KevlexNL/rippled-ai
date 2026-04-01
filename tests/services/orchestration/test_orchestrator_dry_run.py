"""Tests for SignalOrchestrator dry_run mode — no DB persistence."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.contracts import (
    EligibilityReason,
    RoutingAction,
)
from app.services.orchestration.orchestrator import SignalOrchestrator


def _make_signal(**kwargs) -> NormalizedSignal:
    defaults = {
        "signal_id": "debug-test-001",
        "source_type": "email",
        "occurred_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "authored_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "latest_authored_text": "I'll send the report by Friday.",
        "subject": "Report",
    }
    defaults.update(kwargs)
    return NormalizedSignal(**defaults)


class TestDryRunMode:
    """dry_run=True must skip all DB persistence while still running pipeline stages."""

    def test_dry_run_does_not_require_db_session(self):
        """Orchestrator in dry_run mode works without a real DB session."""
        orchestrator = SignalOrchestrator(db=None, dry_run=True)
        signal = _make_signal(latest_authored_text="", prior_context_text=None)

        result = orchestrator.process(signal)

        # Should still run eligibility and return a result
        assert result.eligibility.eligible is False
        assert result.eligibility.reason == EligibilityReason.missing_text
        assert result.final_routing.action == RoutingAction.discard
        assert result.error is None

    def test_dry_run_never_calls_db(self):
        """Orchestrator in dry_run mode never touches the DB session."""
        mock_db = MagicMock()
        orchestrator = SignalOrchestrator(db=mock_db, dry_run=True)
        signal = _make_signal(latest_authored_text="", prior_context_text=None)

        orchestrator.process(signal)

        # DB should never be touched in dry_run mode
        mock_db.add.assert_not_called()
        mock_db.flush.assert_not_called()

    def test_dry_run_returns_valid_run_id(self):
        """dry_run produces a result with a usable run_id."""
        orchestrator = SignalOrchestrator(db=None, dry_run=True)
        signal = _make_signal(latest_authored_text="", prior_context_text=None)

        result = orchestrator.process(signal)

        assert result.run_id.startswith("dry-run-")
        assert len(result.run_id) > len("dry-run-")
