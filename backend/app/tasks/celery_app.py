from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "nexarr",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.rss_monitor",
        "app.tasks.wanted_search",
        "app.tasks.download_monitor",
        "app.tasks.subtitle_search",
        "app.tasks.metadata_refresh",
        "app.tasks.transcoding",
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

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "rss-monitor-every-15-minutes": {
        "task": "app.tasks.rss_monitor.monitor_rss_feeds",
        "schedule": crontab(minute=f"*/{settings.RSS_SYNC_INTERVAL}"),
    },
    "wanted-search-every-hour": {
        "task": "app.tasks.wanted_search.search_wanted_media",
        "schedule": crontab(minute=0),  # Every hour
    },
    "download-monitor-every-minute": {
        "task": "app.tasks.download_monitor.check_downloads",
        "schedule": 60.0,  # Every 60 seconds
    },
    "metadata-refresh-daily": {
        "task": "app.tasks.metadata_refresh.refresh_all_metadata",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
}


@celery_app.task
def test_task():
    """
    Test task to verify Celery is working
    """
    return "Celery is working!"
