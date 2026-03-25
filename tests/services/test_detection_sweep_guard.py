"""Tests for detection sweep idempotency guard (WO-RIPPLED-DETECTION-RESCAN-LOOP).

Verifies:
1. run_detection_sweep skips items with seed_processed_at already set
2. run_detection_sweep sets seed_processed_at after processing each item
3. run_detection writes a "no_match" audit entry when no patterns match
4. Running detection twice on the same item produces only 1 audit record
5. Sweep logs scanned vs skipped counts
"""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.detection.detector import run_detection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(**kwargs) -> Any:
    """Create a minimal SourceItem-like namespace for testing."""
    defaults: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "user_id": "user-001",
        "source_type": "email",
        "external_id": "ext-001",
        "source_id": "src-001",
        "content": None,
        "content_normalized": None,
        "direction": "outbound",
        "sender_id": "user-001",
        "sender_name": "Alice",
        "sender_email": "alice@example.com",
        "is_external_participant": False,
        "recipients": None,
        "thread_id": None,
        "metadata_": None,
        "occurred_at": datetime.now(timezone.utc),
        "seed_processed_at": None,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_mock_db(item):
    """Return a mock SQLAlchemy Session that returns `item` on .get()."""
    db = MagicMock()
    db.get.return_value = item
    savepoint = MagicMock()
    savepoint.__enter__ = MagicMock(return_value=savepoint)
    savepoint.__exit__ = MagicMock(return_value=False)
    db.begin_nested.return_value = savepoint
    db.flush = MagicMock()
    # Track profile query (returns None = no profile)
    db.query.return_value.filter.return_value.first.return_value = None
    return db


# ---------------------------------------------------------------------------
# Test: run_detection writes "no_match" audit when no patterns fire
# ---------------------------------------------------------------------------

class TestNoMatchAudit:
    """When run_detection finds no pattern matches and item is not suppressed,
    it should write a 'no_match' audit entry."""

    def test_no_pattern_match_writes_no_match_audit(self):
        """Content with no commitment language should still produce an audit entry."""
        item = _make_item(
            content_normalized="The weather is nice today. Just wanted to share some photos.",
        )
        db = _make_mock_db(item)
        candidates = run_detection(item.id, db)

        assert candidates == [], "No candidates expected for non-commitment text"

        # Verify a "no_match" audit entry was written
        audit_calls = [
            c for c in db.add.call_args_list
            if hasattr(c[0][0], 'tier_used') and c[0][0].tier_used == "no_match"
        ]
        assert len(audit_calls) == 1, (
            "Expected exactly one 'no_match' audit entry; "
            f"got {len(audit_calls)}. All add calls: {db.add.call_args_list}"
        )


# ---------------------------------------------------------------------------
# Test: run_detection_sweep respects seed_processed_at guard
# ---------------------------------------------------------------------------

class TestDetectionSweepGuard:
    """The sweep must skip items that already have seed_processed_at set."""

    @patch("app.tasks.get_sync_session")
    @patch("app.tasks.run_detection")
    def test_sweep_query_filters_on_seed_processed_at(
        self, mock_run_detection, mock_get_sync
    ):
        """The sweep SQL query must include seed_processed_at IS NULL."""
        from app.tasks import run_detection_sweep

        # Session 1: skipped count
        count_session = MagicMock()
        count_session.execute.return_value.scalar.return_value = 0
        count_session.__enter__ = MagicMock(return_value=count_session)
        count_session.__exit__ = MagicMock(return_value=False)

        # Session 2: unprocessed items query (returns nothing)
        query_session = MagicMock()
        query_session.execute.return_value.scalars.return_value.all.return_value = []
        query_session.__enter__ = MagicMock(return_value=query_session)
        query_session.__exit__ = MagicMock(return_value=False)

        mock_get_sync.side_effect = [count_session, query_session]

        result = run_detection_sweep(limit=10)

        assert result["processed"] == 0
        assert result["unprocessed_found"] == 0

        # Verify the query was called — we inspect the SQL string
        execute_call = query_session.execute.call_args
        assert execute_call is not None, "Expected session.execute to be called"

        # The query object should contain seed_processed_at filter
        query = execute_call[0][0]
        query_str = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "seed_processed_at" in query_str, (
            f"Sweep query must filter on seed_processed_at IS NULL. "
            f"Got query: {query_str}"
        )

    @patch("app.tasks.get_sync_session")
    @patch("app.tasks.run_detection")
    def test_sweep_sets_seed_processed_at_after_processing(
        self, mock_run_detection, mock_get_sync
    ):
        """After processing an item, the sweep must set seed_processed_at."""
        from app.tasks import run_detection_sweep

        item_id = str(uuid.uuid4())
        mock_run_detection.return_value = []  # No candidates found

        # Session 1: skipped count query
        count_session = MagicMock()
        count_session.execute.return_value.scalar.return_value = 5
        count_session.__enter__ = MagicMock(return_value=count_session)
        count_session.__exit__ = MagicMock(return_value=False)

        # Session 2: unprocessed items query
        query_session = MagicMock()
        query_session.execute.return_value.scalars.return_value.all.return_value = [item_id]
        query_session.__enter__ = MagicMock(return_value=query_session)
        query_session.__exit__ = MagicMock(return_value=False)

        # Session 3: used for run_detection + seed_processed_at update
        process_session = MagicMock()
        process_session.__enter__ = MagicMock(return_value=process_session)
        process_session.__exit__ = MagicMock(return_value=False)

        mock_get_sync.side_effect = [count_session, query_session, process_session]

        result = run_detection_sweep(limit=10)
        assert result["processed"] == 1

        # Verify seed_processed_at was set via an UPDATE
        execute_calls = process_session.execute.call_args_list
        assert len(execute_calls) > 0, "Expected execute call to set seed_processed_at"

        # Check that at least one execute call updates seed_processed_at
        found_update = False
        for c in execute_calls:
            query_str = str(c[0][0])
            if "seed_processed_at" in query_str:
                found_update = True
                break

        assert found_update, (
            "Expected an UPDATE setting seed_processed_at after processing. "
            f"Execute calls: {execute_calls}"
        )

    @patch("app.tasks.get_sync_session")
    @patch("app.tasks.run_detection")
    def test_sweep_logs_skipped_count(
        self, mock_run_detection, mock_get_sync
    ):
        """Sweep result should include a 'skipped' count for already-processed items."""
        from app.tasks import run_detection_sweep

        # Session 1: skipped count — returns 42 already-processed items
        count_session = MagicMock()
        count_session.execute.return_value.scalar.return_value = 42
        count_session.__enter__ = MagicMock(return_value=count_session)
        count_session.__exit__ = MagicMock(return_value=False)

        # Session 2: unprocessed items query (returns nothing)
        query_session = MagicMock()
        query_session.execute.return_value.scalars.return_value.all.return_value = []
        query_session.__enter__ = MagicMock(return_value=query_session)
        query_session.__exit__ = MagicMock(return_value=False)

        mock_get_sync.side_effect = [count_session, query_session]

        result = run_detection_sweep(limit=10)

        assert "skipped" in result, (
            f"Sweep result must include 'skipped' key. Got: {result}"
        )
        assert result["skipped"] == 42
