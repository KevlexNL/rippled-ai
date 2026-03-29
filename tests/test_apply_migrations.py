"""Tests for scripts/apply_migrations.py"""

import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# Add project root to path so we can import the script as a module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    return cursor


@pytest.fixture
def mock_conn(mock_cursor):
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    return conn


@pytest.fixture
def migrations_dir(tmp_path):
    """Create a temp directory with fake migration SQL files."""
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "001_first.sql").write_text("CREATE TABLE first (id INT);")
    (d / "002_second.sql").write_text("CREATE TABLE second (id INT);")
    (d / "003_third.sql").write_text("CREATE TABLE third (id INT);")
    return str(d)


class TestNewMigrationApplied:
    """test_new_migration_applied: verify new migration file gets executed and recorded."""

    def test_applies_all_when_none_recorded(self, mock_conn, mock_cursor, migrations_dir):
        from scripts.apply_migrations import run_migrations

        # No migrations applied yet
        mock_cursor.fetchall.return_value = []

        applied, skipped = run_migrations(mock_conn, migrations_dir)

        assert applied == 3
        assert skipped == 0

        # Verify each migration SQL was executed
        execute_calls = mock_cursor.execute.call_args_list
        # Calls: CREATE TABLE schema_migrations, SELECT versions, then for each migration: execute SQL + INSERT
        sql_texts = [c[0][0] for c in execute_calls]

        # Should contain the CREATE TABLE IF NOT EXISTS for schema_migrations
        assert any("schema_migrations" in s and "CREATE TABLE" in s for s in sql_texts)
        # Should contain the migration SQL
        assert any("CREATE TABLE first" in s for s in sql_texts)
        assert any("CREATE TABLE second" in s for s in sql_texts)
        assert any("CREATE TABLE third" in s for s in sql_texts)
        # Should contain INSERT for each migration
        insert_calls = [s for s in sql_texts if "INSERT INTO schema_migrations" in s]
        assert len(insert_calls) == 3

    def test_applies_only_new_migrations(self, mock_conn, mock_cursor, migrations_dir):
        from scripts.apply_migrations import run_migrations

        # First two already applied
        mock_cursor.fetchall.return_value = [("001_first.sql",), ("002_second.sql",)]

        applied, skipped = run_migrations(mock_conn, migrations_dir)

        assert applied == 1
        assert skipped == 2

        sql_texts = [c[0][0] for c in mock_cursor.execute.call_args_list]
        assert any("CREATE TABLE third" in s for s in sql_texts)
        assert not any("CREATE TABLE first" in s for s in sql_texts)
        assert not any("CREATE TABLE second" in s for s in sql_texts)


class TestAlreadyAppliedSkipped:
    """test_already_applied_skipped: verify already-recorded migration is skipped."""

    def test_all_applied_skips_all(self, mock_conn, mock_cursor, migrations_dir):
        from scripts.apply_migrations import run_migrations

        mock_cursor.fetchall.return_value = [
            ("001_first.sql",),
            ("002_second.sql",),
            ("003_third.sql",),
        ]

        applied, skipped = run_migrations(mock_conn, migrations_dir)

        assert applied == 0
        assert skipped == 3

        sql_texts = [c[0][0] for c in mock_cursor.execute.call_args_list]
        # No migration SQL should have been executed
        assert not any("CREATE TABLE first" in s for s in sql_texts)
        assert not any("CREATE TABLE second" in s for s in sql_texts)
        assert not any("CREATE TABLE third" in s for s in sql_texts)


class TestIdempotent:
    """test_idempotent: run twice, verify schema_migrations has no duplicates."""

    def test_run_twice_no_duplicates(self, mock_conn, mock_cursor, migrations_dir):
        from scripts.apply_migrations import run_migrations

        # First run: nothing applied yet
        mock_cursor.fetchall.return_value = []
        applied1, skipped1 = run_migrations(mock_conn, migrations_dir)
        assert applied1 == 3
        assert skipped1 == 0

        # Second run: all now recorded
        mock_cursor.fetchall.return_value = [
            ("001_first.sql",),
            ("002_second.sql",),
            ("003_third.sql",),
        ]
        mock_cursor.execute.reset_mock()
        applied2, skipped2 = run_migrations(mock_conn, migrations_dir)
        assert applied2 == 0
        assert skipped2 == 3

        # No INSERT calls on second run
        sql_texts = [c[0][0] for c in mock_cursor.execute.call_args_list]
        insert_calls = [s for s in sql_texts if "INSERT INTO schema_migrations" in s]
        assert len(insert_calls) == 0


class TestEmptyMigrationsDir:
    """Edge case: no migration files at all."""

    def test_empty_dir(self, mock_conn, mock_cursor, tmp_path):
        from scripts.apply_migrations import run_migrations

        empty_dir = str(tmp_path / "empty")
        os.makedirs(empty_dir)

        applied, skipped = run_migrations(mock_conn, empty_dir)
        assert applied == 0
        assert skipped == 0


class TestConnectionError:
    """Test that connection errors are handled."""

    @patch("scripts.apply_migrations.get_connection")
    def test_connection_failure_exits_with_error(self, mock_get_conn):
        from scripts.apply_migrations import main

        mock_get_conn.side_effect = Exception("Connection refused")

        exit_code = main()
        assert exit_code == 1
