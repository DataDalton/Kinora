"""
Dispatcher for every long-interval scheduled task.

Celery beat crons do not catch up: a machine that is off during the slot simply
skips that run. Beat therefore only fires this dispatcher every minute, and the
dispatcher decides what is due, so any task that missed its window while the
stack was down fires within a minute of startup instead of waiting for the next
slot. It also re-reads the user-configurable intervals from app_settings on
every tick, so settings changes apply within a minute with no restart.

Two schedule kinds:
- Interval: due when the time since the last dispatch reaches the interval.
  The interval comes from an app_settings key when "setting" is present,
  otherwise from "default_minutes".
- Daily: due when the last dispatch is older than the most recent occurrence of
  the anchor hour (UTC). Runs at that hour when the stack is up, and once at
  startup when the slot was missed.

Short-cycle jobs (60s and 300s monitors) stay on plain beat entries, their next
regular run doubles as the catch-up.
"""

import calendar
import time
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.core.cache import cacheGet, cacheSet

# Dispatch key -> schedule spec. Keys match the task:last_run names each task
# writes, which the system status panel relies on.
SCHEDULED_TASKS = {
    "rss_monitor": {
        "task": "app.tasks.rss_monitor.monitor_rss_feeds",
        "setting": "rss_sync_interval",
        "default_minutes": 15,
    },
    "wanted_search": {
        "task": "app.tasks.wanted_search.search_wanted_media",
        "setting": "auto_search_interval",
        "default_minutes": 60,
    },
    "music_wanted_search": {
        "task": "app.tasks.music_monitor.search_wanted_music",
        "setting": "auto_search_interval",
        "default_minutes": 60,
    },
    "upgrade_search": {
        "task": "app.tasks.upgrade_search.search_upgrades",
        "setting": "upgrade_search_interval",
        "default_minutes": 360,
    },
    "metadata_prefetch": {
        "task": "app.tasks.metadata_prefetch.prefetch_warm_sets",
        "default_minutes": 360,
    },
    "music_new_releases": {
        "task": "app.tasks.music_monitor.check_new_releases",
        "default_minutes": 360,
    },
    "yts_sync": {
        "task": "app.tasks.yts_sync.sync_yts_catalog",
        "default_minutes": 360,
    },
    "metadata_refresh": {
        "task": "app.tasks.metadata_refresh.refresh_all_metadata",
        "daily_at_hour": 3,
    },
}

# In-process fallback for last-dispatch times, used when Dragonfly is unavailable
# so tasks are not fired every minute during a cache outage.
_localLastDispatch: dict = {}


@celery_app.task(name="app.tasks.dispatcher.dispatch_interval_tasks")
def dispatch_interval_tasks():
    """Fire every scheduled task that is due, including missed-window catch-ups."""
    return runAsync(async_dispatch_interval_tasks())


async def _load_intervals() -> dict:
    """
    Current interval minutes per interval-kind dispatch key. Settings-backed keys
    read app_settings with their default as fallback, fixed keys use their
    default. Daily-anchored tasks are not included.
    """
    settingKeys = list({spec["setting"] for spec in SCHEDULED_TASKS.values() if "setting" in spec})
    values = {}
    if settingKeys:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT key, value FROM app_settings WHERE key = ANY($1)", settingKeys)
                values = {row["key"]: row["value"] for row in rows}
        except Exception as e:
            print(f"Dispatcher could not read intervals, using defaults: {e}")

    intervals = {}
    for dispatchKey, spec in SCHEDULED_TASKS.items():
        if "default_minutes" not in spec:
            continue
        raw = values.get(spec.get("setting", ""))
        try:
            minutes = int(raw) if raw else spec["default_minutes"]
        except TypeError, ValueError:
            minutes = spec["default_minutes"]
        intervals[dispatchKey] = max(1, minutes)
    return intervals


def _mostRecentDailyBoundary(hour: int, now: datetime) -> float:
    """Epoch seconds of the most recent occurrence of hour:00 UTC at or before now."""
    boundary = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if boundary > now:
        boundary -= timedelta(days=1)
    return calendar.timegm(boundary.timetuple())


async def async_dispatch_interval_tasks():
    intervals = await _load_intervals()
    nowTs = time.time()
    nowDt = datetime.utcnow()
    fired = []

    for dispatchKey, spec in SCHEDULED_TASKS.items():
        cacheKey = f"dispatch:last:{dispatchKey}"
        last = await cacheGet(cacheKey)
        if not isinstance(last, (int, float)):
            last = _localLastDispatch.get(dispatchKey)

        if "daily_at_hour" in spec:
            boundary = _mostRecentDailyBoundary(spec["daily_at_hour"], nowDt)
            due = last is None or float(last) < boundary
            markerExpire = 48 * 3600
        else:
            intervalSeconds = intervals[dispatchKey] * 60
            due = last is None or (nowTs - float(last)) >= intervalSeconds
            markerExpire = max(intervalSeconds * 2, 3600)

        if not due:
            continue

        celery_app.send_task(spec["task"])
        fired.append(dispatchKey)
        _localLastDispatch[dispatchKey] = nowTs
        # Kept beyond the interval so a missed dispatcher run never loses the marker.
        await cacheSet(cacheKey, nowTs, expire=markerExpire)

    return {"fired": fired, "intervals_minutes": intervals}
