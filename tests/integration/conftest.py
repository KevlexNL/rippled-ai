"""Integration test fixtures.

Uses the real Supabase DB via the session pooler URL (DATABASE_URL in .env).
get_db is overridden to use a test-dedicated engine — avoids races with the
global engine that unit tests may have imported first.

Each test module run gets a unique test user UUID. All rows are deleted in
teardown via CASCADE FK so we don't pollute the DB.
"""
import asyncio
import os
import uuid

import pytest
from starlette.testclient import TestClient

# Load .env before anything else so os.environ has the right DATABASE_URL.
from dotenv import load_dotenv
load_dotenv(override=True)


def _make_async_url(url: str) -> str:
    return (
        url
        .replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
    )


def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Check your .env file or set the env var before running integration tests."
        )
    return url


# ---------------------------------------------------------------------------
# Module-scoped engine / session factory
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    """Async engine for the integration test module, using the session pooler URL."""
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(
        _make_async_url(_get_db_url()),
        pool_size=3,
        max_overflow=5,
        connect_args={"statement_cache_size": 0},
    )
    yield engine
    # dispose() is async; wrap it so the fixture can yield before teardown
    asyncio.run(_dispose(engine))


async def _dispose(engine):
    await engine.dispose()


@pytest.fixture(scope="module")
def client(test_engine):
    """TestClient with get_db overridden to use the test engine (real DB, correct URL)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.deps import get_db
    from app.main import app

    AsyncTestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with AsyncTestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Test user isolation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_user_id() -> str:
    """Unique UUID per module run — keeps tests isolated from real data."""
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def test_user_headers(test_user_id: str) -> dict:
    return {"X-User-ID": test_user_id}


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_user(test_user_id: str):
    """Delete the test user (and all cascaded rows) after the module finishes."""
    yield
    asyncio.run(_delete_test_user(test_user_id))


async def _delete_test_user(user_id: str) -> None:
    """Hard-delete the test user; FK CASCADE removes sources, source_items, etc."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text, bindparam
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    engine = create_async_engine(
        _make_async_url(_get_db_url()),
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.begin() as conn:
            # Delete non-cascading FK references first
            for table in ("lifecycle_transitions", "commitment_signals", "commitment_ambiguities", "commitment_contexts"):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :id").bindparams(
                        bindparam("id", type_=PGUUID(as_uuid=False))
                    ),
                    {"id": user_id},
                )
            await conn.execute(
                text("DELETE FROM users WHERE id = :id").bindparams(
                    bindparam("id", type_=PGUUID(as_uuid=False))
                ),
                {"id": user_id},
            )
    finally:
        await engine.dispose()
