from celery import Celery
import asyncio

from app.core.config import settings

# Queue carrying media encodes, consumed by a dedicated worker so long encodes cannot
# occupy the pool that the periodic monitors and the scheduler run on.
TRANSCODE_QUEUE = "transcode"

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
        "app.tasks.dispatcher",
        "app.tasks.rss_monitor",
        "app.tasks.wanted_search",
        "app.tasks.upgrade_search",
        "app.tasks.manual_search",
        "app.tasks.download_monitor",
        "app.tasks.subtitle_search",
        "app.tasks.metadata_refresh",
        "app.tasks.metadata_prefetch",
        "app.tasks.transcoding",
        "app.tasks.music_monitor",
        "app.tasks.validation_monitor",
        "app.tasks.folder_health",
        "app.tasks.seeding_monitor",
        "app.tasks.yts_sync",
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
    # One reserved task per child. The worker pool autoscales, and the autoscaler grows
    # the pool from how saturated it looks, so messages held in reserve against a busy
    # child would understate the backlog. At one, a child takes work only when it is free.
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Encoding runs for minutes to hours while every other task on the default queue is a
    # monitor that has to keep its cadence, so the encode gets a queue and a worker of its
    # own. Only the encode is routed. Rule evaluation is short and stays on the default
    # queue, where it is not stuck behind an encode that is already running.
    task_routes={
        "app.tasks.transcoding.transcode_media_task": {"queue": TRANSCODE_QUEUE},
    },
    # Time limits belong here rather than in task_routes. Route entries are sent as message
    # options, where time_limit collides with the publisher's own parameter of that name.
    task_annotations={
        "app.tasks.transcoding.transcode_media_task": {
            "time_limit": 12 * 60 * 60,  # 12 hours for transcoding tasks
            "soft_time_limit": 11 * 60 * 60,  # 11 hours soft limit
        }
    },
)


# Celery Beat schedule. Every long-interval task (searches, RSS, prefetch, catalog
# sync, daily refresh) is driven by the dispatcher, which re-reads app_settings on
# every tick and fires anything whose window was missed while the stack was down.
# Only the short-cycle monitors stay as plain beat entries, their next regular run
# doubles as the catch-up.
celery_app.conf.beat_schedule = {
    "interval-dispatcher": {
        "task": "app.tasks.dispatcher.dispatch_interval_tasks",
        "schedule": 60.0,  # Every 60 seconds, fires whichever scheduled tasks are due
    },
    "download-monitor-every-minute": {
        "task": "app.tasks.download_monitor.check_downloads",
        "schedule": 60.0,  # Every 60 seconds
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
    "seeding-rules-monitor": {
        "task": "app.tasks.seeding_monitor.evaluate_seeding_rules",
        "schedule": 60.0,  # Every 60 seconds - smart seeding and reliability rules
    },
}


@celery_app.task
def test_task():
    """
    Test task to verify Celery is working
    """
    return "Celery is working!"
