"""Term resolver — maps alias strings to canonical terms + context for enrichment."""
from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, Session

from app.models.orm import CommonTerm

logger = logging.getLogger(__name__)


async def resolve_terms_in_text(
    text: str, user_id: str, db: AsyncSession
) -> list[dict]:
    """Scan text for any known aliases. Return list of matched term contexts.

    Returns list of dicts: [{"alias": "Hatch", "canonical": "GoHighLevel", "context": "..."}]
    Used to inject context into LLM prompts before processing meeting transcripts.
    """
    if not text or not text.strip():
        return []

    result = await db.execute(
        select(CommonTerm)
        .options(selectinload(CommonTerm.aliases))
        .where(CommonTerm.user_id == user_id)
    )
    terms = result.scalars().all()

    if not terms:
        return []

    text_lower = text.lower()
    matches = []
    seen_terms = set()

    for term in terms:
        # Build list of searchable strings: canonical + all aliases
        search_pairs = [(term.canonical_term, term.canonical_term)]
        for alias in term.aliases:
            search_pairs.append((alias.alias, alias.alias))

        for search_str, original in search_pairs:
            if term.id in seen_terms:
                break

            s_lower = search_str.lower()

            if len(search_str) < 4:
                # Short aliases: whole-word exact match only to avoid false positives
                pattern = r'\b' + re.escape(s_lower) + r'\b'
                if re.search(pattern, text_lower):
                    matches.append({
                        "alias": _find_original_case(text, s_lower),
                        "canonical": term.canonical_term,
                        "context": term.context,
                    })
                    seen_terms.add(term.id)
            else:
                # Longer aliases: case-insensitive substring match
                if s_lower in text_lower:
                    matches.append({
                        "alias": _find_original_case(text, s_lower),
                        "canonical": term.canonical_term,
                        "context": term.context,
                    })
                    seen_terms.add(term.id)

    return matches


def _find_original_case(text: str, lower_needle: str) -> str:
    """Find the original-case version of a matched substring in text."""
    idx = text.lower().find(lower_needle)
    if idx >= 0:
        return text[idx:idx + len(lower_needle)]
    return lower_needle


async def get_term_context_block(user_id: str, db: AsyncSession) -> str:
    """Returns a formatted context block for injection into LLM prompts.

    Example output:

    ## Terminology Context
    - "GoHighLevel" (also known as: Hatch, GHL): GoHighLevel is the CRM platform used by KRS.
    - "Aileen" (also known as: Eillyne, Eilynne, Ayleen): Aileen is a team member.

    Returns empty string if no terms defined.
    """
    result = await db.execute(
        select(CommonTerm)
        .options(selectinload(CommonTerm.aliases))
        .where(CommonTerm.user_id == user_id)
    )
    terms = result.scalars().all()

    if not terms:
        return ""

    lines = ["## Terminology Context"]
    for term in terms:
        alias_names = [a.alias for a in term.aliases]
        if alias_names:
            aka = f" (also known as: {', '.join(alias_names)})"
        else:
            aka = ""
        context_str = f": {term.context}" if term.context else ""
        lines.append(f'- "{term.canonical_term}"{aka}{context_str}')

    return "\n".join(lines)


def get_term_context_block_sync(user_id: str, db: Session) -> str:
    """Sync version for use in seed_detector and other sync contexts."""
    result = db.execute(
        select(CommonTerm)
        .options(selectinload(CommonTerm.aliases))
        .where(CommonTerm.user_id == user_id)
    )
    terms = result.scalars().all()

    if not terms:
        return ""

    lines = ["## Terminology Context"]
    for term in terms:
        alias_names = [a.alias for a in term.aliases]
        if alias_names:
            aka = f" (also known as: {', '.join(alias_names)})"
        else:
            aka = ""
        context_str = f": {term.context}" if term.context else ""
        lines.append(f'- "{term.canonical_term}"{aka}{context_str}')

    return "\n".join(lines)
