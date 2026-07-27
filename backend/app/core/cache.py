from typing import Optional, Any
import json
import redis.asyncio as redis
from app.core.config import settings

# Cache TTL constants (in seconds)
CACHE_TTL_SHORT = 3600  # 1 hour - for detail pages with potentially changing data (new seasons, episodes)
CACHE_TTL_LONG = 21600  # 6 hours - for trending, popular, discover, search results, charts

# Dragonfly client (uses redis library for wire protocol compatibility)
cacheClient: Optional[redis.Redis] = None


async def getCacheClient() -> Optional[redis.Redis]:
    """
    Get Dragonfly client instance
    Returns None if connection fails
    """
    global cacheClient

    if cacheClient is None:
        try:
            cacheClient = await redis.from_url(
                settings.DRAGONFLY_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception:
            return None

    return cacheClient


async def closeCacheClient():
    """
    Close Dragonfly connection
    """
    global cacheClient

    if cacheClient:
        await cacheClient.close()
        cacheClient = None


async def cacheGet(key: str) -> Optional[Any]:
    """
    Get value from cache
    Returns None if Dragonfly is unavailable
    """
    try:
        client = await getCacheClient()
        if not client:
            return None

        value = await client.get(key)

        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        return None
    except Exception:
        return None


async def cacheSet(key: str, value: Any, expire: int = 3600) -> bool:
    """
    Set value in cache with expiration time in seconds
    Returns False if Dragonfly is unavailable
    """
    try:
        client = await getCacheClient()
        if not client:
            return False

        if not isinstance(value, str):
            value = json.dumps(value)

        return await client.set(key, value, ex=expire)
    except Exception:
        return False


async def cacheDelete(key: str) -> bool:
    """
    Delete key from cache
    Returns False if Dragonfly is unavailable
    """
    try:
        client = await getCacheClient()
        if not client:
            return False
        return await client.delete(key) > 0
    except Exception:
        return False


async def cacheIncr(key: str) -> Optional[int]:
    """
    Atomically increment an integer key and return the new value
    Returns None if Dragonfly is unavailable
    """
    try:
        client = await getCacheClient()
        if not client:
            return None
        return await client.incr(key)
    except Exception:
        return None


async def cacheExists(key: str) -> bool:
    """
    Check if key exists in cache
    Returns False if Dragonfly is unavailable
    """
    try:
        client = await getCacheClient()
        if not client:
            return False
        return await client.exists(key) > 0
    except Exception:
        return False
