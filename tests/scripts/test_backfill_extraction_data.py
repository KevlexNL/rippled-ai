"""Tests for scripts/backfill_extraction_data.py — backfill logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
from decimal import Decimal

import pytest

from scripts.backfill_extraction_data import find_items_without_audit, backfill


def _make_source_item(item_id: str = "item-1", source_type: str = "email", content: str = "I will send the report"):
    item = MagicMock()
    item.id = item_id
    item.source_type = source_type
    item.content = content
    item.content_normalized = content
    item.ingested_at = None
    return item


class TestFindItemsWithoutAudit:
    def test_returns_items_missing_audit(self):
        """Should build correct query filtering out items with audit rows."""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [_make_source_item()]
        db.execute.return_value = mock_result

        result = find_items_without_audit(db, limit=10)
        assert len(result) == 1
        db.execute.assert_called_once()

    def test_empty_when_all_have_audit(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = find_items_without_audit(db)
        assert result == []


class TestBackfillDryRun:
    @patch("scripts.backfill_extraction_data.create_engine")
    @patch("scripts.backfill_extraction_data.get_settings")
    @patch("scripts.backfill_extraction_data.find_items_without_audit")
    def test_dry_run_does_not_write(self, mock_find, mock_settings, mock_engine, capsys):
        mock_settings.return_value.database_url = "postgresql://test"
        mock_find.return_value = [_make_source_item("item-1"), _make_source_item("item-2")]

        summary = backfill(dry_run=True, limit=None)

        assert summary["total_found"] == 2
        assert summary["processed"] == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out


class TestBackfillExecution:
    @patch("scripts.backfill_extraction_data.run_detection")
    @patch("scripts.backfill_extraction_data.Session")
    @patch("scripts.backfill_extraction_data.create_engine")
    @patch("scripts.backfill_extraction_data.get_settings")
    @patch("scripts.backfill_extraction_data.find_items_without_audit")
    def test_processes_items_and_commits(self, mock_find, mock_settings, mock_engine, mock_session_cls, mock_detect, capsys):
        mock_settings.return_value.database_url = "postgresql://test"
        item = _make_source_item("item-1")
        mock_find.return_value = [item]
        mock_detect.return_value = []  # no candidates found

        # Mock the Session so the idempotency check returns None (no existing audit)
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        summary = backfill(dry_run=False, limit=None)

        assert summary["processed"] == 1
        assert summary["errors"] == 0
        mock_detect.assert_called_once()

    @patch("scripts.backfill_extraction_data.run_detection")
    @patch("scripts.backfill_extraction_data.Session")
    @patch("scripts.backfill_extraction_data.create_engine")
    @patch("scripts.backfill_extraction_data.get_settings")
    @patch("scripts.backfill_extraction_data.find_items_without_audit")
    def test_skips_if_audit_exists_at_processing_time(self, mock_find, mock_settings, mock_engine, mock_session_cls, mock_detect):
        """Idempotency: skip items that gained audit rows between query and processing."""
        mock_settings.return_value.database_url = "postgresql://test"
        item = _make_source_item("item-1")
        mock_find.return_value = [item]

        # Idempotency check returns an existing audit row ID → item should be skipped
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = "existing-audit-id"
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        summary = backfill(dry_run=False, limit=None)

        assert summary["total_found"] == 1
        assert summary["skipped"] == 1
        mock_detect.assert_not_called()

    @patch("scripts.backfill_extraction_data.run_detection")
    @patch("scripts.backfill_extraction_data.Session")
    @patch("scripts.backfill_extraction_data.create_engine")
    @patch("scripts.backfill_extraction_data.get_settings")
    @patch("scripts.backfill_extraction_data.find_items_without_audit")
    def test_handles_detection_error_gracefully(self, mock_find, mock_settings, mock_engine, mock_session_cls, mock_detect, capsys):
        mock_settings.return_value.database_url = "postgresql://test"
        item = _make_source_item("item-1")
        mock_find.return_value = [item]
        mock_detect.side_effect = ValueError("SourceItem not found")

        # No existing audit → will attempt detection
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        summary = backfill(dry_run=False, limit=None)

        assert summary["total_found"] == 1
        assert summary["errors"] == 1
        captured = capsys.readouterr()
        assert "ERR" in captured.out
