"""
Database connection pool management with PgBouncer support.

Connections go through PgBouncer (port 6432) in transaction pooling mode
for maximum performance. Migrations run directly against PostgreSQL.
"""

from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
import asyncpg
import orjson
import os

_pool: Optional[asyncpg.Pool] = None


def getDsn() -> str:
    """Build DSN pointing to PgBouncer (port 6432), not PostgreSQL directly.

    Reads through settings so the password resolves from the secrets file when present
    (Docker) and PgBouncer host/port reflect the environment auto-detection.
    """
    from app.core.config import settings

    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.PGBOUNCER_HOST}:{settings.PGBOUNCER_PORT}/{settings.POSTGRES_DB}"
    )


def getDirectDsn() -> str:
    """Build DSN for direct PostgreSQL connection (for migrations).

    Reads through settings, which computes DATABASE_URL from the secrets-file password.
    """
    from app.core.config import settings

    return settings.DATABASE_URL


async def initPool() -> asyncpg.Pool:
    """Initialize connection pool to PgBouncer.

    Pool settings are minimal since PgBouncer handles connection management.
    PgBouncer in transaction mode returns connections after each transaction,
    so we use statementCacheSize=0 to avoid prepared statement issues.
    """
    global _pool
    dsn = getDsn()

    _pool = await asyncpg.create_pool(
        dsn,
        min_size=5,
        max_size=20,
        command_timeout=60,
        # Disable prepared statements - required for transaction pooling mode
        statement_cache_size=0,
        # Disable SSL - PgBouncer handles connections without SSL locally
        ssl=False,
        setup=_setupConnection,
    )
    return _pool


async def _setupConnection(conn: asyncpg.Connection) -> None:
    """Configure JSON codecs using orjson for each connection."""
    await conn.set_type_codec(
        "jsonb", encoder=lambda v: orjson.dumps(v).decode("utf-8"), decoder=orjson.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=lambda v: orjson.dumps(v).decode("utf-8"), decoder=orjson.loads, schema="pg_catalog"
    )


async def getPool() -> asyncpg.Pool:
    """Return the connection pool, raising if not initialized."""
    global _pool
    if _pool is None:
        _pool = await initPool()
    return _pool


@asynccontextmanager
async def getConnection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquire a connection from the pool."""
    pool = await getPool()
    async with pool.acquire() as conn:
        yield conn


async def getDb() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency for database connections."""
    async with getConnection() as conn:
        yield conn


async def closePool() -> None:
    """Close the connection pool on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# Aliases for backwards compatibility with existing code
get_pool = getPool
get_db = getDb
init_pool = initPool
close_pool = closePool
