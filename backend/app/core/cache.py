from typing import Optional, Any
import json
import redis.asyncio as redis
from app.core.config import settings

# Redis client
redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Get Redis client instance
    """
    global redis_client

    if redis_client is None:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

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
    """
    client = await get_redis()
    value = await client.get(key)

    if value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    return None


async def cache_set(key: str, value: Any, expire: int = 3600) -> bool:
    """
    Set value in cache with expiration time in seconds
    """
    client = await get_redis()

    if not isinstance(value, str):
        value = json.dumps(value)

    return await client.set(key, value, ex=expire)


async def cache_delete(key: str) -> bool:
    """
    Delete key from cache
    """
    client = await get_redis()
    return await client.delete(key) > 0


async def cache_exists(key: str) -> bool:
    """
    Check if key exists in cache
    """
    client = await get_redis()
    return await client.exists(key) > 0
