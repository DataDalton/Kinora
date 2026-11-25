"""
Jellyfin library update notifications.

After Kinora writes, renames, or deletes files in the library it tells Jellyfin which
folders changed, so Jellyfin rescans only those folders instead of waiting for its
scheduled scan. Kinora never signs in to Jellyfin and its own login does not depend on
it. The only credential is an API key the administrator creates in Jellyfin.

Changed paths are collected in Dragonfly by queueLibraryUpdate, which callers use from
both sync and async code. The first path in a quiet period schedules one Celery flush a
short delay later, so a season pack or an album produces a single request. The flush
maps Kinora paths to Jellyfin paths, sends POST /Library/Media/Updated, and falls back
to a full POST /Library/Refresh only when Jellyfin rejects the targeted call.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# app_settings keys. The api key row is stored encrypted.
SETTING_ENABLED = "jellyfin_enabled"
SETTING_URL = "jellyfin_url"
SETTING_API_KEY = "jellyfin_api_key"
SETTING_PATH_MAPPINGS = "jellyfin_path_mappings"
SETTINGS_CATEGORY = "jellyfin"

UPDATE_CREATED = "Created"
UPDATE_MODIFIED = "Modified"
UPDATE_DELETED = "Deleted"
_UPDATE_TYPES = {UPDATE_CREATED, UPDATE_MODIFIED, UPDATE_DELETED}

# Dragonfly keys. The pending hash maps a Kinora path to its update type. The scheduled
# key exists while a flush task is waiting to run, so later paths join that flush.
PENDING_KEY = "jellyfin:pending_updates"
FLUSH_SCHEDULED_KEY = "jellyfin:flush_scheduled"
STATUS_KEY = "jellyfin:last_update_status"

# Seconds between the first queued path and the flush that sends the batch.
BATCH_DELAY_SECONDS = 15

# Request timeout for every Jellyfin call, in seconds.
REQUEST_TIMEOUT_SECONDS = 15

# Notification type for a batch that failed every retry. Notifications of this type are
# deduplicated over this window in seconds.
FAILURE_NOTIFICATION_TYPE = "jellyfin_update_failed"
FAILURE_NOTIFICATION_DEDUP_SECONDS = 6 * 60 * 60

_syncRedis: Optional[redis.Redis] = None


def _getSyncRedis() -> redis.Redis:
    """Sync Dragonfly client for queueing, usable from sync helpers and async handlers alike."""
    global _syncRedis
    if _syncRedis is None:
        _syncRedis = redis.Redis.from_url(
            settings.DRAGONFLY_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _syncRedis


def _notifyFolder(path: str, updateType: str) -> str:
    """
    The path reported to Jellyfin. A created or modified file is reported by its folder,
    so every file landing in one folder collapses to one entry. A deleted path is
    reported as itself, and Jellyfin walks up to the nearest folder it still knows.
    """
    path = os.path.normpath(path)
    if updateType == UPDATE_DELETED:
        return path
    if os.path.isdir(path):
        return path
    return os.path.dirname(path)


def queueLibraryUpdate(paths: Iterable[Optional[str]], updateType: str = UPDATE_CREATED) -> None:
    """
    Record library paths that changed and schedule a batched notification to Jellyfin.
    Never raises, so a Dragonfly or broker problem cannot fail the import that called it.
    Paths are queued even while the integration is disabled. The flush checks the setting
    and discards them, which keeps this call free of database reads.
    """
    if updateType not in _UPDATE_TYPES:
        updateType = UPDATE_MODIFIED
    try:
        folders = {_notifyFolder(p, updateType) for p in paths if p}
        if not folders:
            return
        client = _getSyncRedis()
        client.hset(PENDING_KEY, mapping={folder: updateType for folder in folders})
        # The scheduled marker outlives the batch delay so a slow worker start does not
        # schedule a second flush. The flush deletes it before draining.
        if client.set(FLUSH_SCHEDULED_KEY, "1", nx=True, ex=BATCH_DELAY_SECONDS * 4):
            from app.tasks.celery_app import celery_app

            celery_app.send_task(
                "app.tasks.jellyfin.flush_jellyfin_updates",
                countdown=BATCH_DELAY_SECONDS,
            )
    except Exception as e:
        logger.warning(f"Could not queue Jellyfin library update. {e}")


def drainPendingUpdates() -> Dict[str, str]:
    """Take every queued path and clear the queue in one transaction."""
    client = _getSyncRedis()
    client.delete(FLUSH_SCHEDULED_KEY)
    pipe = client.pipeline(transaction=True)
    pipe.hgetall(PENDING_KEY)
    pipe.delete(PENDING_KEY)
    pending, _ = pipe.execute()
    return pending or {}


def parsePathMappings(raw: Any) -> List[Dict[str, str]]:
    """Path mappings as a list of {"kinora_path", "jellyfin_path"} prefixes, from stored JSON or a list."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    mappings = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kinoraPath = str(entry.get("kinora_path") or "").strip()
        jellyfinPath = str(entry.get("jellyfin_path") or "").strip()
        if kinoraPath and jellyfinPath:
            mappings.append({"kinora_path": kinoraPath, "jellyfin_path": jellyfinPath})
    return mappings


def mapPath(path: str, mappings: List[Dict[str, str]]) -> str:
    """
    Rewrite a Kinora path into the path Jellyfin sees. The longest matching prefix wins,
    and a prefix only matches whole path components, so /data/movies does not match
    /data/movies2. A path no mapping covers is returned unchanged.
    """
    best = None
    for mapping in mappings:
        source = mapping["kinora_path"].rstrip("/\\")
        if path == source or path.startswith(source + "/") or path.startswith(source + "\\"):
            if best is None or len(source) > len(best[0]):
                best = (source, mapping["jellyfin_path"].rstrip("/\\"))
    if best is None:
        return path
    source, target = best
    remainder = path[len(source) :].lstrip("/\\")
    if not remainder:
        return target or "/"
    # Jellyfin on Windows uses backslashes. The mapped part follows the target's separator.
    separator = "\\" if "\\" in target and "/" not in target else "/"
    return target + separator + remainder.replace("\\", "/").replace("/", separator)


def authHeaders(apiKey: str) -> Dict[str, str]:
    return {
        "Authorization": f'MediaBrowser Client="Kinora", Token="{apiKey}"',
        "X-Emby-Token": apiKey,
        "Accept": "application/json",
    }


async def loadConfig(conn=None) -> Dict[str, Any]:
    """Read the Jellyfin settings rows, with the api key decrypted."""
    from app.db import get_pool

    query = "SELECT key, value FROM app_settings WHERE key = ANY($1::text[])"
    keys = [SETTING_ENABLED, SETTING_URL, SETTING_API_KEY, SETTING_PATH_MAPPINGS]
    if conn is None:
        pool = await get_pool()
        async with pool.acquire() as poolConn:
            rows = await poolConn.fetch(query, keys)
    else:
        rows = await conn.fetch(query, keys)
    values = {row["key"]: row["value"] or "" for row in rows}

    apiKey = ""
    if values.get(SETTING_API_KEY):
        from app.api.v1.endpoints.settings import decrypt_value

        decrypted = decrypt_value(values[SETTING_API_KEY])
        apiKey = "" if decrypted == "***DECRYPTION_ERROR***" else decrypted

    return {
        "enabled": str(values.get(SETTING_ENABLED, "")).lower() == "true",
        "url": (values.get(SETTING_URL) or "").strip().rstrip("/"),
        "apiKey": apiKey,
        "pathMappings": parsePathMappings(values.get(SETTING_PATH_MAPPINGS)),
    }


class JellyfinRequestError(Exception):
    """A Jellyfin call that failed. rejected is True when Jellyfin answered with an error status."""

    def __init__(self, message: str, statusCode: Optional[int] = None):
        super().__init__(message)
        self.statusCode = statusCode
        self.rejected = statusCode is not None


async def _request(method: str, url: str, apiKey: str, body: Optional[Dict[str, Any]] = None):
    from app.core.http_client import http_request

    kwargs: Dict[str, Any] = {"headers": authHeaders(apiKey), "timeout": REQUEST_TIMEOUT_SECONDS}
    if body is not None:
        kwargs["json"] = body
    try:
        response = await http_request(method, url, **kwargs)
    except Exception as e:
        raise JellyfinRequestError(f"Could not reach Jellyfin at {url}. {e}")
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise JellyfinRequestError("Jellyfin refused the API key", response.status_code)
        raise JellyfinRequestError(f"Jellyfin answered HTTP {response.status_code}", response.status_code)
    return response


async def testConnection(url: str, apiKey: str) -> Dict[str, Any]:
    """Call GET /System/Info and report the server name and version."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return {"success": False, "message": "Server URL is not set"}
    if not apiKey:
        return {"success": False, "message": "API key is not set"}
    try:
        response = await _request("GET", f"{url}/System/Info", apiKey)
        info = response.json() if response.content else {}
    except JellyfinRequestError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Unexpected response from Jellyfin. {e}"}
    serverName = info.get("ServerName")
    version = info.get("Version")
    label = " ".join(part for part in [serverName, version and f"v{version}"] if part)
    return {
        "success": True,
        "message": f"Connected to {label}" if label else "Connected to Jellyfin",
        "serverName": serverName,
        "version": version,
    }


async def sendLibraryUpdates(config: Dict[str, Any], updates: Dict[str, str]) -> str:
    """
    Tell Jellyfin which paths changed. Returns "targeted" or "full" for the call that
    succeeded. Raises JellyfinRequestError when both calls fail or Jellyfin is unreachable.
    """
    mappings = config.get("pathMappings") or []
    body = {
        "Updates": [
            {"Path": mapPath(path, mappings), "UpdateType": updateType} for path, updateType in sorted(updates.items())
        ]
    }
    baseUrl = config["url"]
    try:
        await _request("POST", f"{baseUrl}/Library/Media/Updated", config["apiKey"], body)
        return "targeted"
    except JellyfinRequestError as e:
        # A rejected key fails the full refresh too, and an unreachable server is retried
        # by the task. Only a targeted call Jellyfin answered but refused falls back.
        if not e.rejected or e.statusCode in (401, 403):
            raise
        logger.info(f"Jellyfin rejected the targeted update ({e}), requesting a full library refresh")
    await _request("POST", f"{baseUrl}/Library/Refresh", config["apiKey"])
    return "full"


async def recordStatus(state: str, message: str, pathCount: int) -> None:
    """Store the outcome of the latest batch for the health page."""
    from app.core.cache import cacheSet

    await cacheSet(
        STATUS_KEY,
        {
            "state": state,
            "message": message,
            "pathCount": pathCount,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        expire=30 * 24 * 60 * 60,
    )


async def readStatus() -> Optional[Dict[str, Any]]:
    from app.core.cache import cacheGet

    status = await cacheGet(STATUS_KEY)
    return status if isinstance(status, dict) else None


async def reportFinalFailure(message: str, pathCount: int) -> None:
    """Record a batch that failed every retry on the health page and as a deduplicated notification."""
    await recordStatus("error", message, pathCount)
    from app.services.notifications import SEVERITY_WARNING, create_notification

    await create_notification(
        type=FAILURE_NOTIFICATION_TYPE,
        title="Jellyfin did not receive library changes",
        message=f"{message}. Jellyfin picks up the new files on its next scheduled library scan.",
        severity=SEVERITY_WARNING,
        data={"pathCount": pathCount},
        dedup_window_seconds=FAILURE_NOTIFICATION_DEDUP_SECONDS,
    )


async def healthEntry(conn) -> Dict[str, Any]:
    """External API entry for the system status page."""
    config = await loadConfig(conn)
    if not config["enabled"]:
        return {"name": "Jellyfin", "status": "not_configured", "message": "Library updates disabled"}
    if not config["url"] or not config["apiKey"]:
        return {"name": "Jellyfin", "status": "error", "message": "Enabled without a server URL or API key"}
    status = await readStatus()
    if status and status.get("state") == "error":
        return {
            "name": "Jellyfin",
            "status": "error",
            "message": status.get("message") or "Last library update failed",
            "lastChecked": status.get("timestamp"),
        }
    entry = {"name": "Jellyfin", "status": "healthy", "message": "Configured"}
    if status:
        entry["message"] = "Last library update delivered"
        entry["lastChecked"] = status.get("timestamp")
    return entry
