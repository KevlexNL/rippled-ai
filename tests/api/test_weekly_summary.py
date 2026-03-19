"""Tests for GET /report/weekly-summary endpoint.

Verifies the weekly pipeline cost report returns correct aggregations
from detection_audit and commitments tables.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/report/weekly-summary"


def _mock_db_for_weekly_summary(
    *,
    suppressed: int = 100,
    tier_1: int = 1,
    tier_2: int = 50,
    tier_3: int = 20,
    cost_llm: Decimal = Decimal("2.50"),
    cost_embedding: Decimal = Decimal("0.00"),
    commitments: int = 10,
    source_items: int = 80,
):
    """Return a mock session that returns canned weekly summary data."""
    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Tier counts query
            row = MagicMock()
            row.suppressed = suppressed
            row.tier_1 = tier_1
            row.tier_2 = tier_2
            row.tier_3 = tier_3
            row.cost_llm_usd = float(cost_llm)
            row.cost_embedding_usd = float(cost_embedding)
            result.one.return_value = row
        elif call_count == 2:
            # Commitments count
            result.scalar.return_value = commitments
        elif call_count == 3:
            # Source items count
            result.scalar.return_value = source_items
        return result

    mock_session.execute = mock_execute
    return mock_session


def _override_db(mock_db):
    from app.db.deps import get_db

    async def override():
        yield mock_db

    app.dependency_overrides[get_db] = override
    return get_db


class TestWeeklySummaryShape:
    def test_returns_200(self):
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_response_has_all_required_fields(self):
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            required = [
                "week",
                "source_items_processed",
                "by_tier",
                "cost_llm_usd",
                "cost_embedding_usd",
                "commitments_surfaced",
                "false_positive_rate_pct",
            ]
            for field in required:
                assert field in data, f"Missing field: {field}"
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_by_tier_breakdown(self):
        mock_db = _mock_db_for_weekly_summary(
            suppressed=500, tier_1=2, tier_2=30, tier_3=15
        )
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            tier = data["by_tier"]
            assert tier["suppressed"] == 500
            assert tier["tier_1"] == 2
            assert tier["tier_2"] == 30
            assert tier["tier_3"] == 15
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_cost_values(self):
        mock_db = _mock_db_for_weekly_summary(
            cost_llm=Decimal("5.29"), cost_embedding=Decimal("0.01")
        )
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            assert data["cost_llm_usd"] == 5.29
            assert data["cost_embedding_usd"] == 0.01
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_commitments_and_source_items(self):
        mock_db = _mock_db_for_weekly_summary(commitments=64, source_items=990)
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            assert data["commitments_surfaced"] == 64
            assert data["source_items_processed"] == 990
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_week_format_is_iso(self):
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            # Should match ISO week format like "2026-W12"
            assert data["week"].startswith("20")
            assert "-W" in data["week"]
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_custom_week_param(self):
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL, params={"week": "2026-W10"})
            data = resp.json()
            assert data["week"] == "2026-W10"
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_invalid_week_param(self):
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL, params={"week": "not-a-week"})
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_false_positive_rate_is_null(self):
        """false_positive_rate_pct is null until signal_feedback is implemented."""
        mock_db = _mock_db_for_weekly_summary()
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            assert data["false_positive_rate_pct"] is None
        finally:
            app.dependency_overrides.pop(dep, None)

    def test_zero_data_week(self):
        mock_db = _mock_db_for_weekly_summary(
            suppressed=0, tier_1=0, tier_2=0, tier_3=0,
            cost_llm=Decimal("0"), cost_embedding=Decimal("0"),
            commitments=0, source_items=0,
        )
        dep = _override_db(mock_db)
        try:
            resp = client.get(URL)
            data = resp.json()
            assert data["source_items_processed"] == 0
            assert data["cost_llm_usd"] == 0.0
            assert data["commitments_surfaced"] == 0
        finally:
            app.dependency_overrides.pop(dep, None)
