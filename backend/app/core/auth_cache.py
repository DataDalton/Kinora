"""
Short-lived cache for resolved authentication identities.

get_current_user runs on every authenticated request and resolves the user row,
group memberships, and effective permissions from the database. This module caches
that resolved identity in Dragonfly so the hot path costs one cache read instead of
three queries per request.

Invalidation is version based. Every stored identity embeds the auth version it
was written under, and any mutation that can change a user's identity or
permissions bumps the version, which invalidates every stored identity at once.
The version itself is checked from a small in-process cache refreshed every few
seconds, so a request normally performs a single Dragonfly read (the identity),
not two. The process that performs a bump sees it instantly; other worker
processes converge within the refresh window. The TTL is only a safety net for
changes that bypass the API (for example direct database edits).
"""

import time
from typing import Optional, Dict, Any

from app.core.cache import getCacheClient, cacheGet, cacheSet, cacheIncr

# Safety-net TTL. Real invalidation happens through bumpAuthVersion.
AUTH_CACHE_TTL = 900

AUTH_VERSION_KEY = "auth:version"

# How long a process trusts its locally cached auth version. Bounds the window
# in which another worker process can still serve a pre-bump identity.
VERSION_REFRESH_SECONDS = 5.0

_versionCache = {"value": 0, "fetchedAt": 0.0}


async def _getAuthVersion() -> int:
    """
    Current auth cache version, served from the in-process cache and refreshed
    from Dragonfly at most every VERSION_REFRESH_SECONDS. 0 when unavailable.
    """
    now = time.monotonic()
    if now - _versionCache["fetchedAt"] < VERSION_REFRESH_SECONDS:
        return _versionCache["value"]

    try:
        client = await getCacheClient()
        value = 0
        if client:
            raw = await client.get(AUTH_VERSION_KEY)
            value = int(raw) if raw else 0
        _versionCache["value"] = value
        _versionCache["fetchedAt"] = now
        return value
    except Exception:
        # Keep the last known version rather than treating a cache blip as a bump.
        _versionCache["fetchedAt"] = now
        return _versionCache["value"]


async def bumpAuthVersion() -> None:
    """
    Invalidate every cached auth identity by advancing the version they must
    match. The bumping process updates its local version immediately, so its own
    subsequent requests never serve the stale identity.
    """
    newValue = await cacheIncr(AUTH_VERSION_KEY)
    if newValue is not None:
        _versionCache["value"] = newValue
        _versionCache["fetchedAt"] = time.monotonic()


async def getCachedAuthUser(username: str) -> Optional[Dict[str, Any]]:
    """
    Return the cached identity payload for a username, or None on miss or when
    the stored entry predates the current auth version.
    """
    cached = await cacheGet(f"auth:user:{username}")
    if not isinstance(cached, dict):
        return None
    if cached.get("_ver") != await _getAuthVersion():
        return None
    payload = cached.get("user")
    return payload if isinstance(payload, dict) else None


async def setCachedAuthUser(username: str, payload: Dict[str, Any]) -> None:
    """Store a resolved identity payload for a username under the current version."""
    version = await _getAuthVersion()
    await cacheSet(
        f"auth:user:{username}",
        {"_ver": version, "user": payload},
        expire=AUTH_CACHE_TTL,
    )
