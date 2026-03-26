"""Clean seed run — WO-RIPPLED-FULL-DB-RESET-CLEAN-SEED Phase 4.

Runs the full ingestion pipeline synchronously:
1. Email backfill (IMAP, 90 days) for all active email sources
2. Meeting backfill (Read.ai, 90 days) for all active meeting sources
3. Seed detection pass (LLM commitment extraction)

Requires ENCRYPTION_KEY env var to decrypt source credentials.

Usage:
    ENCRYPTION_KEY=<key> .venv/bin/python scripts/clean_seed_run.py --email
    ENCRYPTION_KEY=<key> .venv/bin/python scripts/clean_seed_run.py --meetings
    ENCRYPTION_KEY=<key> .venv/bin/python scripts/clean_seed_run.py --detection
    ENCRYPTION_KEY=<key> .venv/bin/python scripts/clean_seed_run.py --all
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clean_seed_run")


def run_email_backfill() -> dict:
    """Poll all active email sources via IMAP (first sync = 30 day backfill)."""
    from app.connectors.email.imap_poller import poll_all_email_sources

    logger.info("=== EMAIL BACKFILL START ===")
    start = time.monotonic()
    result = poll_all_email_sources()
    elapsed = time.monotonic() - start
    logger.info("=== EMAIL BACKFILL COMPLETE (%.1fs) ===", elapsed)
    logger.info("  Result: %s", result)
    return result


def run_meeting_backfill(days: int = 90) -> dict:
    """Backfill meetings from Read.ai for all active meeting sources."""
    from sqlalchemy import select
    from app.connectors.meeting.readai_backfill import backfill_meetings
    from app.db.session import get_sync_session
    from app.models.orm import Source

    logger.info("=== MEETING BACKFILL START (days=%d) ===", days)
    start = time.monotonic()
    results = []

    with get_sync_session() as db:
        sources = db.execute(
            select(Source).where(
                Source.source_type == "meeting",
                Source.is_active.is_(True),
            )
        ).scalars().all()

        logger.info("Found %d active meeting source(s)", len(sources))

        for source in sources:
            logger.info(
                "  Backfilling meeting source %s (%s)",
                source.id, source.display_name,
            )
            try:
                result = backfill_meetings(source, days=days, db=db)
                results.append(result)
                logger.info("  Result: %s", result)
            except Exception:
                logger.exception("  Error backfilling source %s", source.id)
                results.append({"error": str(source.id)})

    elapsed = time.monotonic() - start
    logger.info("=== MEETING BACKFILL COMPLETE (%.1fs) ===", elapsed)

    total = {
        "sources_processed": len(results),
        "total_fetched": sum(r.get("fetched", 0) for r in results),
        "total_created": sum(r.get("created", 0) for r in results),
        "total_duplicates": sum(r.get("duplicates", 0) for r in results),
        "total_errors": sum(r.get("errors", 0) for r in results),
    }
    logger.info("  Totals: %s", total)
    return total


def run_seed_detection() -> dict:
    """Run LLM seed detection pass for all users with source items."""
    from sqlalchemy import select, func
    from app.db.session import get_sync_session
    from app.models.orm import SourceItem
    from app.services.detection.seed_detector import run_seed_pass, build_user_profile

    logger.info("=== SEED DETECTION START ===")
    start = time.monotonic()

    with get_sync_session() as db:
        # Find all users with unprocessed source items
        user_ids = db.execute(
            select(SourceItem.user_id).where(
                SourceItem.seed_processed_at.is_(None)
            ).group_by(SourceItem.user_id)
        ).scalars().all()

        logger.info("Found %d user(s) with unprocessed source items", len(user_ids))

        results = []
        for user_id in user_ids:
            # Count unprocessed items
            count = db.execute(
                select(func.count()).select_from(SourceItem).where(
                    SourceItem.user_id == user_id,
                    SourceItem.seed_processed_at.is_(None),
                )
            ).scalar()
            logger.info(
                "  Processing user %s (%d unprocessed items)",
                str(user_id)[:8], count,
            )
            try:
                result = run_seed_pass(str(user_id), db)
                results.append(result)
                logger.info("  Result: %s", result)
                # Build user profile from extracted commitments
                build_user_profile(str(user_id), db)
            except Exception:
                logger.exception("  Error processing user %s", user_id)
                results.append({"error": str(user_id)})

    elapsed = time.monotonic() - start
    logger.info("=== SEED DETECTION COMPLETE (%.1fs) ===", elapsed)

    total = {
        "users_processed": len(results),
        "items_processed": sum(r.get("items_processed", 0) for r in results),
        "commitments_created": sum(r.get("commitments_created", 0) for r in results),
        "errors": sum(r.get("errors", 0) for r in results),
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info("  Totals: %s", total)
    return total


def run_status_check() -> dict:
    """Print current DB state after seed run."""
    from sqlalchemy import text
    from app.db.session import get_sync_session

    with get_sync_session() as db:
        tables = [
            "source_items", "normalized_signals", "raw_signal_ingests",
            "commitments", "commitment_candidates", "commitment_signals",
            "detection_audit", "lifecycle_transitions",
        ]
        print("\n=== POST-SEED DB STATE ===")
        counts = {}
        for t in tables:
            result = db.execute(text(f"SELECT COUNT(*) FROM {t}"))
            count = result.scalar()
            counts[t] = count
            print(f"  {t}: {count}")

        # Source items by type
        print("\n  Source items by type:")
        result = db.execute(text(
            "SELECT source_type, COUNT(*) FROM source_items GROUP BY source_type ORDER BY source_type"
        ))
        for row in result:
            print(f"    {row[0]}: {row[1]}")

        # Commitments with owner
        result = db.execute(text(
            "SELECT COUNT(*) FROM commitments WHERE resolved_owner IS NOT NULL"
        ))
        owned = result.scalar()
        print(f"\n  Commitments with resolved_owner: {owned}/{counts.get('commitments', 0)}")

        return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean seed run")
    parser.add_argument("--email", action="store_true", help="Run email IMAP backfill")
    parser.add_argument("--meetings", action="store_true", help="Run Read.ai meeting backfill")
    parser.add_argument("--detection", action="store_true", help="Run seed detection pass")
    parser.add_argument("--status", action="store_true", help="Show current DB state")
    parser.add_argument("--all", action="store_true", help="Run all stages")
    parser.add_argument("--days", type=int, default=90, help="Days of history to fetch")
    args = parser.parse_args()

    if not any([args.email, args.meetings, args.detection, args.status, args.all]):
        parser.print_help()
        sys.exit(1)

    start_time = datetime.now(timezone.utc)
    print(f"\nClean seed run started at {start_time.isoformat()}")

    if args.all or args.email:
        run_email_backfill()

    if args.all or args.meetings:
        run_meeting_backfill(days=args.days)

    if args.all or args.detection:
        run_seed_detection()

    if args.all or args.status:
        run_status_check()

    end_time = datetime.now(timezone.utc)
    print(f"\nClean seed run completed at {end_time.isoformat()}")
    print(f"Total duration: {(end_time - start_time).total_seconds():.1f}s")
