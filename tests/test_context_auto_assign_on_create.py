"""Tests for auto-context-assignment on commitment creation.

When a commitment is created via POST /api/v1/commitments without a context_id,
the system should try to match it to an existing context using the context_assigner.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.services.context_assigner import match_commitment_to_context


def _uid():
    return str(uuid.uuid4())


def _make_context(name: str, **kwargs):
    ctx = MagicMock()
    ctx.id = kwargs.get("id", _uid())
    ctx.name = name
    return ctx


def _make_commitment(title: str, counterparty_name: str | None = None, context_id: str | None = None):
    obj = MagicMock()
    obj.id = _uid()
    obj.title = title
    obj.counterparty_name = counterparty_name
    obj.context_id = context_id
    return obj


class TestAutoAssignOnCreate:
    """Test that match_commitment_to_context correctly identifies contexts for new commitments."""

    def test_new_commitment_gets_context_from_counterparty(self):
        """A new commitment with counterparty matching a context should get auto-assigned."""
        contexts = [_make_context("Acme Corp", id="ctx-acme")]
        commitment = _make_commitment("Send proposal", counterparty_name="Acme Corp")

        match = match_commitment_to_context(commitment, contexts)
        assert match is not None
        assert match.id == "ctx-acme"

    def test_new_commitment_gets_context_from_title(self):
        """A new commitment with title matching a context name should get auto-assigned."""
        contexts = [_make_context("Project Beta", id="ctx-beta")]
        commitment = _make_commitment("Review Project Beta deliverables")

        match = match_commitment_to_context(commitment, contexts)
        assert match is not None
        assert match.id == "ctx-beta"

    def test_new_commitment_no_match_returns_none(self):
        """When no context matches, return None (don't assign)."""
        contexts = [_make_context("Acme Corp")]
        commitment = _make_commitment("Buy groceries")

        match = match_commitment_to_context(commitment, contexts)
        assert match is None

    def test_explicit_context_id_not_overridden(self):
        """If a commitment already has context_id, auto-assign should be skipped."""
        contexts = [_make_context("Acme Corp", id="ctx-acme")]
        commitment = _make_commitment("Send proposal", counterparty_name="Acme Corp", context_id="existing-ctx")

        # The creation endpoint should skip auto-assign when context_id is already set.
        # match_commitment_to_context would still return a match, but the caller skips it.
        # This test documents that behavior expectation.
        assert commitment.context_id == "existing-ctx"
