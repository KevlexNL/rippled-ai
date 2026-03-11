"""Synchronous SQLAlchemy session factory for Celery workers.

FastAPI routes use the async engine (app/db/engine.py + app/db/deps.py).
Celery workers run in a synchronous context and must not use AsyncSession.
This module provides a separate sync engine + sessionmaker for that purpose.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _make_sync_url(url: str) -> str:
    """Convert asyncpg URLs back to sync psycopg2 URLs."""
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


settings = get_settings()

_sync_engine = create_engine(
    _make_sync_url(settings.database_url),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

_SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=_sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Context manager yielding a synchronous SQLAlchemy Session.

    Usage in Celery tasks:
        with get_sync_session() as db:
            db.add(some_object)
            db.commit()
    """
    session: Session = _SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
