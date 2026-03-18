"""One-time script: seed Kevin's identity profiles and backfill resolved_owner.

Usage:
    cd /home/kevinbeeftink/projects/rippled-ai
    source .venv/bin/activate
    python3 scripts/backfill_owner.py
"""
from __future__ import annotations

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orm import Commitment, UserIdentityProfile
from app.services.identity.owner_resolver import resolve_owner_sync

KEVIN_USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"

IDENTITIES = [
    ("full_name", "Kevin Beeftink"),
    ("email", "kevin@kevlex.digital"),
    ("first_name", "Kevin"),
]


def main() -> None:
    settings = get_settings()
    db_url = settings.database_url
    engine = create_engine(db_url)

    with Session(engine) as db:
        # Step 1: Seed Kevin's identity profiles
        print("Seeding identity profiles...")
        for identity_type, identity_value in IDENTITIES:
            db.execute(
                text("""
                    INSERT INTO user_identity_profiles (user_id, identity_type, identity_value, source, confirmed)
                    VALUES (:user_id, :identity_type, :identity_value, 'manual', true)
                    ON CONFLICT (user_id, identity_type, identity_value) DO UPDATE SET confirmed = true
                """),
                {
                    "user_id": KEVIN_USER_ID,
                    "identity_type": identity_type,
                    "identity_value": identity_value,
                },
            )
        db.commit()
        print(f"  Seeded {len(IDENTITIES)} identity profiles for Kevin.")

        # Step 2: Backfill resolved_owner
        print("\nRunning backfill...")
        result = db.execute(
            select(Commitment).where(
                Commitment.user_id == KEVIN_USER_ID,
                Commitment.resolved_owner.is_(None),
                Commitment.suggested_owner.isnot(None),
            )
        )
        commitments = result.scalars().all()
        print(f"  Found {len(commitments)} commitments with suggested_owner but no resolved_owner.")

        updated = 0
        for c in commitments:
            resolved = resolve_owner_sync(c.suggested_owner, KEVIN_USER_ID, db)
            if resolved:
                c.resolved_owner = resolved
                updated += 1

        db.commit()
        print(f"  Updated {updated}/{len(commitments)} commitments with resolved_owner.")

        # Step 3: Verify
        total_resolved = db.execute(
            text("""
                SELECT COUNT(*) FROM commitments
                WHERE user_id = :user_id AND resolved_owner IS NOT NULL
            """),
            {"user_id": KEVIN_USER_ID},
        ).scalar_one()

        total = db.execute(
            text("""
                SELECT COUNT(*) FROM commitments
                WHERE user_id = :user_id
            """),
            {"user_id": KEVIN_USER_ID},
        ).scalar_one()

        print(f"\nVerification: {total_resolved}/{total} commitments now have resolved_owner.")


if __name__ == "__main__":
    main()
