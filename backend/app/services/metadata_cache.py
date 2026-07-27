"""
Persistent second tier for the metadata caches.

Read order for a metadata request is Dragonfly, then this Postgres table, then the
provider network call. Rows carry a per-row TTL so freshness can be tiered by how
likely the record is to change, and expired rows are still kept as a stale
fallback when the provider is unreachable.

All operations are best effort and never raise: the network path must keep
working even if this table is unavailable.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from app.db import get_pool

# Retention for stale rows. Rows older than this are removed opportunistically on
# write, they have been refetched or unused for far too long to trust.
STALE_RETENTION_DAYS = 90

# Tiered detail TTLs by content age.
TTL_OLD_CONTENT = 7 * 86400  # released over 2 years ago, effectively immutable
TTL_SETTLED_CONTENT = 86400  # released 90 days to 2 years ago


async def getFresh(cache_key: str) -> Optional[Any]:
    """Payload for a key whose row is within its own TTL, else None."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT payload FROM metadata_cache
                WHERE cache_key = $1
                  AND fetched_at > NOW() - (ttl_seconds * INTERVAL '1 second')
                """,
                cache_key,
            )
        if row is None:
            return None
        return _decode(row["payload"])
    except Exception:
        return None


async def getStale(cache_key: str) -> Optional[Any]:
    """Payload for a key regardless of TTL, used when the provider is down."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT payload FROM metadata_cache WHERE cache_key = $1", cache_key)
        if row is None:
            return None
        return _decode(row["payload"])
    except Exception:
        return None


async def setCached(cache_key: str, provider: str, payload: Any, ttl_seconds: int) -> None:
    """Upsert a payload with its TTL. Best effort."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO metadata_cache (cache_key, provider, payload, ttl_seconds, fetched_at)
                VALUES ($1, $2, $3::jsonb, $4, NOW())
                ON CONFLICT (cache_key) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    ttl_seconds = EXCLUDED.ttl_seconds,
                    fetched_at = NOW()
                """,
                cache_key,
                provider,
                json.dumps(payload),
                ttl_seconds,
            )
    except Exception as e:
        print(f"Metadata cache write failed for {cache_key[:80]}: {e}")


async def cleanupStale() -> int:
    """
    Remove rows that have not been refreshed within the retention window. Called
    from the scheduled prefetch task. Returns rows removed, 0 on failure.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM metadata_cache WHERE fetched_at < NOW() - INTERVAL '{STALE_RETENTION_DAYS} days'"
            )
        return int(result.split()[-1]) if result else 0
    except Exception:
        return 0


def _decode(payload: Any) -> Any:
    """asyncpg returns jsonb as str unless a codec is registered, decode either way."""
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def tieredTtl(release_date_str: Optional[str], base_ttl: int) -> int:
    """
    TTL for a detail payload based on how old the content is. Content released
    over two years ago effectively never changes, recent content keeps the
    caller's short TTL so new seasons, runtimes, and statuses stay fresh.
    """
    if not release_date_str:
        return base_ttl
    try:
        released = datetime.strptime(release_date_str[:10], "%Y-%m-%d")
    except ValueError, TypeError:
        return base_ttl

    age = datetime.utcnow() - released
    if age > timedelta(days=730):
        return max(base_ttl, TTL_OLD_CONTENT)
    if age > timedelta(days=90):
        return max(base_ttl, TTL_SETTLED_CONTENT)
    return base_ttl
