"""Backfill commitment structure fields (counterparty_resolved, user_relationship, structure_complete).

Iterates existing commitments and populates new fields based on:
- counterparty_resolved: from existing counterparty_name
- user_relationship: inferred from resolved_owner vs user identity profiles
- structure_complete: True if owner AND deliverable AND counterparty are all populated

Usage:
    python scripts/backfill_commitment_structure.py

Requires DATABASE_URL in .env. Safe to re-run (idempotent).
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.orm import Commitment


def get_user_identities(session: Session, user_id: str) -> set[str]:
    """Fetch all known identity values (names, emails) for a user."""
    identities: set[str] = set()
    try:
        rows = session.execute(
            text("SELECT identity_value FROM user_identity_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        for row in rows:
            identities.add(row[0].lower().strip())
    except Exception:
        pass  # Table may not exist yet

    # Also fetch user email and display_name
    try:
        user_row = session.execute(
            text("SELECT email, display_name FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()
        if user_row:
            if user_row[0]:
                identities.add(user_row[0].lower().strip())
            if user_row[1]:
                identities.add(user_row[1].lower().strip())
                # Also add individual name parts
                for part in user_row[1].lower().split():
                    identities.add(part.strip())
    except Exception:
        pass

    return identities


def owner_matches_user(owner: str, identities: set[str]) -> bool:
    """Check if an owner string matches any known user identity."""
    lower = owner.lower().strip()
    for identity in identities:
        if identity in lower or lower in identity:
            return True
    return False


def backfill():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment")
        sys.exit(1)

    # Convert async URL to sync
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        commitments = session.execute(select(Commitment)).scalars().all()
        print(f"Found {len(commitments)} commitments to backfill")

        updated = 0
        identity_cache: dict[str, set[str]] = {}

        for c in commitments:
            changed = False

            # 1. Populate counterparty_resolved from counterparty_name if not set
            if not c.counterparty_resolved and c.counterparty_name:
                c.counterparty_resolved = c.counterparty_name
                changed = True

            # 2. Determine user_relationship
            if not c.user_relationship:
                # Get user identities (cached per user_id)
                if c.user_id not in identity_cache:
                    identity_cache[c.user_id] = get_user_identities(session, c.user_id)
                identities = identity_cache[c.user_id]

                owner = c.resolved_owner or c.suggested_owner
                if owner and owner_matches_user(owner, identities):
                    c.user_relationship = "mine"
                elif owner:
                    c.user_relationship = "watching"
                else:
                    # No owner — default to mine (user's own commitment space)
                    c.user_relationship = "mine"
                changed = True

            # 3. Compute structure_complete
            has_owner = bool(c.resolved_owner or c.suggested_owner)
            has_deliverable = bool(c.deliverable or c.title)
            has_counterparty = bool(c.counterparty_resolved or c.counterparty_name)
            new_complete = has_owner and has_deliverable and has_counterparty

            if c.structure_complete != new_complete:
                c.structure_complete = new_complete
                changed = True

            if changed:
                updated += 1

        session.commit()
        print(f"Backfill complete: {updated}/{len(commitments)} commitments updated")

        # Summary stats
        mine_count = sum(1 for c in commitments if c.user_relationship == "mine")
        contributing_count = sum(1 for c in commitments if c.user_relationship == "contributing")
        watching_count = sum(1 for c in commitments if c.user_relationship == "watching")
        complete_count = sum(1 for c in commitments if c.structure_complete)
        incomplete_count = sum(1 for c in commitments if not c.structure_complete)

        print(f"  mine: {mine_count}, contributing: {contributing_count}, watching: {watching_count}")
        print(f"  structure_complete: {complete_count}, incomplete: {incomplete_count}")


if __name__ == "__main__":
    backfill()
