"""Backfill: create CommitmentSignal(signal_role='origin') for promoted candidates.

Finds all CommitmentCandidates where:
  - was_promoted = true
  - originating_item_id IS NOT NULL
  - No CommitmentSignal with signal_role='origin' exists for the linked commitment

Creates the missing origin signal rows so the frontend can display the
original signal date instead of the ingestion timestamp.

WO: WO-RIPPLED-SIGNAL-LINK-MISSING

Usage:
    python scripts/backfill_origin_signals.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import and_, select, exists

sys.path.insert(0, ".")

from app.db.session import get_sync_session
from app.models.orm import (
    CandidateCommitment,
    CommitmentCandidate,
    CommitmentSignal,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_origin_signals")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill origin signals for promoted candidates")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without doing it")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = all)")
    args = parser.parse_args()

    with get_sync_session() as db:
        # Find promoted candidates that have an originating_item_id
        # but whose commitment lacks an origin signal.
        stmt = (
            select(
                CommitmentCandidate.id,
                CommitmentCandidate.user_id,
                CommitmentCandidate.originating_item_id,
                CommitmentCandidate.confidence_score,
                CandidateCommitment.commitment_id,
            )
            .join(
                CandidateCommitment,
                CandidateCommitment.candidate_id == CommitmentCandidate.id,
            )
            .where(
                and_(
                    CommitmentCandidate.was_promoted.is_(True),
                    CommitmentCandidate.originating_item_id.isnot(None),
                    ~exists(
                        select(CommitmentSignal.id).where(
                            and_(
                                CommitmentSignal.commitment_id == CandidateCommitment.commitment_id,
                                CommitmentSignal.signal_role == "origin",
                            )
                        )
                    ),
                )
            )
        )

        if args.limit > 0:
            stmt = stmt.limit(args.limit)

        rows = db.execute(stmt).all()
        logger.info("Found %d promoted candidates missing origin signals", len(rows))

        if args.dry_run:
            for row in rows:
                logger.info(
                    "  [DRY RUN] Would create signal: commitment=%s ← source_item=%s",
                    row.commitment_id,
                    row.originating_item_id,
                )
            logger.info("Dry run complete — no changes made")
            return

        created = 0
        for row in rows:
            signal = CommitmentSignal(
                commitment_id=row.commitment_id,
                source_item_id=row.originating_item_id,
                user_id=row.user_id,
                signal_role="origin",
                confidence=row.confidence_score,
                interpretation_note=f"Backfill from candidate {row.id}",
            )
            db.add(signal)
            created += 1

        db.commit()
        logger.info("Created %d origin signal rows", created)


if __name__ == "__main__":
    main()
