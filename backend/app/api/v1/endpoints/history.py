from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
import asyncpg

from app.db import get_db
from app.schemas.history import DownloadHistory, DownloadHistoryCreate, DownloadHistoryUpdate, DownloadHistoryStats
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/", response_model=List[DownloadHistory])
async def get_download_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    media_type: Optional[str] = None,
    media_id: Optional[int] = None,
    status: Optional[str] = None,
    indexer: Optional[str] = None,
    was_upgrade: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get download history with optional filters
    """
    query = "SELECT * FROM download_history WHERE 1=1"
    params = []
    param_count = 1

    if media_type:
        query += f" AND media_type = ${param_count}"
        params.append(media_type)
        param_count += 1

    if media_id is not None:
        query += f" AND media_id = ${param_count}"
        params.append(media_id)
        param_count += 1

    if status:
        query += f" AND status = ${param_count}"
        params.append(status)
        param_count += 1

    if indexer:
        query += f" AND indexer = ${param_count}"
        params.append(indexer)
        param_count += 1

    if was_upgrade is not None:
        query += f" AND was_upgrade = ${param_count}"
        params.append(was_upgrade)
        param_count += 1

    if date_from:
        query += f" AND started_at >= ${param_count}"
        params.append(date_from)
        param_count += 1

    if date_to:
        query += f" AND started_at <= ${param_count}"
        params.append(date_to)
        param_count += 1

    query += f" ORDER BY started_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, skip])

    rows = await conn.fetch(query, *params)
    return [DownloadHistory(**dict(row)) for row in rows]


@router.get("/stats", response_model=DownloadHistoryStats)
async def get_download_stats(
    media_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get download history statistics
    """
    where_clause = ""
    params = []

    if media_type:
        where_clause = " WHERE media_type = $1"
        params = [media_type]

    stats = await conn.fetchrow(
        f"""
        SELECT
            COUNT(*) as total_downloads,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COUNT(*) FILTER (WHERE status IN ('pending', 'downloading')) as in_progress,
            COALESCE(SUM(size), 0) as total_size_bytes,
            COUNT(*) FILTER (WHERE was_upgrade = true) as upgrades
        FROM download_history{where_clause}
        """,
        *params,
    )

    return DownloadHistoryStats(
        total_downloads=stats["total_downloads"],
        completed=stats["completed"],
        failed=stats["failed"],
        in_progress=stats["in_progress"],
        total_size_bytes=stats["total_size_bytes"],
        upgrades=stats["upgrades"],
    )


@router.get("/media/{media_type}/{media_id}", response_model=List[DownloadHistory])
async def get_media_history(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get download history for a specific media item
    """
    valid_types = ["movie", "show", "anime", "album"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    rows = await conn.fetch(
        """
        SELECT * FROM download_history
        WHERE media_type = $1 AND media_id = $2
        ORDER BY started_at DESC
        """,
        media_type,
        media_id,
    )
    return [DownloadHistory(**dict(row)) for row in rows]


@router.get("/{history_id}", response_model=DownloadHistory)
async def get_history_entry(
    history_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific download history entry
    """
    row = await conn.fetchrow("SELECT * FROM download_history WHERE id = $1", history_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )

    return DownloadHistory(**dict(row))


@router.post("/", response_model=DownloadHistory, status_code=status.HTTP_201_CREATED)
async def create_history_entry(
    history_data: DownloadHistoryCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Create a new download history entry
    """
    row = await conn.fetchrow(
        """
        INSERT INTO download_history (
            media_type, media_id, episode_id, torrent_hash, torrent_title,
            indexer, indexer_page_url, torrent_url, magnet_link, info_hash,
            quality, source, size, seeders, download_client, save_path,
            status, progress, was_upgrade
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, 'pending', 0.0, false)
        RETURNING *
        """,
        history_data.media_type,
        history_data.media_id,
        history_data.episode_id,
        history_data.torrent_hash,
        history_data.torrent_title,
        history_data.indexer,
        history_data.indexer_page_url,
        history_data.torrent_url,
        history_data.magnet_link,
        history_data.info_hash,
        history_data.quality,
        history_data.source,
        history_data.size,
        history_data.seeders,
        history_data.download_client,
        history_data.save_path,
    )

    return DownloadHistory(**dict(row))


@router.put("/{history_id}", response_model=DownloadHistory)
async def update_history_entry(
    history_id: int,
    update_data: DownloadHistoryUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update a download history entry
    """
    existing = await conn.fetchrow("SELECT * FROM download_history WHERE id = $1", history_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )

    update_fields = []
    values = []
    param_count = 1

    if update_data.status is not None:
        update_fields.append(f"status = ${param_count}")
        values.append(update_data.status)
        param_count += 1

    if update_data.progress is not None:
        update_fields.append(f"progress = ${param_count}")
        values.append(update_data.progress)
        param_count += 1

    if update_data.error_message is not None:
        update_fields.append(f"error_message = ${param_count}")
        values.append(update_data.error_message)
        param_count += 1

    if update_data.completed_at is not None:
        update_fields.append(f"completed_at = ${param_count}")
        values.append(update_data.completed_at)
        param_count += 1

    if update_data.was_upgrade is not None:
        update_fields.append(f"was_upgrade = ${param_count}")
        values.append(update_data.was_upgrade)
        param_count += 1

    if not update_fields:
        return DownloadHistory(**dict(existing))

    update_fields.append("updated_at = NOW()")
    values.append(history_id)

    query = f"""
        UPDATE download_history SET {", ".join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return DownloadHistory(**dict(row))


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    history_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a download history entry
    """
    existing = await conn.fetchrow("SELECT id FROM download_history WHERE id = $1", history_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )

    await conn.execute("DELETE FROM download_history WHERE id = $1", history_id)
    return None


@router.delete("/media/{media_type}/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_media_history(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Clear all download history for a specific media item
    """
    valid_types = ["movie", "show", "anime", "album"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    await conn.execute(
        "DELETE FROM download_history WHERE media_type = $1 AND media_id = $2",
        media_type,
        media_id,
    )
    return None


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_history(
    media_type: Optional[str] = None,
    older_than_days: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Clear download history with optional filters
    """
    query = "DELETE FROM download_history WHERE 1=1"
    params = []
    param_count = 1

    if media_type:
        query += f" AND media_type = ${param_count}"
        params.append(media_type)
        param_count += 1

    if older_than_days:
        query += f" AND started_at < NOW() - INTERVAL '${param_count} days'"
        params.append(older_than_days)
        param_count += 1

    await conn.execute(query, *params)
    return None


@router.get("/indexers", response_model=List[str])
async def get_used_indexers(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get list of indexers that have been used in download history
    """
    rows = await conn.fetch(
        "SELECT DISTINCT indexer FROM download_history ORDER BY indexer ASC"
    )
    return [row["indexer"] for row in rows]
