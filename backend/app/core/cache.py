from typing import Optional, Any
import json
import redis.asyncio as redis
from app.core.config import settings

# Cache TTL constants (in seconds)
CACHE_TTL_SHORT = 3600  # 1 hour - for detail pages with potentially changing data (new seasons, episodes)
CACHE_TTL_LONG = 21600  # 6 hours - for trending, popular, discover, search results, charts

# Redis client
redis_client: Optional[redis.Redis] = None


async def get_redis() -> Optional[redis.Redis]:
    """
    Get Redis client instance
    Returns None if Redis connection fails
    """
    global redis_client

    if redis_client is None:
        try:
            redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception:
            return None

    return redis_client


async def close_redis():
    """
    Close Redis connection
    """
    global redis_client

    if redis_client:
        await redis_client.close()
        redis_client = None


async def cache_get(key: str) -> Optional[Any]:
    """
    Get value from cache
    Returns None if Redis is unavailable
    """
    try:
        client = await get_redis()
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


async def cache_set(key: str, value: Any, expire: int = 3600) -> bool:
    """
    Set value in cache with expiration time in seconds
    Returns False if Redis is unavailable
    """
    try:
        client = await get_redis()
        if not client:
            return False

        if not isinstance(value, str):
            value = json.dumps(value)

        return await client.set(key, value, ex=expire)
    except Exception:
        return False


async def cache_delete(key: str) -> bool:
    """
    Delete key from cache
    Returns False if Redis is unavailable
    """
    try:
        client = await get_redis()
        if not client:
            return False
        return await client.delete(key) > 0
    except Exception:
        return False


async def cache_exists(key: str) -> bool:
    """
    Check if key exists in cache
    Returns False if Redis is unavailable
    """
    try:
        client = await get_redis()
        if not client:
            return False
        return await client.exists(key) > 0
    except Exception:
        return False
