"""Tests for GET /commitments/{id}/signals enriched response.

The frontend expects each signal to include:
- source: source_type from the linked SourceItem (email|slack|meeting)
- text: content snippet from the SourceItem
- created_at: datetime
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
USER_HEADERS = {"X-User-ID": "user-sig-001"}


def _make_signal_with_source(
    signal_id: str = "sig-001",
    commitment_id: str = "c-001",
    source_item_id: str = "si-001",
    signal_role: str = "origin",
    source_type: str = "email",
    content: str = "I'll send the report by Friday",
) -> tuple:
    """Return (signal_namespace, source_namespace) pair for testing."""
    now = datetime.now(timezone.utc)

    sig = SimpleNamespace(
        id=signal_id,
        commitment_id=commitment_id,
        source_item_id=source_item_id,
        user_id="user-sig-001",
        signal_role=signal_role,
        confidence=Decimal("0.850"),
        interpretation_note="Detected commitment",
        created_at=now,
    )

    si = SimpleNamespace(
        id=source_item_id,
        source_type=source_type,
        content=content,
    )

    return sig, si


def _mock_db_for_signals(commitment_exists: bool = True, signal_pairs: list[tuple] | None = None):
    """Mock DB session for the signals endpoint.

    signal_pairs: list of (signal, source_item) tuples.
    """
    if signal_pairs is None:
        signal_pairs = []

    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # _get_commitment_or_404 query
            if commitment_exists:
                c = SimpleNamespace(id="c-001", user_id="user-sig-001")
                result.scalar_one_or_none.return_value = c
            else:
                result.scalar_one_or_none.return_value = None
        elif call_count == 2:
            # signals query — returns (signal, source_item) tuples
            result.__iter__ = MagicMock(return_value=iter(signal_pairs))
        return result

    mock_session.execute = mock_execute
    return mock_session


class TestSignalsEnriched:
    def test_signal_includes_source_field(self):
        """Each signal should include a 'source' field (source_type from SourceItem)."""
        sig, si = _make_signal_with_source(source_type="email")
        mock_db = _mock_db_for_signals(signal_pairs=[(sig, si)])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/commitments/c-001/signals", headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert "source" in data[0]
            assert data[0]["source"] == "email"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_signal_includes_text_field(self):
        """Each signal should include a 'text' field (content from SourceItem)."""
        sig, si = _make_signal_with_source(content="Send report by Friday")
        mock_db = _mock_db_for_signals(signal_pairs=[(sig, si)])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/commitments/c-001/signals", headers=USER_HEADERS)
            data = resp.json()
            assert "text" in data[0]
            assert data[0]["text"] == "Send report by Friday"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_signal_retains_existing_fields(self):
        """Enriched signals should still include all original CommitmentSignalRead fields."""
        sig, si = _make_signal_with_source()
        mock_db = _mock_db_for_signals(signal_pairs=[(sig, si)])
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/commitments/c-001/signals", headers=USER_HEADERS)
            data = resp.json()
            item = data[0]
            for field in ("id", "commitment_id", "source_item_id", "signal_role", "created_at"):
                assert field in item, f"Missing field: {field}"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_404_when_commitment_not_found(self):
        mock_db = _mock_db_for_signals(commitment_exists=False)
        from app.db.deps import get_db

        async def override():
            yield mock_db

        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/v1/commitments/c-missing/signals", headers=USER_HEADERS)
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)
