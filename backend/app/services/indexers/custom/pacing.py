"""
Request pacing for user-defined indexers.

Private trackers ban accounts that send too many requests, so every request to a
user-defined indexer first reserves a time slot. Slots are spaced by the larger of the
indexer's minimum interval and sixty seconds divided by its requests per minute, so both
limits hold at once. Slots are reserved in the shared cache, so the API and every Celery
worker draw from one schedule per indexer. When the cache is unreachable the schedule is
kept per process instead.

A 429 answer or a Retry-After header pushes the indexer's next slot back, so the request
after it waits as long as the tracker asked.
"""

import asyncio
import time
from typing import Dict, Optional

from app.core.cache import getCacheClient

# Longest a request waits for its slot before failing, so a long backlog fails fast
# instead of holding a search open.
MAX_WAIT_SECONDS = 45.0

_RESERVE_SCRIPT = """
local now = tonumber(ARGV[1])
local spacing = tonumber(ARGV[2])
local nextAt = tonumber(redis.call('GET', KEYS[1]) or '0')
local slot = now
if nextAt > now then slot = nextAt end
local ttl = math.ceil((slot + spacing - now) * 1000) + 60000
redis.call('SET', KEYS[1], tostring(slot + spacing), 'PX', ttl)
return tostring(slot - now)
"""

_PUSH_SCRIPT = """
local target = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local nextAt = tonumber(redis.call('GET', KEYS[1]) or '0')
if target > nextAt then
  redis.call('SET', KEYS[1], tostring(target), 'PX', math.ceil((target - now) * 1000) + 60000)
end
return 1
"""

_localNext: Dict[int, float] = {}
_localLocks: Dict[int, asyncio.Lock] = {}


class RateLimitWait(Exception):
    """The indexer's next free slot is further away than MAX_WAIT_SECONDS."""


def spacingSeconds(minIntervalSeconds: Optional[float], requestsPerMinute: Optional[int]) -> float:
    spacing = max(0.0, float(minIntervalSeconds or 0))
    if requestsPerMinute and requestsPerMinute > 0:
        spacing = max(spacing, 60.0 / requestsPerMinute)
    return spacing


def _key(indexerId: int) -> str:
    return f"indexer:custom:pace:{indexerId}"


async def _reserveShared(indexerId: int, spacing: float) -> Optional[float]:
    client = await getCacheClient()
    if client is None:
        return None
    try:
        wait = await client.eval(_RESERVE_SCRIPT, 1, _key(indexerId), repr(time.time()), repr(spacing))
        return float(wait)
    except Exception:
        return None


async def _reserveLocal(indexerId: int, spacing: float) -> float:
    lock = _localLocks.setdefault(indexerId, asyncio.Lock())
    async with lock:
        now = time.time()
        slot = max(now, _localNext.get(indexerId, 0.0))
        _localNext[indexerId] = slot + spacing
        return slot - now


async def waitForSlot(indexerId: int, name: str, spacing: float) -> None:
    """Wait until this request's slot. Raises RateLimitWait when the wait would be too long."""
    if spacing <= 0:
        return
    wait = await _reserveShared(indexerId, spacing)
    if wait is None:
        wait = await _reserveLocal(indexerId, spacing)
    if wait > MAX_WAIT_SECONDS:
        raise RateLimitWait(f"{name} is rate limited for another {int(wait)} seconds, so the request was not sent")
    if wait > 0:
        await asyncio.sleep(wait)


async def pushBack(indexerId: int, seconds: float) -> None:
    """Keep every request to the indexer waiting for at least the given number of seconds."""
    target = time.time() + max(0.0, seconds)
    _localNext[indexerId] = max(_localNext.get(indexerId, 0.0), target)
    client = await getCacheClient()
    if client is None:
        return
    try:
        await client.eval(_PUSH_SCRIPT, 1, _key(indexerId), repr(target), repr(time.time()))
    except Exception:
        pass
