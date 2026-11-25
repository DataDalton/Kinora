"""
Celery task that delivers queued library changes to Jellyfin.

queueLibraryUpdate in app.services.jellyfin collects changed paths and schedules this
task once per batch. A failed delivery retries with a growing delay. After the last
retry the failure goes to the health page and to a deduplicated notification. Nothing
here runs inside an import, so a Jellyfin outage never slows or fails one.
"""

import logging
from typing import Dict, Optional

from app.tasks.celery_app import celery_app, runAsync
from app.services import jellyfin

logger = logging.getLogger(__name__)

# Retries after the first attempt. The delay doubles from the base on each retry.
MAX_RETRIES = 4
RETRY_BASE_DELAY_SECONDS = 30


@celery_app.task(
    bind=True,
    name="app.tasks.jellyfin.flush_jellyfin_updates",
    max_retries=MAX_RETRIES,
    soft_time_limit=120,
    time_limit=180,
)
def flush_jellyfin_updates(self, updates: Optional[Dict[str, str]] = None):
    """
    Send one batch of changed paths to Jellyfin. The first run drains the queue. A retry
    carries the batch it failed to send in its arguments, so paths queued meanwhile go
    out in their own batch.
    """
    if updates is None:
        try:
            updates = jellyfin.drainPendingUpdates()
        except Exception as e:
            logger.warning(f"Could not read queued Jellyfin updates. {e}")
            return {"status": "failed", "reason": "queue unavailable"}
    if not updates:
        return {"status": "skipped", "reason": "nothing queued"}

    config = runAsync(jellyfin.loadConfig())
    if not config["enabled"]:
        return {"status": "skipped", "reason": "disabled", "paths": len(updates)}
    if not config["url"] or not config["apiKey"]:
        runAsync(jellyfin.reportFinalFailure("Jellyfin is enabled without a server URL or API key", len(updates)))
        return {"status": "failed", "reason": "not configured", "paths": len(updates)}

    try:
        mode = runAsync(jellyfin.sendLibraryUpdates(config, updates))
    except jellyfin.JellyfinRequestError as e:
        # An API key Jellyfin refuses stays refused, so it is reported without retrying.
        isAuthError = e.statusCode in (401, 403)
        if not isAuthError and self.request.retries < MAX_RETRIES:
            delay = RETRY_BASE_DELAY_SECONDS * (2**self.request.retries)
            logger.info(f"Jellyfin library update failed ({e}), retrying in {delay}s")
            raise self.retry(args=[updates], countdown=delay)
        logger.warning(f"Jellyfin library update was not delivered. {e}")
        runAsync(jellyfin.reportFinalFailure(str(e), len(updates)))
        return {"status": "failed", "reason": str(e), "paths": len(updates)}

    message = (
        f"Sent {len(updates)} changed path(s)"
        if mode == "targeted"
        else "Jellyfin refused the path list, requested a full library refresh instead"
    )
    runAsync(jellyfin.recordStatus("ok", message, len(updates)))
    logger.info(f"Jellyfin library update delivered. {message}")
    return {"status": "ok", "mode": mode, "paths": len(updates)}
