"""Tests for common terms API routes.

Tests verify:
- GET /api/v1/identity/terms — list terms with aliases for current user
- POST /api/v1/identity/terms — create a term with optional aliases
- PATCH /api/v1/identity/terms/{id} — update canonical_term / context
- DELETE /api/v1/identity/terms/{id} — delete a term (cascades aliases)
- POST /api/v1/identity/terms/{id}/aliases — add an alias
- DELETE /api/v1/identity/terms/{id}/aliases/{alias_id} — remove an alias
- Scoping: user A cannot see/modify user B's terms
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.models.orm import CommonTerm, CommonTermAlias

client = TestClient(app)
URL_PREFIX = "/api/v1/identity/terms"
USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"
OTHER_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
USER_HEADERS = {"X-User-ID": USER_ID}
OTHER_HEADERS = {"X-User-ID": OTHER_USER_ID}

NOW = datetime.now(timezone.utc)


def _make_alias(id: str, term_id: str, alias: str) -> CommonTermAlias:
    a = CommonTermAlias()
    a.id = id
    a.term_id = term_id
    a.alias = alias
    a.source = "manual"
    a.created_at = NOW
    return a


def _make_term(
    id: str = "term-001",
    user_id: str = USER_ID,
    canonical_term: str = "GoHighLevel",
    context: str | None = "GoHighLevel is the CRM platform used by KRS.",
    aliases: list[tuple[str, str]] | None = None,
) -> CommonTerm:
    t = CommonTerm()
    t.id = id
    t.user_id = user_id
    t.canonical_term = canonical_term
    t.context = context
    t.created_at = NOW
    t.updated_at = NOW
    t.aliases = []
    for alias_id, alias_val in (aliases or []):
        a = CommonTermAlias()
        a.id = alias_id
        a.term_id = id
        a.alias = alias_val
        a.source = "manual"
        a.created_at = NOW
        a.term = t
        t.aliases.append(a)
    return t


class _FakeScalars:
    def __init__(self, items):
        self._items = items
    def all(self):
        return self._items
    def unique(self):
        return self
    def __iter__(self):
        return iter(self._items)


def _make_execute_result(items):
    result = MagicMock()
    result.scalars.return_value = _FakeScalars(items)
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


def _make_unique_result(items):
    """Create a mock result that supports .scalars().unique().all() chain."""
    class _UniqueScalars:
        def __init__(self, items):
            self._items = items
        def all(self):
            return self._items
        def unique(self):
            return self
        def __iter__(self):
            return iter(self._items)

    result = MagicMock()
    result.scalars.return_value = _UniqueScalars(items)
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


def _override_db(mock_db):
    from app.db.deps import get_db
    async def override():
        yield mock_db
    app.dependency_overrides[get_db] = override


def _cleanup_db():
    from app.db.deps import get_db
    app.dependency_overrides.pop(get_db, None)


# ── LIST ─────────────────────────────────────────────────────────────────

class TestListTerms:
    def test_returns_terms_with_aliases(self):
        t1_aliases = [_make_alias("a1", "t1", "Hatch"), _make_alias("a2", "t1", "GHL")]
        t2_aliases = [_make_alias("a3", "t2", "Eillyne")]
        t1 = _make_term(id="t1")
        t2 = _make_term(id="t2", canonical_term="Aileen")
        # Don't set aliases on term objects — let the route load them via separate queries
        t1.aliases = []
        t2.aliases = []

        call_count = [0]

        async def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_execute_result([t1, t2])
            elif call_count[0] == 2:
                return _make_execute_result(t1_aliases)
            else:
                return _make_execute_result(t2_aliases)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        _override_db(mock_db)
        try:
            resp = client.get(URL_PREFIX, headers=USER_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["canonical_term"] == "GoHighLevel"
            assert len(data[0]["aliases"]) == 2
            assert data[0]["aliases"][0]["alias"] == "Hatch"
        finally:
            _cleanup_db()

    def test_returns_empty_list_when_none(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result([]))

        _override_db(mock_db)
        try:
            resp = client.get(URL_PREFIX, headers=USER_HEADERS)
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            _cleanup_db()


# ── CREATE ───────────────────────────────────────────────────────────────

class TestCreateTerm:
    def test_create_term_with_aliases(self):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        created_objs = []

        def mock_add(obj):
            if isinstance(obj, CommonTerm):
                obj.id = "new-term-001"
                obj.created_at = NOW
                obj.updated_at = NOW
                obj.aliases = []
            elif isinstance(obj, CommonTermAlias):
                obj.id = f"new-alias-{len(created_objs)}"
                obj.created_at = NOW
            created_objs.append(obj)

        mock_db.add = mock_add

        async def mock_refresh(obj):
            pass

        mock_db.refresh = mock_refresh

        _override_db(mock_db)
        try:
            resp = client.post(
                URL_PREFIX,
                json={
                    "canonical_term": "GoHighLevel",
                    "context": "CRM platform",
                    "aliases": ["Hatch", "GHL"],
                },
                headers=USER_HEADERS,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["canonical_term"] == "GoHighLevel"
            assert data["context"] == "CRM platform"
        finally:
            _cleanup_db()

    def test_create_term_without_aliases(self):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        def mock_add(obj):
            obj.id = "new-term-002"
            obj.created_at = NOW
            obj.updated_at = NOW
            if isinstance(obj, CommonTerm):
                obj.aliases = []

        mock_db.add = mock_add

        async def mock_refresh(obj):
            pass

        mock_db.refresh = mock_refresh

        _override_db(mock_db)
        try:
            resp = client.post(
                URL_PREFIX,
                json={"canonical_term": "Aileen"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["canonical_term"] == "Aileen"
            assert data["aliases"] == []
        finally:
            _cleanup_db()

    def test_create_term_requires_canonical_term(self):
        mock_db = AsyncMock()
        _override_db(mock_db)
        try:
            resp = client.post(URL_PREFIX, json={}, headers=USER_HEADERS)
            assert resp.status_code == 422
        finally:
            _cleanup_db()


# ── UPDATE ───────────────────────────────────────────────────────────────

class TestUpdateTerm:
    def test_update_canonical_term(self):
        term = _make_term(id="t-upd")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result([term]))
        mock_db.flush = AsyncMock()

        async def mock_refresh(obj):
            pass

        mock_db.refresh = mock_refresh

        _override_db(mock_db)
        try:
            resp = client.patch(
                f"{URL_PREFIX}/t-upd",
                json={"canonical_term": "HighLevel CRM"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 200
            assert term.canonical_term == "HighLevel CRM"
        finally:
            _cleanup_db()

    def test_update_nonexistent_returns_404(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        _override_db(mock_db)
        try:
            resp = client.patch(
                f"{URL_PREFIX}/nonexistent",
                json={"canonical_term": "X"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 404
        finally:
            _cleanup_db()


# ── DELETE TERM ──────────────────────────────────────────────────────────

class TestDeleteTerm:
    def test_delete_existing_term(self):
        term = _make_term(id="t-del")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result([term]))
        mock_db.delete = AsyncMock()

        _override_db(mock_db)
        try:
            resp = client.delete(f"{URL_PREFIX}/t-del", headers=USER_HEADERS)
            assert resp.status_code == 204
        finally:
            _cleanup_db()

    def test_delete_nonexistent_returns_404(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        _override_db(mock_db)
        try:
            resp = client.delete(f"{URL_PREFIX}/nonexistent", headers=USER_HEADERS)
            assert resp.status_code == 404
        finally:
            _cleanup_db()


# ── ALIASES ──────────────────────────────────────────────────────────────

class TestAddAlias:
    def test_add_alias_to_term(self):
        term = _make_term(id="t-alias")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_execute_result([term]))
        mock_db.flush = AsyncMock()

        def mock_add(obj):
            obj.id = "new-alias-001"
            obj.created_at = NOW

        mock_db.add = mock_add

        async def mock_refresh(obj):
            pass

        mock_db.refresh = mock_refresh

        _override_db(mock_db)
        try:
            resp = client.post(
                f"{URL_PREFIX}/t-alias/aliases",
                json={"alias": "Hatch"},
                headers=USER_HEADERS,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["alias"] == "Hatch"
        finally:
            _cleanup_db()


class TestDeleteAlias:
    def test_delete_alias(self):
        term = _make_term(id="t-da", aliases=[("a-del", "Hatch")])
        alias_obj = term.aliases[0]

        call_count = [0]

        def make_result(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_execute_result([term])
            else:
                return _make_execute_result([alias_obj])

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=make_result)
        mock_db.delete = AsyncMock()

        _override_db(mock_db)
        try:
            resp = client.delete(
                f"{URL_PREFIX}/t-da/aliases/a-del",
                headers=USER_HEADERS,
            )
            assert resp.status_code == 204
        finally:
            _cleanup_db()


# ── SCOPING ──────────────────────────────────────────────────────────────

class TestScoping:
    def test_cannot_update_other_users_term(self):
        """Term owned by USER_ID should 404 for OTHER_USER_ID."""
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        _override_db(mock_db)
        try:
            resp = client.patch(
                f"{URL_PREFIX}/t-other",
                json={"canonical_term": "hacked"},
                headers=OTHER_HEADERS,
            )
            assert resp.status_code == 404
        finally:
            _cleanup_db()

    def test_cannot_delete_other_users_term(self):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        _override_db(mock_db)
        try:
            resp = client.delete(f"{URL_PREFIX}/t-other", headers=OTHER_HEADERS)
            assert resp.status_code == 404
        finally:
            _cleanup_db()
