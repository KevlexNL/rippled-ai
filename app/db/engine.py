from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings


def _make_async_url(url: str) -> str:
    """Convert postgres:// or postgresql:// to postgresql+asyncpg://"""
    return url.replace("postgresql://", "postgresql+asyncpg://") \
              .replace("postgres://", "postgresql+asyncpg://")


settings = get_settings()

engine = create_async_engine(
    _make_async_url(settings.database_url),
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
    # Required for PgBouncer / Supabase session pooler compatibility.
    # asyncpg's prepared statement cache conflicts with connection poolers.
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
