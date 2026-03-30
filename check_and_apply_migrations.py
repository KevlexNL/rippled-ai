#!/usr/bin/env python3
"""Check and apply SQL migrations, tracking state in schema_migrations.

Fixes from WO-2:
  - Correct .env path to project root
  - Check schema_migrations table (not supabase_migrations)
  - Use full filename as version (e.g. 001_create_commitment_contexts.sql)
  - Apply migrations in sorted order
  - Record each applied migration in schema_migrations
  - Idempotent: safe to run multiple times

Usage:
    python check_and_apply_migrations.py
"""

import glob
import os
import sys
from urllib.parse import urlparse

import psycopg2

# Load .env from the project root (same directory as this script)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found. Set it in .env or as an environment variable.")
    sys.exit(1)

MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "supabase", "migrations")

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""


def get_connection():
    """Connect to PostgreSQL using DATABASE_URL."""
    parsed = urlparse(DATABASE_URL)
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
        migrations_dir = MIGRATIONS_DIR

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
        version = os.path.basename(filepath)  # Full filename as version

        if version in applied:
            print(f"Already applied: {version}")
            skipped_count += 1
            continue

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
    """Entry point."""
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
