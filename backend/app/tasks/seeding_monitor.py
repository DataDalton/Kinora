"""
Seeding rules monitor.

Runs the smart seeding and reliability rules engine on a fixed interval.
"""

import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.services.seeding_rules import run_seeding_rules
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.seeding_monitor.evaluate_seeding_rules")
def evaluate_seeding_rules():
    """Evaluate smart seeding and reliability rules for all torrents."""
    return runAsync(_run())


async def _run():
    taskName = "seeding_monitor"
    startTime = time.time()
    status = "success"
    try:
        result = await run_seeding_rules()
        if result.get("status") == "error":
            status = "failed"
        return result
    except Exception as e:
        status = "failed"
        print(f"Seeding rules error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )
