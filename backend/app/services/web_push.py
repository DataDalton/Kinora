"""
Web Push delivery over VAPID.

Holds the instance VAPID key pair, maps notification types to the push categories users
choose from, decides which users receive each notification, and sends the encrypted
payload to every enabled subscription those users own. Subscriptions the push service
reports as gone are deleted.
"""

import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiohttp
import asyncpg
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush_async

from app.core.config import settings
from app.db import get_pool

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY_SETTING = "vapid_private_key"
VAPID_SUBJECT_SETTING = "vapid_subject"
# Push services require a contact in the JWT. A mailto on localhost is rejected by
# Apple, so the default is the project URL. The vapid_subject setting overrides it.
DEFAULT_VAPID_SUBJECT = "https://github.com/DataDalton/Kinora"

# How long the push service keeps an undelivered message for an offline device.
PUSH_TTL_SECONDS = 24 * 3600
PUSH_TIMEOUT_SECONDS = 15
# Upper bound on concurrent requests to push services for one notification.
MAX_PARALLEL_SENDS = 8
# Push services answer these for a subscription that no longer exists.
GONE_STATUS_CODES = {404, 410}
ADMIN_PERMISSION = "system.admin"


@dataclass(frozen=True)
class PushCategory:
    key: str
    label: str
    description: str
    # Admin-only categories go to administrators. Others also reach the users tied to
    # the item, such as the person who requested a movie.
    adminOnly: bool
    defaultEnabled: bool
    exactTypes: Tuple[str, ...] = ()
    typePrefixes: Tuple[str, ...] = ()

    def matches(self, notificationType: str) -> bool:
        return notificationType in self.exactTypes or any(
            notificationType.startswith(prefix) for prefix in self.typePrefixes
        )


PUSH_CATEGORIES: Tuple[PushCategory, ...] = (
    PushCategory(
        key="downloads",
        label="Downloads started",
        description="A release was sent to the download client. Requesters get this for items they asked for.",
        adminOnly=False,
        defaultEnabled=True,
        exactTypes=("new_download",),
    ),
    PushCategory(
        key="vpn",
        label="VPN and port alerts",
        description="The VPN kill switch engaged or released, or the forwarded port changed.",
        adminOnly=True,
        defaultEnabled=True,
        exactTypes=("vpn_killswitch", "vpn_restored", "port_drift"),
    ),
    PushCategory(
        key="recovery",
        label="Automatic recovery",
        description="A stalled or failed download was recovered automatically.",
        adminOnly=True,
        defaultEnabled=True,
        exactTypes=("auto_recovery",),
    ),
    PushCategory(
        key="validation",
        label="Validation failures",
        description="A torrent failed validation and was removed.",
        adminOnly=True,
        defaultEnabled=True,
        exactTypes=("validation_failed",),
    ),
    PushCategory(
        key="indexers",
        label="Indexer outages",
        description="An indexer stopped responding.",
        adminOnly=True,
        defaultEnabled=True,
        typePrefixes=("indexer_unreachable_",),
    ),
    PushCategory(
        key="templates",
        label="Blocked by safety template",
        description="A search found releases, but the profile's safety template allowed none of them.",
        adminOnly=True,
        defaultEnabled=False,
        typePrefixes=("template_blocked_",),
    ),
    PushCategory(
        key="system",
        label="Other system alerts",
        description="Any other alert Kinora raises.",
        adminOnly=True,
        defaultEnabled=True,
    ),
)

FALLBACK_CATEGORY = PUSH_CATEGORIES[-1]
CATEGORIES_BY_KEY = {category.key: category for category in PUSH_CATEGORIES}

# Detail pages for the media types notifications carry in their data.
MEDIA_PATHS = {
    "movie": "/movies/{id}",
    "show": "/shows/{id}",
    "anime": "/anime/{id}",
    "album": "/music/album/{id}",
}

_vapidCache: Optional[Tuple[Vapid01, str]] = None


def categoryForType(notificationType: str) -> PushCategory:
    for category in PUSH_CATEGORIES:
        if category.matches(notificationType):
            return category
    return FALLBACK_CATEGORY


def resolvePushTypes(storedPreferences: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Per-category push switches for a user, with defaults for categories never set."""
    stored = (storedPreferences or {}).get("pushTypes") or {}
    return {category.key: bool(stored.get(category.key, category.defaultEnabled)) for category in PUSH_CATEGORIES}


def _fernet() -> Fernet:
    # Same derivation as the settings endpoints, so the stored value reads back there too.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def _publicKeyFor(vapid: Vapid01) -> str:
    raw = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def getVapidKeys(conn: asyncpg.Connection) -> Tuple[Vapid01, str]:
    """
    Return the VAPID signer and its public key in the base64url form browsers expect.
    The key pair is created on first use. ON CONFLICT keeps the first writer's key when
    two processes generate one at the same moment, and both then read that row back.
    """
    global _vapidCache
    if _vapidCache is not None:
        return _vapidCache

    row = await conn.fetchrow("SELECT value, is_encrypted FROM app_settings WHERE key = $1", VAPID_PRIVATE_KEY_SETTING)
    if row is None or not row["value"]:
        generated = Vapid01()
        generated.generate_keys()
        encrypted = _fernet().encrypt(generated.private_pem()).decode()
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, 'string', TRUE, 'notifications', $3)
            ON CONFLICT (key) DO NOTHING
            """,
            VAPID_PRIVATE_KEY_SETTING,
            encrypted,
            "VAPID private key that signs Web Push requests. Replacing it invalidates every push subscription.",
        )
        row = await conn.fetchrow(
            "SELECT value, is_encrypted FROM app_settings WHERE key = $1",
            VAPID_PRIVATE_KEY_SETTING,
        )
        logger.info("Generated the VAPID key pair for Web Push")

    pem = row["value"]
    if row["is_encrypted"]:
        pem = _fernet().decrypt(pem.encode()).decode()
    vapid = Vapid01.from_pem(pem.encode())
    _vapidCache = (vapid, _publicKeyFor(vapid))
    return _vapidCache


async def getVapidSubject(conn: asyncpg.Connection) -> str:
    subject = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", VAPID_SUBJECT_SETTING)
    return subject or DEFAULT_VAPID_SUBJECT


def buildPayload(notification: Dict[str, Any]) -> Dict[str, Any]:
    """The JSON the service worker reads to show the notification and route a click."""
    data = notification.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {}

    notificationType = notification.get("type") or "notification"
    url = "/notifications"
    # The tag makes a newer notification replace an older one with the same tag, so it
    # includes the media item and two different downloads never collapse into one.
    tag = notificationType
    pathTemplate = MEDIA_PATHS.get(data.get("media_type") or "")
    if pathTemplate and data.get("media_id") is not None:
        url = pathTemplate.format(id=data["media_id"])
        tag = f"{notificationType}:{data['media_type']}:{data['media_id']}"

    return {
        "title": notification.get("title") or "Kinora",
        "body": notification.get("message") or "",
        "url": url,
        "tag": tag,
        "severity": notification.get("severity"),
        "notificationId": notification.get("id"),
    }


async def _requesterIds(conn: asyncpg.Connection, data: Dict[str, Any]) -> List[int]:
    """Users whose approved request created the media item a notification is about."""
    mediaType = data.get("media_type")
    mediaId = data.get("media_id")
    if not mediaType or mediaId is None:
        return []
    # Music requests are stored as either album or music.
    requestTypes = ["album", "music"] if mediaType == "album" else [mediaType]
    rows = await conn.fetch(
        """
        SELECT DISTINCT user_id FROM media_requests
        WHERE media_type = ANY($1::text[]) AND created_media_id = $2 AND status = 'approved'
        """,
        requestTypes,
        int(mediaId),
    )
    return [row["user_id"] for row in rows]


async def resolveRecipients(
    conn: asyncpg.Connection, notification: Dict[str, Any], category: PushCategory
) -> List[int]:
    """
    Administrators receive every category. For categories tied to a media item, the
    users who requested that item receive it as well.
    """
    adminRows = await conn.fetch(
        """
        SELECT DISTINCT u.id FROM users u
        JOIN user_groups ug ON ug.user_id = u.id
        JOIN permission_group_permissions pgp ON pgp.group_id = ug.group_id
        WHERE u.is_active = TRUE AND pgp.permission_name = $1
        """,
        ADMIN_PERMISSION,
    )
    recipients = {row["id"] for row in adminRows}

    if not category.adminOnly:
        data = notification.get("data") or {}
        if isinstance(data, dict):
            recipients.update(await _requesterIds(conn, data))

    return sorted(recipients)


async def sendToSubscriptions(
    conn: asyncpg.Connection, subscriptions: Iterable[asyncpg.Record], payload: Dict[str, Any]
) -> Dict[str, int]:
    """
    Send one payload to each subscription in parallel. Subscriptions answered with 404 or
    410 are deleted, and successful ones get last_used_at stamped.
    """
    subscriptionList = list(subscriptions)
    if not subscriptionList:
        return {"sent": 0, "failed": 0, "removed": 0}

    vapid, _ = await getVapidKeys(conn)
    subject = await getVapidSubject(conn)
    body = json.dumps(payload)
    limiter = asyncio.Semaphore(MAX_PARALLEL_SENDS)
    sentIds: List[int] = []
    goneIds: List[int] = []
    failedCount = 0

    async def sendOne(session: aiohttp.ClientSession, subscription: asyncpg.Record) -> None:
        nonlocal failedCount
        subscriptionInfo = {
            "endpoint": subscription["endpoint"],
            "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
        }
        async with limiter:
            try:
                # pywebpush fills aud and exp into the claims dict, so each send gets its own.
                await webpush_async(
                    subscription_info=subscriptionInfo,
                    data=body,
                    vapid_private_key=vapid,
                    vapid_claims={"sub": subject},
                    ttl=PUSH_TTL_SECONDS,
                    timeout=PUSH_TIMEOUT_SECONDS,
                    headers={"Urgency": "high" if payload.get("severity") == "error" else "normal"},
                    aiohttp_session=session,
                )
                sentIds.append(subscription["id"])
            except WebPushException as e:
                if e.status_code in GONE_STATUS_CODES:
                    goneIds.append(subscription["id"])
                else:
                    failedCount += 1
                    logger.warning(
                        f"Web Push to subscription {subscription['id']} failed with status {e.status_code}. {e.message}"
                    )
            except Exception as e:
                failedCount += 1
                logger.warning(f"Web Push to subscription {subscription['id']} failed. {e}")

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*(sendOne(session, sub) for sub in subscriptionList))

    if goneIds:
        await conn.execute("DELETE FROM push_subscriptions WHERE id = ANY($1::int[])", goneIds)
        logger.info(f"Removed {len(goneIds)} expired Web Push subscription(s)")
    if sentIds:
        await conn.execute("UPDATE push_subscriptions SET last_used_at = NOW() WHERE id = ANY($1::int[])", sentIds)

    return {"sent": len(sentIds), "failed": failedCount, "removed": len(goneIds)}


async def deliverNotification(notification: Dict[str, Any]) -> Dict[str, int]:
    """
    Push one stored notification to every recipient whose preferences allow its category,
    on each of their enabled devices.
    """
    category = categoryForType(notification.get("type") or "")
    pool = await get_pool()
    async with pool.acquire() as conn:
        recipients = await resolveRecipients(conn, notification, category)
        if not recipients:
            return {"sent": 0, "failed": 0, "removed": 0}

        preferenceRows = await conn.fetch("SELECT id, preferences FROM users WHERE id = ANY($1::int[])", recipients)
        allowedUsers = [
            row["id"] for row in preferenceRows if resolvePushTypes(row["preferences"]).get(category.key, False)
        ]
        if not allowedUsers:
            return {"sent": 0, "failed": 0, "removed": 0}

        subscriptions = await conn.fetch(
            """
            SELECT id, endpoint, p256dh, auth FROM push_subscriptions
            WHERE user_id = ANY($1::int[]) AND enabled = TRUE
            """,
            allowedUsers,
        )
        return await sendToSubscriptions(conn, subscriptions, buildPayload(notification))


async def hasEnabledSubscriptions(conn: asyncpg.Connection) -> bool:
    return bool(await conn.fetchval("SELECT EXISTS (SELECT 1 FROM push_subscriptions WHERE enabled = TRUE)"))


def describeUserAgent(userAgent: Optional[str]) -> str:
    """Short device label such as "Chrome on Android" from a User-Agent header."""
    if not userAgent:
        return "Unknown device"
    ua = userAgent

    if "Edg/" in ua:
        browser = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Firefox/" in ua or "FxiOS" in ua:
        browser = "Firefox"
    elif "SamsungBrowser" in ua:
        browser = "Samsung Internet"
    elif "Chrome/" in ua or "CriOS" in ua:
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        browser = "Browser"

    if "iPhone" in ua:
        system = "iPhone"
    elif "iPad" in ua:
        system = "iPad"
    elif "Android" in ua:
        system = "Android"
    elif "Windows" in ua:
        system = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        system = "macOS"
    elif "CrOS" in ua:
        system = "ChromeOS"
    elif "Linux" in ua:
        system = "Linux"
    else:
        return browser

    return f"{browser} on {system}"
