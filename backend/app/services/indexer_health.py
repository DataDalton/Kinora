"""
Indexer health.

Counts consecutive failed searches per indexer in the shared cache, so every worker sees
the same state. After a run of failures a notification says the indexer is unreachable,
at most once per window, and the next successful search clears the count. Searches keep
trying a failing indexer, since sites recover on their own.
"""

from typing import Optional

from app.core.cache import cacheGet, cacheSet

# Consecutive failures before the indexer is reported unreachable.
FAILURES_BEFORE_ALERT = 3
# Seconds the failure count and the alert dedup window last.
HEALTH_TTL_SECONDS = 6 * 3600
ALERT_WINDOW_SECONDS = 3 * 3600


def _key(name: str) -> str:
    return f"indexer:health:{name.lower()}"


async def record_success(name: str) -> None:
    """Clear an indexer's failure count after a search that reached it."""
    try:
        state = await cacheGet(_key(name))
        if state and state.get("failures"):
            await cacheSet(_key(name), {"failures": 0, "last_error": None}, expire=HEALTH_TTL_SECONDS)
    except Exception:
        pass


async def record_failure(name: str, error: str) -> None:
    """Count a failed search and notify once the indexer has failed several times in a row."""
    try:
        state = await cacheGet(_key(name)) or {}
        failures = int(state.get("failures") or 0) + 1
        await cacheSet(_key(name), {"failures": failures, "last_error": error[:300]}, expire=HEALTH_TTL_SECONDS)
        if failures == FAILURES_BEFORE_ALERT:
            from app.services.notifications import create_notification

            await create_notification(
                type=f"indexer_unreachable_{name.lower()}",
                title=f"{name} is unreachable",
                message=(
                    f"The last {failures} searches on {name} failed ({error[:160]}). "
                    "Searches keep trying it, and items are not pushed back while it is down."
                ),
                severity="warning",
                data={"indexer": name},
                dedup_window_seconds=ALERT_WINDOW_SECONDS,
            )
    except Exception:
        pass


async def get_failure_count(name: str) -> Optional[int]:
    try:
        state = await cacheGet(_key(name))
        return int(state.get("failures") or 0) if state else 0
    except Exception:
        return None


async def get_state(name: str) -> dict:
    """The failure count and last error of an indexer, with zero failures when nothing is recorded."""
    try:
        state = await cacheGet(_key(name)) or {}
    except Exception:
        state = {}
    return {"failures": int(state.get("failures") or 0), "last_error": state.get("last_error")}
