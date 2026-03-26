"""Full database reset for clean seed run — WO-RIPPLED-FULL-DB-RESET-CLEAN-SEED.

Truncates all data tables, cleans up test users/sources, and resets
last_synced_at on active sources to force a full re-fetch.

Preserves:
  - Real users (kevin.beeftink@gmail.com and any non-test users)
  - Active, real sources (email, Slack, meeting connectors)
  - user_settings for real users
  - user_identity_profiles for real users

Usage:
    .venv/bin/python scripts/full_db_reset.py --dry-run   # Preview only
    .venv/bin/python scripts/full_db_reset.py --execute    # Actually run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import text

# Ensure project root is on the path
sys.path.insert(0, ".")
from app.db.session import get_sync_session


# Tables to TRUNCATE — order doesn't matter because we use CASCADE.
# These are ALL data tables; config tables (users, sources, user_settings,
# user_identity_profiles) are handled separately.
DATA_TABLES = [
    "candidate_signal_records",
    "signal_processing_stage_runs",
    "signal_processing_runs",
    "llm_judge_runs",
    "candidate_commitments",
    "commitment_event_links",
    "commitment_signals",
    "commitment_ambiguities",
    "lifecycle_transitions",
    "surfacing_audit",
    "clarifications",
    "signal_feedback",
    "outcome_feedback",
    "adhoc_signals",
    "detection_audit",
    "eval_run_items",
    "eval_runs",
    "eval_datasets",
    "digest_log",
    "commitment_contexts",
    "commitments",
    "commitment_candidates",
    "events",
    "normalization_runs",
    "normalized_signals",
    "raw_signal_ingests",
    "source_items",
    "user_commitment_profiles",
]

# Test user patterns — will be deleted
TEST_USER_PATTERNS = [
    "%@test.com",
    "%@rippled.internal",
    "updated@example.com",
]

# Test/inactive source patterns — will be deleted
TEST_SOURCE_NAMES = [
    "learning-loop-test",
    "updated@example.com",
]


def run_reset(dry_run: bool = True) -> dict:
    """Execute the full database reset."""
    stats: dict = {}

    with get_sync_session() as db:
        # --- Step 1: Pre-reset counts ---
        print("\n=== PRE-RESET STATE ===")
        for table in DATA_TABLES:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            if count > 0:
                print(f"  {table}: {count}")
        stats["pre_reset_checked"] = True

        if dry_run:
            print("\n[DRY RUN] Would truncate all data tables listed above.")
            print("[DRY RUN] Would delete test users and inactive sources.")
            print("[DRY RUN] Would reset last_synced_at on active sources.")

            # Show what would be deleted
            for pattern in TEST_USER_PATTERNS:
                result = db.execute(
                    text("SELECT email FROM users WHERE email LIKE :p"),
                    {"p": pattern},
                )
                emails = [row[0] for row in result]
                if emails:
                    print(f"  [DRY RUN] Would delete users: {emails}")

            for name in TEST_SOURCE_NAMES:
                result = db.execute(
                    text(
                        "SELECT id::text, display_name FROM sources WHERE display_name = :n"
                    ),
                    {"n": name},
                )
                sources = [(row[0][:8], row[1]) for row in result]
                if sources:
                    print(f"  [DRY RUN] Would delete sources: {sources}")

            result = db.execute(
                text(
                    "SELECT id::text, display_name, source_type FROM sources "
                    "WHERE is_active = false"
                )
            )
            inactive = [(row[0][:8], row[1], row[2]) for row in result]
            if inactive:
                print(f"  [DRY RUN] Would delete inactive sources: {inactive}")

            db.rollback()
            return {"status": "dry_run", "stats": stats}

        # --- Step 2: TRUNCATE all data tables ---
        print("\n=== TRUNCATING DATA TABLES ===")
        table_list = ", ".join(DATA_TABLES)
        db.execute(text(f"TRUNCATE {table_list} CASCADE"))
        print(f"  Truncated {len(DATA_TABLES)} tables.")
        stats["tables_truncated"] = len(DATA_TABLES)

        # --- Step 3: Delete test users ---
        print("\n=== CLEANING UP TEST USERS ===")
        total_deleted_users = 0
        for pattern in TEST_USER_PATTERNS:
            # First delete any sources owned by test users (and their settings)
            result = db.execute(
                text(
                    "DELETE FROM sources WHERE user_id IN "
                    "(SELECT id FROM users WHERE email LIKE :p)"
                ),
                {"p": pattern},
            )
            if result.rowcount > 0:
                print(f"  Deleted {result.rowcount} sources for pattern {pattern}")

            result = db.execute(
                text(
                    "DELETE FROM user_settings WHERE user_id IN "
                    "(SELECT id FROM users WHERE email LIKE :p)"
                ),
                {"p": pattern},
            )

            result = db.execute(
                text(
                    "DELETE FROM user_identity_profiles WHERE user_id IN "
                    "(SELECT id FROM users WHERE email LIKE :p)"
                ),
                {"p": pattern},
            )

            result = db.execute(
                text("DELETE FROM users WHERE email LIKE :p"),
                {"p": pattern},
            )
            total_deleted_users += result.rowcount
            if result.rowcount > 0:
                print(f"  Deleted {result.rowcount} users matching {pattern}")
        stats["users_deleted"] = total_deleted_users

        # --- Step 4: Delete test/inactive sources ---
        print("\n=== CLEANING UP TEST/INACTIVE SOURCES ===")
        total_deleted_sources = 0
        for name in TEST_SOURCE_NAMES:
            result = db.execute(
                text("DELETE FROM sources WHERE display_name = :n"),
                {"n": name},
            )
            total_deleted_sources += result.rowcount
            if result.rowcount > 0:
                print(f"  Deleted {result.rowcount} sources named '{name}'")

        # Delete inactive sources
        result = db.execute(
            text("DELETE FROM sources WHERE is_active = false"),
        )
        total_deleted_sources += result.rowcount
        if result.rowcount > 0:
            print(f"  Deleted {result.rowcount} inactive sources")
        stats["sources_deleted"] = total_deleted_sources

        # --- Step 5: Reset last_synced_at on remaining sources ---
        print("\n=== RESETTING LAST_SYNCED_AT ===")
        result = db.execute(
            text("UPDATE sources SET last_synced_at = NULL WHERE last_synced_at IS NOT NULL")
        )
        print(f"  Reset last_synced_at on {result.rowcount} sources")
        stats["sources_reset"] = result.rowcount

        # --- Step 6: Verify ---
        print("\n=== POST-RESET STATE ===")
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        stats["remaining_users"] = result.scalar()
        print(f"  Users remaining: {stats['remaining_users']}")

        result = db.execute(text("SELECT COUNT(*) FROM sources"))
        stats["remaining_sources"] = result.scalar()
        print(f"  Sources remaining: {stats['remaining_sources']}")

        result = db.execute(
            text(
                "SELECT id::text, source_type, display_name, is_active "
                "FROM sources ORDER BY source_type"
            )
        )
        for row in result:
            print(f"    {row[1]} | {row[2]} | active={row[3]}")

        result = db.execute(
            text("SELECT id::text, email FROM users ORDER BY email")
        )
        for row in result:
            print(f"    {row[1]}")

        for table in DATA_TABLES:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            if count > 0:
                print(f"  WARNING: {table} still has {count} rows!")

        db.commit()
        print("\n=== RESET COMPLETE ===")
        print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
        stats["status"] = "complete"
        return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full DB reset for clean seed run")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes only")
    group.add_argument("--execute", action="store_true", help="Execute the reset")
    args = parser.parse_args()

    result = run_reset(dry_run=args.dry_run)
    print(f"\nResult: {result}")
