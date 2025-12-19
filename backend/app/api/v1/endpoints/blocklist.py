from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import asyncpg

from app.core.database import get_db
from app.schemas.blocklist import BlocklistEntry, BlocklistCreate, BulkBlocklistCreate, BlocklistCheck, BlocklistCheckResult
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/", response_model=List[BlocklistEntry])
async def get_blocklist(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    media_type: Optional[str] = None,
    media_id: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all blocklisted releases with optional filters
    """
    query = "SELECT * FROM blocklist WHERE 1=1"
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

    if search:
        query += f" AND release_title ILIKE ${param_count}"
        params.append(f"%{search}%")
        param_count += 1

    query += f" ORDER BY blocked_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, skip])

    rows = await conn.fetch(query, *params)
    return [BlocklistEntry(**dict(row)) for row in rows]


@router.get("/count", response_model=dict)
async def get_blocklist_count(
    media_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get count of blocklisted releases
    """
    if media_type:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM blocklist WHERE media_type = $1",
            media_type,
        )
    else:
        result = await conn.fetchval("SELECT COUNT(*) FROM blocklist")

    return {"count": result}


@router.get("/media/{media_type}/{media_id}", response_model=List[BlocklistEntry])
async def get_media_blocklist(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all blocklisted releases for a specific media item
    """
    valid_types = ["movie", "show", "anime", "album"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    rows = await conn.fetch(
        """
        SELECT * FROM blocklist
        WHERE media_type = $1 AND media_id = $2
        ORDER BY blocked_at DESC
        """,
        media_type,
        media_id,
    )
    return [BlocklistEntry(**dict(row)) for row in rows]


@router.get("/{blocklist_id}", response_model=BlocklistEntry)
async def get_blocklist_entry(
    blocklist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific blocklist entry
    """
    row = await conn.fetchrow("SELECT * FROM blocklist WHERE id = $1", blocklist_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocklist entry not found",
        )

    return BlocklistEntry(**dict(row))


@router.post("/", response_model=BlocklistEntry, status_code=status.HTTP_201_CREATED)
async def add_to_blocklist(
    blocklist_data: BlocklistCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add a release to the blocklist
    """
    valid_types = ["movie", "show", "anime", "album"]
    if blocklist_data.media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    existing = await conn.fetchrow(
        """
        SELECT id FROM blocklist
        WHERE media_type = $1 AND media_id = $2 AND release_title = $3
        """,
        blocklist_data.media_type,
        blocklist_data.media_id,
        blocklist_data.release_title,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Release is already blocklisted for this media item",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO blocklist (media_type, media_id, release_title, reason)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        blocklist_data.media_type,
        blocklist_data.media_id,
        blocklist_data.release_title,
        blocklist_data.reason,
    )

    return BlocklistEntry(**dict(row))


@router.post("/bulk", response_model=dict)
async def bulk_add_to_blocklist(
    bulk_data: BulkBlocklistCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add multiple releases to the blocklist
    """
    valid_types = ["movie", "show", "anime", "album"]
    added_count = 0

    async with conn.transaction():
        for entry in bulk_data.entries:
            if entry.media_type not in valid_types:
                continue

            existing = await conn.fetchrow(
                """
                SELECT id FROM blocklist
                WHERE media_type = $1 AND media_id = $2 AND release_title = $3
                """,
                entry.media_type,
                entry.media_id,
                entry.release_title,
            )

            if not existing:
                await conn.execute(
                    """
                    INSERT INTO blocklist (media_type, media_id, release_title, reason)
                    VALUES ($1, $2, $3, $4)
                    """,
                    entry.media_type,
                    entry.media_id,
                    entry.release_title,
                    entry.reason,
                )
                added_count += 1

    return {"success": True, "added": added_count, "total": len(bulk_data.entries)}


@router.post("/check", response_model=BlocklistCheckResult)
async def check_blocklist(
    check_data: BlocklistCheck,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Check if a release is blocklisted
    """
    row = await conn.fetchrow(
        """
        SELECT * FROM blocklist
        WHERE media_type = $1 AND media_id = $2 AND release_title = $3
        """,
        check_data.media_type,
        check_data.media_id,
        check_data.release_title,
    )

    if row:
        return BlocklistCheckResult(
            is_blocked=True,
            entry=BlocklistEntry(**dict(row)),
        )

    return BlocklistCheckResult(is_blocked=False, entry=None)


@router.delete("/{blocklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_blocklist(
    blocklist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Remove a release from the blocklist
    """
    existing = await conn.fetchrow("SELECT id FROM blocklist WHERE id = $1", blocklist_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocklist entry not found",
        )

    await conn.execute("DELETE FROM blocklist WHERE id = $1", blocklist_id)
    return None


@router.delete("/media/{media_type}/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_media_blocklist(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Clear all blocklist entries for a specific media item
    """
    valid_types = ["movie", "show", "anime", "album"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    await conn.execute(
        "DELETE FROM blocklist WHERE media_type = $1 AND media_id = $2",
        media_type,
        media_id,
    )
    return None


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_blocklist(
    media_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Clear entire blocklist or by media type
    """
    if media_type:
        await conn.execute("DELETE FROM blocklist WHERE media_type = $1", media_type)
    else:
        await conn.execute("DELETE FROM blocklist")

    return None
