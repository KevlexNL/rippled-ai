"""Micro-seed — targeted pipeline run on a small set of items.

Runs detection + candidate promotion on selected items.
Additive only — does NOT truncate anything. Idempotent via seed_processed_at.

Usage:
    python scripts/micro_seed.py --type email --count 5
    python scripts/micro_seed.py --type slack --count 3
    python scripts/micro_seed.py --type meeting --count 2
    python scripts/micro_seed.py --all --count-per-type 3
    python scripts/micro_seed.py --ids <id1> <id2> <id3>
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal as D

sys.path.insert(0, ".")

from sqlalchemy import and_, func, or_, select, update
from app.db.session import get_sync_session
from app.models.orm import CommitmentCandidate, SourceItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("micro_seed")

SOURCE_TYPES = ["email", "slack", "meeting"]


# ---------------------------------------------------------------------------
# Item selection
# ---------------------------------------------------------------------------

def _select_items_by_type(source_type: str, count: int) -> list[str]:
    """Get IDs of recent unprocessed items of a given type."""
    with get_sync_session() as db:
        ids = db.execute(
            select(SourceItem.id)
            .where(
                SourceItem.source_type == source_type,
                SourceItem.is_quoted_content.is_(False),
            )
            .order_by(SourceItem.occurred_at.desc())
            .limit(count)
        ).scalars().all()
    return [str(i) for i in ids]


def _select_all_types(count_per_type: int) -> list[str]:
    """Get recent items across all available types."""
    all_ids = []
    for st in SOURCE_TYPES:
        ids = _select_items_by_type(st, count_per_type)
        if ids:
            logger.info("  %s: %d items selected", st, len(ids))
            all_ids.extend(ids)
        else:
            logger.info("  %s: no items available", st)
    return all_ids


# ---------------------------------------------------------------------------
# Detection phase
# ---------------------------------------------------------------------------

def _run_detection(item_ids: list[str]) -> dict:
    """Run detection pipeline on selected items."""
    from app.services.detection import run_detection

    total = len(item_ids)
    processed = 0
    candidates_created = 0
    errors = 0
    skipped = 0

    for i, item_id in enumerate(item_ids, 1):
        try:
            with get_sync_session() as db:
                # Check if already processed
                item = db.get(SourceItem, item_id)
                if item is None:
                    logger.warning("  [%d/%d] Item %s not found — skipping", i, total, item_id)
                    errors += 1
                    continue

                result = run_detection(str(item_id), db)

                # Mark as processed
                db.execute(
                    update(SourceItem)
                    .where(SourceItem.id == item_id)
                    .values(seed_processed_at=func.now())
                )
                db.commit()

            n_candidates = len(result) if result else 0
            candidates_created += n_candidates
            processed += 1

            status = f"{n_candidates} candidate(s)" if n_candidates else "no match"
            logger.info("  [%d/%d] %s — %s (%s)", i, total, item_id[:8], status,
                       item.source_type)

        except Exception as e:
            errors += 1
            logger.error("  [%d/%d] Error on %s: %s", i, total, item_id[:8], e)
            # Still mark as processed to avoid infinite retries
            try:
                with get_sync_session() as db:
                    db.execute(
                        update(SourceItem)
                        .where(SourceItem.id == item_id)
                        .values(seed_processed_at=func.now())
                    )
                    db.commit()
            except Exception:
                pass

    return {
        "total": total,
        "processed": processed,
        "candidates_created": candidates_created,
        "errors": errors,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Promotion phase
# ---------------------------------------------------------------------------

def _run_promotion(item_ids: list[str]) -> dict:
    """Run clarification/promotion on candidates from the seeded items."""
    from app.services.clarification import run_clarification

    now = datetime.now(timezone.utc)

    # Find eligible candidates from the items we just processed
    with get_sync_session() as db:
        candidate_ids = db.execute(
            select(CommitmentCandidate.id).where(
                and_(
                    CommitmentCandidate.originating_item_id.in_(item_ids),
                    CommitmentCandidate.was_promoted.is_(False),
                    CommitmentCandidate.was_discarded.is_(False),
                    or_(
                        CommitmentCandidate.observe_until <= now,
                        CommitmentCandidate.observe_until.is_(None),
                        CommitmentCandidate.confidence_score >= D("0.75"),
                    ),
                )
            ).order_by(CommitmentCandidate.created_at.asc())
        ).scalars().all()

    promoted = 0
    deferred = 0
    skipped = 0
    errors = 0

    for cid in candidate_ids:
        try:
            with get_sync_session() as db:
                result = run_clarification(str(cid), db)
            status = result.get("status", "unknown")
            if status == "clarified":
                promoted += 1
                logger.info("  Promoted candidate %s → commitment %s",
                           str(cid)[:8], result.get("commitment_id", "?")[:8])
            elif status == "deferred":
                deferred += 1
            elif status == "skipped":
                skipped += 1
        except Exception as e:
            errors += 1
            logger.error("  Promotion error for %s: %s", str(cid)[:8], e)

    return {
        "eligible": len(candidate_ids),
        "promoted": promoted,
        "deferred": deferred,
        "skipped": skipped,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Micro-seed — targeted detection + promotion on a small set of items"
    )
    parser.add_argument("--type", type=str, choices=SOURCE_TYPES,
                        help="Source type to seed (email, slack, meeting)")
    parser.add_argument("--count", type=int, default=5,
                        help="Number of items to process (default: 5)")
    parser.add_argument("--all", action="store_true",
                        help="Seed items from all available source types")
    parser.add_argument("--count-per-type", type=int, default=3,
                        help="Items per type when using --all (default: 3)")
    parser.add_argument("--ids", nargs="+", type=str,
                        help="Specific source_item IDs to process")
    parser.add_argument("--skip-promotion", action="store_true",
                        help="Skip the promotion phase (detection only)")
    args = parser.parse_args()

    if not args.type and not args.all and not args.ids:
        parser.print_help()
        sys.exit(1)

    start = time.monotonic()
    logger.info("═══ MICRO-SEED START ═══")

    # Resolve item IDs
    if args.ids:
        item_ids = args.ids
        logger.info("Processing %d specific item(s)", len(item_ids))
    elif args.all:
        logger.info("Selecting up to %d items per type across all types", args.count_per_type)
        item_ids = _select_all_types(args.count_per_type)
    else:
        logger.info("Selecting up to %d %s item(s)", args.count, args.type)
        item_ids = _select_items_by_type(args.type, args.count)

    if not item_ids:
        logger.info("No items found — nothing to do.")
        return

    logger.info("Selected %d item(s) for processing", len(item_ids))

    # Phase 1: Detection
    logger.info("── PHASE 1: DETECTION ──")
    det_result = _run_detection(item_ids)
    logger.info(
        "Detection: processed=%d candidates=%d errors=%d",
        det_result["processed"], det_result["candidates_created"], det_result["errors"],
    )

    # Phase 2: Promotion
    if not args.skip_promotion:
        logger.info("── PHASE 2: PROMOTION ──")
        promo_result = _run_promotion(item_ids)
        logger.info(
            "Promotion: eligible=%d promoted=%d deferred=%d skipped=%d errors=%d",
            promo_result["eligible"], promo_result["promoted"],
            promo_result["deferred"], promo_result["skipped"], promo_result["errors"],
        )

    elapsed = time.monotonic() - start
    logger.info("═══ MICRO-SEED COMPLETE (%.1fs) ═══", elapsed)


if __name__ == "__main__":
    main()
