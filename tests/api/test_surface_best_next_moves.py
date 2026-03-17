"""Tests for GET /surface/best-next-moves.

Verifies the endpoint returns grouped commitments in the expected shape:
{ groups: [{ label: str, items: [CommitmentRead] }] }

Groups are: "Quick wins", "Likely blockers", "Needs focus".
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/surface/best-next-moves"
USER_HEADERS = {"X-User-ID": "user-bnm-001"}


def _make_commitment(**overrides) -> SimpleNamespace:
    """Build a commitment-like object with sensible defaults."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id="c-001",
        user_id="user-bnm-001",
        context_id=None,
        version=1,
        title="Test commitment",
        description=None,
        commitment_text=None,
        commitment_type=None,
        priority_class=None,
        context_type=None,
        owner_candidates=None,
        resolved_owner=None,
        suggested_owner=None,
        ownership_ambiguity=None,
        deadline_candidates=None,
        resolved_deadline=None,
        vague_time_phrase=None,
        suggested_due_date=None,
        timing_ambiguity=None,
        deliverable=None,
        target_entity=None,
        suggested_next_step=None,
        deliverable_ambiguity=None,
        lifecycle_state="active",
        state_changed_at=now,
        confidence_commitment=None,
        confidence_owner=None,
        confidence_deadline=None,
        confidence_delivery=None,
        confidence_closure=None,
        confidence_actionability=None,
        commitment_explanation=None,
        missing_pieces_explanation=None,
        delivery_explanation=None,
        closure_explanation=None,
        delivered_at=None,
        auto_close_after_hours=48,
        observe_until=None,
        observation_window_hours=None,
        is_surfaced=True,
        surfaced_at=now,
        surfaced_as="shortlist",
        priority_score=Decimal("50.00"),
        timing_strength=None,
        business_consequence=None,
        cognitive_burden=None,
        confidence_for_surfacing=Decimal("0.800"),
        surfacing_reason=None,
        delivery_state=None,
        counterparty_type=None,
        counterparty_email=None,
        counterparty_name=None,
        post_event_reviewed=False,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_db_with_commitments(commitments: list):
    """Return a mock async session that returns given commitments for the main query,
    and empty results for event/source sub-queries."""
    mock_session = AsyncMock()

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Main commitment query
            result.scalars.return_value = commitments
        else:
            # Event map / source map sub-queries
            result.__iter__ = MagicMock(return_value=iter([]))
        return result

    mock_session.execute = mock_execute
    return mock_session


class TestBestNextMovesShape:
    def test_returns_200_with_groups_key(self):
        mock_db = _mock_db_with_commitments([])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert "groups" in data
            assert isinstance(data["groups"], list)
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_empty_commitments_returns_empty_groups(self):
        mock_db = _mock_db_with_commitments([])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            assert data["groups"] == []
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_quick_win_type_grouped_correctly(self):
        """Commitment with type 'confirm' should appear in Quick wins."""
        c = _make_commitment(
            id="c-qw-001",
            commitment_type="confirm",
            surfaced_as="shortlist",
        )
        mock_db = _mock_db_with_commitments([c])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            labels = [g["label"] for g in data["groups"]]
            assert "Quick wins" in labels
            qw_group = next(g for g in data["groups"] if g["label"] == "Quick wins")
            assert len(qw_group["items"]) == 1
            assert qw_group["items"][0]["id"] == "c-qw-001"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_overdue_external_grouped_as_blocker(self):
        """Overdue commitment with external counterparty → Likely blockers."""
        past = datetime.now(timezone.utc) - timedelta(days=2)
        c = _make_commitment(
            id="c-block-001",
            commitment_type="deliver",
            resolved_deadline=past,
            counterparty_type="external",
            surfaced_as="main",
        )
        mock_db = _mock_db_with_commitments([c])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            labels = [g["label"] for g in data["groups"]]
            assert "Likely blockers" in labels
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_remaining_items_grouped_as_needs_focus(self):
        """Non-quick-win, non-blocker items → Needs focus."""
        c = _make_commitment(
            id="c-focus-001",
            commitment_type="investigate",
            surfaced_as="main",
        )
        mock_db = _mock_db_with_commitments([c])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            labels = [g["label"] for g in data["groups"]]
            assert "Needs focus" in labels
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_total_items_capped_at_five(self):
        """No more than 5 items total across all groups."""
        commitments = [
            _make_commitment(
                id=f"c-many-{i:03d}",
                commitment_type="investigate",
                surfaced_as="main",
                priority_score=Decimal(str(90 - i)),
            )
            for i in range(10)
        ]
        mock_db = _mock_db_with_commitments(commitments)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            total_items = sum(len(g["items"]) for g in data["groups"])
            assert total_items <= 5
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_group_items_are_commitment_read_shape(self):
        """Each item in a group should have CommitmentRead fields."""
        c = _make_commitment(id="c-shape-001", commitment_type="send")
        mock_db = _mock_db_with_commitments([c])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(URL, headers=USER_HEADERS)
            data = resp.json()
            item = data["groups"][0]["items"][0]
            assert "id" in item
            assert "title" in item
            assert "lifecycle_state" in item
            assert "priority_score" in item
        finally:
            app.dependency_overrides.pop(get_db, None)
