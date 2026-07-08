"""
In-app notification endpoints.
"""

from typing import Optional
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List notifications, newest first."""
    where = "WHERE read = FALSE" if unread_only else ""
    rows = await conn.fetch(
        f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT COUNT(*) FROM notifications")
    unread = await conn.fetchval("SELECT COUNT(*) FROM notifications WHERE read = FALSE")
    return {
        "notifications": [dict(r) for r in rows],
        "total": total,
        "unread": unread,
    }


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    count = await conn.fetchval("SELECT COUNT(*) FROM notifications WHERE read = FALSE")
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute("UPDATE notifications SET read = TRUE WHERE id = $1", notification_id)
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute("UPDATE notifications SET read = TRUE WHERE read = FALSE")
    return {"success": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute("DELETE FROM notifications WHERE id = $1", notification_id)
    return {"success": True}


@router.delete("")
async def clear_notifications(
    read_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Clear notifications, by default only already-read ones."""
    if read_only:
        await conn.execute("DELETE FROM notifications WHERE read = TRUE")
    else:
        await conn.execute("DELETE FROM notifications")
    return {"success": True}
