"""Backfill detection_audit rows for source_items processed before audit logging.

Signal Review UI shows "No extraction data" for items that were processed
before detection_audit logging was enabled. This script re-runs detection
on those items so audit rows are created.

Usage:
    cd /home/kevinbeeftink/projects/rippled-ai
    source .venv/bin/activate

    # Preview what would be processed
    python3 scripts/backfill_extraction_data.py --dry-run

    # Process first 50 items
    python3 scripts/backfill_extraction_data.py --limit 50

    # Process all
    python3 scripts/backfill_extraction_data.py
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load .env from project root before any app imports
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orm import DetectionAudit, SourceItem
from app.services.detection import run_detection

logger = logging.getLogger(__name__)


def find_items_without_audit(db: Session, limit: int | None = None) -> list[SourceItem]:
    """Find source_items that have no corresponding detection_audit row."""
    stmt = (
        select(SourceItem)
        .where(
            ~SourceItem.id.in_(
                select(DetectionAudit.source_item_id).distinct()
            )
        )
        .order_by(SourceItem.ingested_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def backfill(dry_run: bool = False, limit: int | None = None) -> dict:
    """Run backfill. Returns summary dict."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    summary = {"total_found": 0, "processed": 0, "skipped": 0, "errors": 0}

    with Session(engine) as db:
        items = find_items_without_audit(db, limit=limit)
        summary["total_found"] = len(items)

        if dry_run:
            print(f"\n[DRY RUN] Found {len(items)} source_items without detection_audit rows:")
            for i, item in enumerate(items, 1):
                content_preview = (item.content_normalized or item.content or "")[:80]
                print(f"  {i}. {item.id} ({item.source_type}) — {content_preview!r}")
            print(f"\nWould process {len(items)} items. Use without --dry-run to execute.")
            return summary

        print(f"\nFound {len(items)} source_items to backfill.\n")

        for i, item in enumerate(items, 1):
            # Double-check idempotency: skip if audit row was created between query and processing
            existing = db.execute(
                select(DetectionAudit.id).where(
                    DetectionAudit.source_item_id == item.id
                ).limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                print(f"  [{i}/{len(items)}] SKIP {item.id} — audit row already exists")
                summary["skipped"] += 1
                continue

            try:
                t0 = time.monotonic()
                candidates = run_detection(str(item.id), db)
                elapsed = time.monotonic() - t0
                db.commit()
                summary["processed"] += 1
                print(
                    f"  [{i}/{len(items)}] OK   {item.id} ({item.source_type}) "
                    f"— {len(candidates)} candidate(s), {elapsed:.1f}s"
                )
            except Exception as exc:
                db.rollback()
                summary["errors"] += 1
                print(f"  [{i}/{len(items)}] ERR  {item.id} — {exc}")
                logger.exception("Backfill error for item %s", item.id)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill detection_audit data for source_items")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    print("=== Backfill Extraction Data ===")
    summary = backfill(dry_run=args.dry_run, limit=args.limit)

    print(f"\n--- Summary ---")
    print(f"  Found:     {summary['total_found']}")
    print(f"  Processed: {summary['processed']}")
    print(f"  Skipped:   {summary['skipped']}")
    print(f"  Errors:    {summary['errors']}")


if __name__ == "__main__":
    main()
