"""
Web Push endpoints. Every route acts on the signed-in user's own devices and preferences.
"""

import ipaddress
from typing import List
from urllib.parse import urlparse

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.endpoints.auth import get_current_user
from app.db import get_db
from app.schemas.push import (
    PushCategoryPreference,
    PushDevice,
    PushDeviceUpdate,
    PushPreferences,
    PushPreferencesUpdate,
    PushSubscribeRequest,
    PushTestRequest,
    PushTestResult,
    PushUnsubscribeRequest,
    VapidPublicKey,
)
from app.schemas.user import UserWithPermissions
from app.services.web_push import (
    ADMIN_PERMISSION,
    CATEGORIES_BY_KEY,
    PUSH_CATEGORIES,
    describeUserAgent,
    getVapidKeys,
    resolvePushTypes,
    sendToSubscriptions,
)

router = APIRouter()

DEVICE_COLUMNS = "id, label, endpoint, enabled, created_at, last_used_at"


def _toDevice(row: asyncpg.Record) -> PushDevice:
    return PushDevice(
        id=row["id"],
        label=row["label"],
        endpoint=row["endpoint"],
        enabled=row["enabled"],
        createdAt=row["created_at"],
        lastUsedAt=row["last_used_at"],
    )


def _validateEndpoint(endpoint: str) -> None:
    """
    The worker POSTs to this URL, so only public HTTPS hosts are accepted. Browser push
    services always hand out HTTPS endpoints on public hostnames.
    """
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Push endpoint must be an HTTPS URL")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Push endpoint must be a public host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Push endpoint must be a public host")


def _visibleCategories(user: UserWithPermissions):
    """Admin-only categories are hidden from users who would never receive them."""
    isAdmin = ADMIN_PERMISSION in user.permissions
    return [category for category in PUSH_CATEGORIES if isAdmin or not category.adminOnly]


def _preferencesResponse(user: UserWithPermissions, storedPreferences) -> PushPreferences:
    enabledByKey = resolvePushTypes(storedPreferences)
    return PushPreferences(
        categories=[
            PushCategoryPreference(
                key=category.key,
                label=category.label,
                description=category.description,
                enabled=enabledByKey[category.key],
            )
            for category in _visibleCategories(user)
        ]
    )


@router.get("/vapid-public-key", response_model=VapidPublicKey)
async def get_vapid_public_key(
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Public VAPID key the browser passes as applicationServerKey when subscribing."""
    _, publicKey = await getVapidKeys(conn)
    return VapidPublicKey(publicKey=publicKey)


@router.post("/subscriptions", response_model=PushDevice)
async def subscribe(
    body: PushSubscribeRequest,
    request: Request,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Store or refresh this browser's subscription. Sending the same endpoint again updates
    the keys and keeps the device's name and on/off state. An endpoint last registered by
    another account moves to this one and starts enabled.
    """
    _validateEndpoint(body.endpoint)
    userAgent = request.headers.get("user-agent")
    label = body.label or describeUserAgent(userAgent)
    row = await conn.fetchrow(
        f"""
        INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, label, user_agent)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (endpoint) DO UPDATE SET
            p256dh = EXCLUDED.p256dh,
            auth = EXCLUDED.auth,
            user_agent = EXCLUDED.user_agent,
            label = CASE
                WHEN $7::boolean OR push_subscriptions.user_id <> EXCLUDED.user_id THEN EXCLUDED.label
                ELSE push_subscriptions.label
            END,
            enabled = CASE
                WHEN push_subscriptions.user_id <> EXCLUDED.user_id THEN TRUE
                ELSE push_subscriptions.enabled
            END,
            user_id = EXCLUDED.user_id
        RETURNING {DEVICE_COLUMNS}
        """,
        current_user.id,
        body.endpoint,
        body.keys.p256dh,
        body.keys.auth,
        label,
        userAgent,
        body.label is not None,
    )
    return _toDevice(row)


@router.post("/subscriptions/unsubscribe")
async def unsubscribe(
    body: PushUnsubscribeRequest,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Remove the subscription for an endpoint the browser has just unsubscribed."""
    await conn.execute(
        "DELETE FROM push_subscriptions WHERE endpoint = $1 AND user_id = $2",
        body.endpoint,
        current_user.id,
    )
    return {"success": True}


@router.get("/subscriptions", response_model=List[PushDevice])
async def list_my_devices(
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        f"SELECT {DEVICE_COLUMNS} FROM push_subscriptions WHERE user_id = $1 ORDER BY created_at",
        current_user.id,
    )
    return [_toDevice(row) for row in rows]


@router.patch("/subscriptions/{device_id}", response_model=PushDevice)
async def update_device(
    device_id: int,
    body: PushDeviceUpdate,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        f"""
        UPDATE push_subscriptions
        SET enabled = COALESCE($3, enabled), label = COALESCE($4, label)
        WHERE id = $1 AND user_id = $2
        RETURNING {DEVICE_COLUMNS}
        """,
        device_id,
        current_user.id,
        body.enabled,
        body.label,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return _toDevice(row)


@router.delete("/subscriptions/{device_id}")
async def remove_device(
    device_id: int,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    result = await conn.execute(
        "DELETE FROM push_subscriptions WHERE id = $1 AND user_id = $2",
        device_id,
        current_user.id,
    )
    if result.endswith(" 0"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return {"success": True}


@router.post("/test", response_model=PushTestResult)
async def send_test_push(
    body: PushTestRequest,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Send a test notification and wait for the push services to answer, so the result
    reflects actual delivery. A device chosen by id is tested even while disabled.
    """
    if body.deviceId is not None:
        subscriptions = await conn.fetch(
            "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE id = $1 AND user_id = $2",
            body.deviceId,
            current_user.id,
        )
        if not subscriptions:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    else:
        subscriptions = await conn.fetch(
            "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = $1 AND enabled = TRUE",
            current_user.id,
        )
        if not subscriptions:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No devices have push enabled")

    payload = {
        "title": "Kinora test notification",
        "body": "Push notifications are working on this device.",
        "url": "/profile?section=notifications",
        "tag": "push_test",
        "severity": "info",
    }
    result = await sendToSubscriptions(conn, subscriptions, payload)
    return PushTestResult(**result)


@router.get("/preferences", response_model=PushPreferences)
async def get_push_preferences(
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Push categories this user can receive, each with its on/off state."""
    stored = await conn.fetchval("SELECT preferences FROM users WHERE id = $1", current_user.id)
    return _preferencesResponse(current_user, stored)


@router.put("/preferences", response_model=PushPreferences)
async def update_push_preferences(
    body: PushPreferencesUpdate,
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Merge the sent category switches into users.preferences under pushTypes."""
    unknown = [key for key in body.types if key not in CATEGORIES_BY_KEY]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown push categories {', '.join(sorted(unknown))}")
    stored = await conn.fetchval(
        """
        UPDATE users
        SET preferences = jsonb_set(
                preferences,
                '{pushTypes}',
                COALESCE(preferences->'pushTypes', '{}'::jsonb) || $2::jsonb
            ),
            updated_at = NOW()
        WHERE id = $1
        RETURNING preferences
        """,
        current_user.id,
        body.types,
    )
    return _preferencesResponse(current_user, stored)
