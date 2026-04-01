"""Backfill entity fields on committed rows with null requester/beneficiary/resolved_owner.

Finds commitments with null entity fields, locates their source candidate,
and re-runs the model to extract requester, beneficiary, deliverable,
speech_act, and user_relationship. Sets resolved_owner = requester_name
as fallback when no identity match.

Usage:
    cd /home/kevinbeeftink/projects/rippled-ai
    source .venv/bin/activate
    python3 scripts/backfill_entity_extraction.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orm import Commitment, CandidateCommitment, CommitmentCandidate
from app.services.model_detection import ModelDetectionService
from app.services.identity.owner_resolver import resolve_party_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill entity fields on commitments")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set — cannot run model extraction.")
        sys.exit(1)

    model_service = ModelDetectionService(
        api_key=settings.openai_api_key,
        model=getattr(settings, "openai_model", "gpt-4.1-mini"),
    )

    with Session(engine) as db:
        # Find commitments with null entity fields
        query = (
            select(Commitment)
            .where(
                Commitment.requester_name.is_(None),
                Commitment.beneficiary_name.is_(None),
            )
            .order_by(Commitment.created_at.desc())
        )
        if args.limit:
            query = query.limit(args.limit)

        commitments = db.execute(query).scalars().all()
        print(f"Found {len(commitments)} commitments with null entity fields.")

        updated = 0
        skipped = 0
        errors = 0

        for c in commitments:
            # Find the source candidate via CandidateCommitment join
            join = db.execute(
                select(CandidateCommitment)
                .where(CandidateCommitment.commitment_id == c.id)
            ).scalars().first()

            if not join:
                skipped += 1
                continue

            candidate = db.get(CommitmentCandidate, join.candidate_id)
            if not candidate or not candidate.raw_text:
                skipped += 1
                continue

            # Call model for entity extraction
            result = model_service.classify(candidate)
            if result is None:
                errors += 1
                print(f"  ERROR: Model returned None for commitment {c.id}")
                continue

            if args.dry_run:
                print(
                    f"  [DRY-RUN] {c.id}: "
                    f"requester={result.requester!r}, "
                    f"beneficiary={result.beneficiary!r}, "
                    f"deliverable={result.deliverable!r}"
                )
                updated += 1
                continue

            # Apply entity fields
            if result.requester:
                c.requester_name = result.requester
            if result.beneficiary:
                c.beneficiary_name = result.beneficiary
            if result.deliverable and not c.deliverable:
                c.deliverable = result.deliverable
            if result.speech_act and not c.speech_act:
                c.speech_act = result.speech_act
            if result.user_relationship and not c.user_relationship:
                c.user_relationship = result.user_relationship

            # Resolve requester against identity profiles
            if c.requester_name:
                resolved = resolve_party_sync(c.requester_name, c.user_id, db)
                if resolved:
                    c.resolved_owner = resolved
                elif not c.resolved_owner:
                    c.resolved_owner = c.requester_name

            updated += 1

        if not args.dry_run:
            db.commit()

        action = "Would update" if args.dry_run else "Updated"
        print(f"\n{action} {updated} commitments. Skipped {skipped}. Errors {errors}.")

        # Verify
        if not args.dry_run:
            stats = db.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved_owner IS NOT NULL THEN 1 ELSE 0 END) as has_owner,
                    SUM(CASE WHEN requester_name IS NOT NULL THEN 1 ELSE 0 END) as has_requester,
                    SUM(CASE WHEN beneficiary_name IS NOT NULL THEN 1 ELSE 0 END) as has_beneficiary
                FROM commitments
            """)).mappings().first()
            print(f"\nVerification:")
            print(f"  Total commitments: {stats['total']}")
            print(f"  Has resolved_owner: {stats['has_owner']}")
            print(f"  Has requester_name: {stats['has_requester']}")
            print(f"  Has beneficiary_name: {stats['has_beneficiary']}")


if __name__ == "__main__":
    main()
