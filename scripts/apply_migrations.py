#!/usr/bin/env python3
"""
Apply SQL migrations idempotently, tracking state in a schema_migrations table.

Usage:
    python scripts/apply_migrations.py
"""

import glob
import os
import sys
from urllib.parse import urlparse

import psycopg2


MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "supabase", "migrations"
)

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""


def get_connection():
    """Connect to PostgreSQL using DATABASE_URL from environment or .env file."""
    # Try loading .env if python-dotenv is available
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL not set. Set it in .env or as an environment variable."
        )

    parsed = urlparse(database_url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
    )


def run_migrations(conn, migrations_dir=None):
    """Apply pending migrations and return (applied_count, skipped_count)."""
    if migrations_dir is None:
        migrations_dir = os.path.abspath(MIGRATIONS_DIR)

    cur = conn.cursor()

    # Ensure tracking table exists
    cur.execute(CREATE_TRACKING_TABLE)
    conn.commit()

    # Get already-applied versions
    cur.execute("SELECT version FROM schema_migrations;")
    applied = {row[0] for row in cur.fetchall()}

    # Discover and sort migration files
    pattern = os.path.join(migrations_dir, "*.sql")
    files = sorted(glob.glob(pattern))

    applied_count = 0
    skipped_count = 0

    for filepath in files:
        version = os.path.basename(filepath)

        if version in applied:
            print(f"Already applied: {version}")
            skipped_count += 1
            continue

        # Apply migration
        with open(filepath, "r") as f:
            sql = f.read()

        try:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s);",
                (version,),
            )
            conn.commit()
            print(f"Applied: {version}")
            applied_count += 1
        except Exception as e:
            conn.rollback()
            print(f"ERROR applying {version}: {e}", file=sys.stderr)
            cur.close()
            return applied_count, skipped_count

    cur.close()
    return applied_count, skipped_count


def main():
    """Entry point. Returns exit code."""
    try:
        conn = get_connection()
    except Exception as e:
        print(f"Connection error: {e}", file=sys.stderr)
        return 1

    try:
        applied, skipped = run_migrations(conn)
        print(f"\nSummary: {applied} applied, {skipped} skipped")
        return 0
    except Exception as e:
        print(f"Migration error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
