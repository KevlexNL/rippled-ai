"""Tests for check_and_apply_migrations.py (WO-2 fixes).

Validates:
  - Correct .env path (project root)
  - Uses schema_migrations table (not supabase_migrations)
  - Full filename as version key
  - Idempotent execution
  - Sorted application order
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

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
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "001_first.sql").write_text("CREATE TABLE first (id INT);")
    (d / "002_second.sql").write_text("CREATE TABLE second (id INT);")
    return str(d)


class TestSchemaTableName:
    """Verify we check schema_migrations, not supabase_migrations."""

    def test_creates_schema_migrations_table(self, mock_conn, mock_cursor, migrations_dir):
        from check_and_apply_migrations import run_migrations

        run_migrations(mock_conn, migrations_dir)

        sql_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        # Must create schema_migrations (not supabase_migrations)
        create_calls = [s for s in sql_calls if "CREATE TABLE" in s]
        assert any("schema_migrations" in s for s in create_calls)
        assert not any("supabase_migrations" in s for s in create_calls)

    def test_selects_from_schema_migrations(self, mock_conn, mock_cursor, migrations_dir):
        from check_and_apply_migrations import run_migrations

        run_migrations(mock_conn, migrations_dir)

        sql_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        select_calls = [s for s in sql_calls if "SELECT version FROM" in s]
        assert any("schema_migrations" in s for s in select_calls)
        assert not any("supabase_migrations" in s for s in select_calls)


class TestFullFilenameAsVersion:
    """Verify full filename (e.g. 001_first.sql) is used as version key."""

    def test_version_is_full_filename(self, mock_conn, mock_cursor, migrations_dir):
        from check_and_apply_migrations import run_migrations

        # Mark 001_first.sql as already applied
        mock_cursor.fetchall.return_value = [("001_first.sql",)]

        applied, skipped = run_migrations(mock_conn, migrations_dir)

        assert skipped == 1
        assert applied == 1  # only 002_second.sql

    def test_prefix_only_does_not_match(self, mock_conn, mock_cursor, migrations_dir):
        """Old bug: used split('_', 1)[0] which extracted just '001'."""
        from check_and_apply_migrations import run_migrations

        # If the old code stored just "001", it should NOT match "001_first.sql"
        mock_cursor.fetchall.return_value = [("001",)]

        applied, skipped = run_migrations(mock_conn, migrations_dir)

        # Both should be applied since "001" != "001_first.sql"
        assert applied == 2
        assert skipped == 0


class TestIdempotency:
    """Running twice produces same result."""

    def test_second_run_skips_all(self, mock_conn, mock_cursor, migrations_dir):
        from check_and_apply_migrations import run_migrations

        # First run
        mock_cursor.fetchall.return_value = []
        applied1, skipped1 = run_migrations(mock_conn, migrations_dir)
        assert applied1 == 2

        # Second run — all now applied
        mock_cursor.fetchall.return_value = [("001_first.sql",), ("002_second.sql",)]
        mock_cursor.execute.reset_mock()
        applied2, skipped2 = run_migrations(mock_conn, migrations_dir)
        assert applied2 == 0
        assert skipped2 == 2


class TestSortedOrder:
    """Migrations are applied in sorted filename order."""

    def test_applies_in_sorted_order(self, mock_conn, mock_cursor, tmp_path):
        from check_and_apply_migrations import run_migrations

        d = tmp_path / "migrations"
        d.mkdir()
        # Create out of order
        (d / "003_third.sql").write_text("SELECT 3;")
        (d / "001_first.sql").write_text("SELECT 1;")
        (d / "002_second.sql").write_text("SELECT 2;")

        mock_cursor.fetchall.return_value = []
        run_migrations(mock_conn, str(d))

        sql_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        # Filter to just the migration SQL (not CREATE TABLE or SELECT version or INSERT)
        migration_sqls = [s for s in sql_calls if s.startswith("SELECT ") and s[7].isdigit()]
        assert migration_sqls == ["SELECT 1;", "SELECT 2;", "SELECT 3;"]


class TestEnvPath:
    """Verify .env path points to project root."""

    def test_env_path_is_project_root(self):
        import check_and_apply_migrations as m

        project_root = os.path.dirname(os.path.abspath(m.__file__))
        expected = os.path.join(project_root, ".env")
        assert m.ENV_PATH == expected
