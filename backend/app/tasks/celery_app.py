from celery import Celery
from celery.schedules import crontab
import asyncio
import asyncpg

from app.core.config import settings

# Persistent event loop for Celery tasks - avoids creating/destroying loops
_celeryLoop: asyncio.AbstractEventLoop | None = None


def runAsync(coro):
    """Run async code in Celery tasks using a persistent event loop."""
    global _celeryLoop
    if _celeryLoop is None or _celeryLoop.is_closed():
        _celeryLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(_celeryLoop)
    return _celeryLoop.run_until_complete(coro)


# Initialize Celery app
celery_app = Celery(
    "kinora",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.rss_monitor",
        "app.tasks.wanted_search",
        "app.tasks.download_monitor",
        "app.tasks.subtitle_search",
        "app.tasks.metadata_refresh",
        "app.tasks.transcoding",
        "app.tasks.music_monitor",
        "app.tasks.validation_monitor",
        "app.tasks.folder_health",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes default
    task_soft_time_limit=25 * 60,  # 25 minutes default
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_routes={
        "app.tasks.transcoding.*": {
            "time_limit": 12 * 60 * 60,  # 12 hours for transcoding tasks
            "soft_time_limit": 11 * 60 * 60,  # 11 hours soft limit
        }
    },
)


def get_schedule_intervals():
    """
    Get schedule intervals from database settings
    Returns default values if database is not accessible
    """
    try:

        async def fetch_settings():
            conn = await asyncpg.connect(settings.DATABASE_URL)
            try:
                rss_interval = await conn.fetchval("SELECT value FROM app_settings WHERE key = 'rss_sync_interval'")
                auto_search_interval = await conn.fetchval(
                    "SELECT value FROM app_settings WHERE key = 'auto_search_interval'"
                )
                return (
                    int(rss_interval) if rss_interval else 15,
                    int(auto_search_interval) if auto_search_interval else 60,
                )
            finally:
                await conn.close()

        rss_interval, auto_search_interval = asyncio.run(fetch_settings())
    except Exception:
        rss_interval = 15
        auto_search_interval = 60

    return rss_interval, auto_search_interval


# Get intervals from database
rss_interval, auto_search_interval = get_schedule_intervals()

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "rss-monitor": {
        "task": "app.tasks.rss_monitor.monitor_rss_feeds",
        "schedule": crontab(minute=f"*/{rss_interval}"),
    },
    "wanted-search": {
        "task": "app.tasks.wanted_search.search_wanted_media",
        "schedule": crontab(minute=f"*/{auto_search_interval}"),
    },
    "download-monitor-every-minute": {
        "task": "app.tasks.download_monitor.check_downloads",
        "schedule": 60.0,  # Every 60 seconds
    },
    "metadata-refresh-daily": {
        "task": "app.tasks.metadata_refresh.refresh_all_metadata",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
    "music-wanted-search": {
        "task": "app.tasks.music_monitor.search_wanted_music",
        "schedule": crontab(minute=f"*/{auto_search_interval}"),  # Same interval as other wanted searches
    },
    "music-new-releases": {
        "task": "app.tasks.music_monitor.check_new_releases",
        "schedule": crontab(hour="*/6"),  # Every 6 hours check for new releases
    },
    "validation-monitor": {
        "task": "app.tasks.validation_monitor.check_validating_torrents",
        "schedule": 300.0,  # Every 5 minutes - fallback for edge cases (server restarts)
    },
    "folder-health-check": {
        "task": "app.tasks.folder_health.check_folder_health",
        "schedule": 300.0,  # Every 5 minutes - check folder accessibility
    },
    "folder-disk-space-update": {
        "task": "app.tasks.folder_health.update_disk_space",
        "schedule": 60.0,  # Every 60 seconds - update cached disk space
    },
}


@celery_app.task
def test_task():
    """
    Test task to verify Celery is working
    """
    return "Celery is working!"
