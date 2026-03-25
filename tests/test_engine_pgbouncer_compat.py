"""Tests that the async engine is configured for PgBouncer compatibility.

Supabase routes connections through PgBouncer in transaction-pool mode.
asyncpg's prepared statement cache and SQLAlchemy's dialect-level
prepared_statement_cache_size must BOTH be set to 0, otherwise the
app gets InvalidSQLStatementNameError on every query.
"""

from app.db.engine import engine


def _get_connect_params() -> dict:
    """Extract the actual connect params baked into the pool creator closure."""
    creator = engine.sync_engine.pool._creator
    for name, cell in zip(creator.__code__.co_freevars, creator.__closure__):
        if name == "cparams":
            return dict(cell.cell_contents)
    raise RuntimeError("Could not find cparams in pool creator closure")


def test_asyncpg_statement_cache_disabled():
    """asyncpg statement_cache_size must be 0 for PgBouncer compat."""
    params = _get_connect_params()
    assert params.get("statement_cache_size") == 0, (
        "statement_cache_size must be 0 for PgBouncer transaction-pool mode"
    )


def test_prepared_statement_cache_disabled():
    """prepared_statement_cache_size must be 0 for PgBouncer compat.

    Without this, asyncpg creates named prepared statements
    (__asyncpg_stmt_N__) that PgBouncer cannot route correctly when
    it reassigns server connections between transactions.
    """
    params = _get_connect_params()
    assert params.get("prepared_statement_cache_size") == 0, (
        "prepared_statement_cache_size must be 0 for PgBouncer transaction-pool mode"
    )


def test_pool_pre_ping_enabled():
    """pool_pre_ping should be True to detect stale PgBouncer connections."""
    assert engine.pool._pre_ping is True, (
        "pool_pre_ping must be True to handle PgBouncer connection recycling"
    )
