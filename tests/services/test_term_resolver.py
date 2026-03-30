"""Tests for term resolver service.

Tests verify:
- resolve_terms_in_text finds aliases case-insensitively
- get_term_context_block returns correctly formatted output
- Empty terms returns empty string
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.orm import CommonTerm, CommonTermAlias
from app.services.identity.term_resolver import (
    get_term_context_block,
    resolve_terms_in_text,
)


_term_counter = 0


def _make_term(canonical, context, aliases):
    global _term_counter
    _term_counter += 1
    t = CommonTerm()
    t.id = f"term-{_term_counter}"
    t.canonical_term = canonical
    t.context = context
    t.aliases = []
    for alias_str in aliases:
        a = CommonTermAlias()
        a.alias = alias_str
        a.term = t
        t.aliases.append(a)
    return t


class _FakeScalars:
    def __init__(self, items):
        self._items = items
    def all(self):
        return self._items


def _mock_db_with_terms(terms):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value = _FakeScalars(terms)
    db.execute = AsyncMock(return_value=result)
    return db


USER_ID = "test-user-001"


class TestResolveTermsInText:
    @pytest.mark.asyncio
    async def test_finds_alias_case_insensitive(self):
        terms = [_make_term("GoHighLevel", "CRM platform", ["Hatch", "GHL"])]
        db = _mock_db_with_terms(terms)

        matches = await resolve_terms_in_text("We need to update hatch today", USER_ID, db)
        assert len(matches) == 1
        assert matches[0]["alias"] == "hatch"
        assert matches[0]["canonical"] == "GoHighLevel"

    @pytest.mark.asyncio
    async def test_finds_multiple_aliases(self):
        terms = [
            _make_term("GoHighLevel", "CRM", ["Hatch", "GHL"]),
            _make_term("Aileen", "Team member", ["Eillyne", "Eilynne"]),
        ]
        db = _mock_db_with_terms(terms)

        text = "Eillyne will update GHL with the new leads"
        matches = await resolve_terms_in_text(text, USER_ID, db)
        assert len(matches) == 2
        canonicals = {m["canonical"] for m in matches}
        assert canonicals == {"GoHighLevel", "Aileen"}

    @pytest.mark.asyncio
    async def test_short_alias_exact_match_only(self):
        """Short aliases (< 4 chars) should not match as substrings."""
        terms = [_make_term("GoHighLevel", "CRM", ["GHL"])]
        db = _mock_db_with_terms(terms)

        # "GHL" should not match inside "TGHLX" (substring)
        matches = await resolve_terms_in_text("Check TGHLX status", USER_ID, db)
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_no_terms_returns_empty(self):
        db = _mock_db_with_terms([])
        matches = await resolve_terms_in_text("some text", USER_ID, db)
        assert matches == []

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self):
        terms = [_make_term("GoHighLevel", "CRM", ["Hatch"])]
        db = _mock_db_with_terms(terms)
        matches = await resolve_terms_in_text("nothing relevant here", USER_ID, db)
        assert matches == []

    @pytest.mark.asyncio
    async def test_canonical_term_also_matches(self):
        terms = [_make_term("GoHighLevel", "CRM", ["Hatch"])]
        db = _mock_db_with_terms(terms)
        matches = await resolve_terms_in_text("Update GoHighLevel config", USER_ID, db)
        assert len(matches) == 1
        assert matches[0]["alias"] == "GoHighLevel"
        assert matches[0]["canonical"] == "GoHighLevel"


class TestGetTermContextBlock:
    @pytest.mark.asyncio
    async def test_returns_formatted_block(self):
        terms = [
            _make_term("GoHighLevel", "GoHighLevel is the CRM platform used by KRS.", ["Hatch", "GHL"]),
            _make_term("Aileen", "Aileen is a team member whose name is often misspelled.", ["Eillyne", "Eilynne", "Ayleen"]),
        ]
        db = _mock_db_with_terms(terms)

        block = await get_term_context_block(USER_ID, db)
        assert block.startswith("## Terminology Context")
        assert '"GoHighLevel"' in block
        assert "Hatch" in block
        assert "GHL" in block
        assert '"Aileen"' in block
        assert "Eillyne" in block

    @pytest.mark.asyncio
    async def test_empty_terms_returns_empty_string(self):
        db = _mock_db_with_terms([])
        block = await get_term_context_block(USER_ID, db)
        assert block == ""

    @pytest.mark.asyncio
    async def test_term_without_context(self):
        terms = [_make_term("GoHighLevel", None, ["Hatch"])]
        db = _mock_db_with_terms(terms)

        block = await get_term_context_block(USER_ID, db)
        assert '"GoHighLevel"' in block
        assert "Hatch" in block
