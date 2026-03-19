"""Tests for context auto-assignment service.

TDD: Tests for assign_contexts_for_user() which matches commitments
to existing commitment_contexts based on counterparty_name and title keywords.

Covers:
- Exact match: counterparty_name matches context name
- Case-insensitive match
- Substring match: context name appears in commitment title
- No match: commitment left without context_id
- Already assigned: existing context_id not overridden
- No contexts: no-op when user has no contexts
- No commitments: no-op when user has no unassigned commitments
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.context_assigner import assign_contexts_for_user, match_commitment_to_context


NOW = datetime.now(timezone.utc)
USER_ID = "test-user-ctx"


def _uid():
    return str(uuid.uuid4())


def _make_context(name: str, **kwargs):
    ctx = MagicMock()
    ctx.id = kwargs.get("id", _uid())
    ctx.user_id = USER_ID
    ctx.name = name
    ctx.summary = kwargs.get("summary")
    return ctx


def _make_commitment(title: str, counterparty_name: str | None = None, context_id: str | None = None, **kwargs):
    obj = MagicMock()
    obj.id = kwargs.get("id", _uid())
    obj.user_id = USER_ID
    obj.title = title
    obj.counterparty_name = counterparty_name
    obj.context_id = context_id
    obj.lifecycle_state = kwargs.get("lifecycle_state", "proposed")
    return obj


# ---------------------------------------------------------------------------
# Unit tests: match_commitment_to_context
# ---------------------------------------------------------------------------

class TestMatchCommitmentToContext:
    """Test the pure matching function."""

    def test_exact_counterparty_match(self):
        contexts = [_make_context("Acme Corp"), _make_context("Internal")]
        commitment = _make_commitment("Send proposal", counterparty_name="Acme Corp")
        result = match_commitment_to_context(commitment, contexts)
        assert result is not None
        assert result.name == "Acme Corp"

    def test_case_insensitive_counterparty_match(self):
        contexts = [_make_context("Acme Corp")]
        commitment = _make_commitment("Send proposal", counterparty_name="acme corp")
        result = match_commitment_to_context(commitment, contexts)
        assert result is not None
        assert result.name == "Acme Corp"

    def test_counterparty_substring_of_context(self):
        """counterparty_name 'Acme' matches context 'Acme Corp'."""
        contexts = [_make_context("Acme Corp")]
        commitment = _make_commitment("Send proposal", counterparty_name="Acme")
        result = match_commitment_to_context(commitment, contexts)
        assert result is not None
        assert result.name == "Acme Corp"

    def test_context_name_in_title(self):
        """Context name found as substring in commitment title."""
        contexts = [_make_context("Project Alpha")]
        commitment = _make_commitment("Review Project Alpha deliverables")
        result = match_commitment_to_context(commitment, contexts)
        assert result is not None
        assert result.name == "Project Alpha"

    def test_no_match(self):
        contexts = [_make_context("Acme Corp")]
        commitment = _make_commitment("Send proposal", counterparty_name="Globex")
        result = match_commitment_to_context(commitment, contexts)
        assert result is None

    def test_empty_contexts(self):
        commitment = _make_commitment("Send proposal", counterparty_name="Acme")
        result = match_commitment_to_context(commitment, [])
        assert result is None

    def test_no_counterparty_no_title_match(self):
        contexts = [_make_context("Acme Corp")]
        commitment = _make_commitment("Do the thing")
        result = match_commitment_to_context(commitment, contexts)
        assert result is None

    def test_counterparty_match_preferred_over_title_match(self):
        """When both counterparty and title could match different contexts, counterparty wins."""
        ctx_acme = _make_context("Acme Corp")
        ctx_beta = _make_context("Beta Project")
        commitment = _make_commitment("Beta Project proposal", counterparty_name="Acme Corp")
        result = match_commitment_to_context(commitment, [ctx_acme, ctx_beta])
        assert result is not None
        assert result.name == "Acme Corp"

    def test_short_context_name_not_spurious(self):
        """Very short context names (1-2 chars) should not match spuriously."""
        contexts = [_make_context("AI")]
        commitment = _make_commitment("Send the email to client")
        result = match_commitment_to_context(commitment, contexts)
        # "AI" is too short to match in "email" — should not match
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: assign_contexts_for_user
# ---------------------------------------------------------------------------

class TestAssignContextsForUser:
    """Test the DB-level orchestration."""

    def test_assigns_matching_commitments(self):
        ctx = _make_context("Acme Corp", id="ctx-acme")
        c1 = _make_commitment("Send Acme Corp proposal", counterparty_name="Acme Corp", context_id=None, id="c1")
        c2 = _make_commitment("Internal review", counterparty_name=None, context_id=None, id="c2")

        db = MagicMock()
        # Mock: contexts query returns [ctx]
        ctx_result = MagicMock()
        ctx_result.scalars.return_value.all.return_value = [ctx]
        # Mock: commitments query returns [c1, c2]
        commit_result = MagicMock()
        commit_result.scalars.return_value.all.return_value = [c1, c2]

        db.execute.side_effect = [ctx_result, commit_result]

        result = assign_contexts_for_user(USER_ID, db)

        assert result["assigned"] == 1
        assert result["skipped"] == 1
        assert c1.context_id == "ctx-acme"
        assert c2.context_id is None  # no match

    def test_does_not_override_existing_context(self):
        ctx = _make_context("Acme Corp", id="ctx-acme")
        c1 = _make_commitment("Acme proposal", counterparty_name="Acme Corp", context_id="existing-ctx", id="c1")

        db = MagicMock()
        ctx_result = MagicMock()
        ctx_result.scalars.return_value.all.return_value = [ctx]
        # Query for unassigned should not return c1 since it already has context_id
        commit_result = MagicMock()
        commit_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [ctx_result, commit_result]

        result = assign_contexts_for_user(USER_ID, db)
        assert result["assigned"] == 0

    def test_no_contexts_returns_zero(self):
        db = MagicMock()
        ctx_result = MagicMock()
        ctx_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [ctx_result]

        result = assign_contexts_for_user(USER_ID, db)
        assert result["assigned"] == 0
        assert result["total"] == 0
