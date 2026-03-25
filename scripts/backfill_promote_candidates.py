"""Backfill: promote eligible commitment_candidates to commitments.

Finds all candidates where:
  - was_promoted = false
  - was_discarded = false
  - observe_until <= now OR observe_until IS NULL OR confidence_score >= 0.75

Runs each through the full clarification pipeline (analyze + promote + clarify).
Idempotent: skips already-promoted candidates.

Usage:
    python scripts/backfill_promote_candidates.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal as D

from sqlalchemy import and_, or_, select

# Ensure app is importable
sys.path.insert(0, ".")

from app.db.session import get_sync_session
from app.models.orm import CommitmentCandidate
from app.services.clarification.clarifier import run_clarification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_promote")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill: promote eligible candidates")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be promoted without doing it")
    parser.add_argument("--limit", type=int, default=0, help="Max candidates to process (0 = all)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)

    with get_sync_session() as db:
        stmt = (
            select(CommitmentCandidate.id)
            .where(
                and_(
                    CommitmentCandidate.was_promoted.is_(False),
                    CommitmentCandidate.was_discarded.is_(False),
                    or_(
                        CommitmentCandidate.observe_until <= now,
                        CommitmentCandidate.observe_until.is_(None),
                        CommitmentCandidate.confidence_score >= D("0.75"),
                    ),
                )
            )
            .order_by(CommitmentCandidate.created_at.asc())
        )
        if args.limit:
            stmt = stmt.limit(args.limit)

        candidate_ids = db.execute(stmt).scalars().all()

    logger.info("Found %d eligible candidates", len(candidate_ids))

    if args.dry_run:
        logger.info("[DRY RUN] Would promote %d candidates. Exiting.", len(candidate_ids))
        return

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
                logger.info("Promoted candidate %s → commitment %s", cid, result.get("commitment_id"))
            elif status == "deferred":
                deferred += 1
            elif status == "skipped":
                skipped += 1
            else:
                logger.warning("Unexpected status for candidate %s: %s", cid, result)
        except Exception:
            errors += 1
            logger.exception("Failed to promote candidate %s", cid)

    logger.info(
        "Backfill complete: promoted=%d deferred=%d skipped=%d errors=%d total=%d",
        promoted, deferred, skipped, errors, len(candidate_ids),
    )


if __name__ == "__main__":
    main()
