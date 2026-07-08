"""
In-app notification service.

Persists notifications to Postgres and pushes them to connected clients over the
WebSocket. Producers: auto-recovery, VPN kill-switch, validation failures, and
port-forward drift.
"""

import json
import logging
from typing import Optional, Dict, Any

from app.db import get_pool

logger = logging.getLogger(__name__)

# Severity levels: info | success | warning | error
SEVERITY_INFO = "info"
SEVERITY_SUCCESS = "success"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    created = data.get("created_at")
    if created is not None and hasattr(created, "isoformat"):
        data["created_at"] = created.isoformat()
    return data


async def create_notification(
    type: str,
    title: str,
    message: Optional[str] = None,
    severity: str = SEVERITY_INFO,
    data: Optional[Dict[str, Any]] = None,
    dedup_window_seconds: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a notification (persist + push). When dedup_window_seconds is set, a
    notification of the same type created within that window is skipped so a
    recurring condition does not spam the list.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if dedup_window_seconds:
                existing = await conn.fetchval(
                    """
                    SELECT 1 FROM notifications
                    WHERE type = $1 AND created_at > NOW() - ($2 * INTERVAL '1 second')
                    LIMIT 1
                    """,
                    type,
                    dedup_window_seconds,
                )
                if existing:
                    return None

            row = await conn.fetchrow(
                """
                INSERT INTO notifications (type, severity, title, message, data)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                RETURNING *
                """,
                type,
                severity,
                title,
                message,
                # The pool registers a jsonb codec, so the dict is passed directly.
                # json.dumps here would double-encode it into a JSON string scalar.
                data,
            )
    except Exception as e:
        logger.warning(f"Failed to create notification '{title}': {e}")
        return None

    notification = _serialize(dict(row))

    try:
        from app.core.webtransport import webtransport_manager

        for user_id in webtransport_manager.get_active_users():
            await webtransport_manager.send_notification(user_id, notification)
    except Exception as e:
        logger.debug(f"Failed to push notification: {e}")

    return notification
