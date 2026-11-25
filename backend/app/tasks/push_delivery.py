"""
Celery task that sends a stored notification over Web Push, so push services are
contacted from the worker instead of the code path that raised the notification.
"""

import logging
from typing import Any, Dict

from app.tasks.celery_app import celery_app, runAsync

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.push_delivery.deliver_push_notification",
    ignore_result=True,
    time_limit=120,
    soft_time_limit=90,
)
def deliverPushNotification(notification: Dict[str, Any]) -> None:
    from app.services.web_push import deliverNotification

    result = runAsync(deliverNotification(notification))
    if result["sent"] or result["failed"] or result["removed"]:
        logger.info(
            f"Web Push for notification {notification.get('id')} sent to {result['sent']} device(s), "
            f"{result['failed']} failed, {result['removed']} expired subscription(s) removed"
        )
