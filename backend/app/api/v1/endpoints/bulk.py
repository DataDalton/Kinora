from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg
import os
import shutil

from app.db import get_db
from app.db.repositories import MediaTagRepository, MediaProfileRepository
from app.schemas.bulk import (
    BulkMonitorRequest,
    BulkDeleteRequest,
    BulkRenameRequest,
    BulkRefreshMetadataRequest,
    BulkRescanRequest,
    BulkTagsRequest,
    BulkMediaProfileRequest,
    BulkRenameAllRequest,
    BulkOperationResult,
)
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()

VALID_MEDIA_TYPES = ["movie", "show", "anime", "album", "artist"]
TABLE_MAP = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "artist": "artists",
}


def validateMediaType(mediaType: str) -> str:
    """Validate and return the table name for a media type."""
    if mediaType not in VALID_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )
    return TABLE_MAP[mediaType]


@router.post("/{media_type}/monitor", response_model=BulkOperationResult)
async def bulk_monitor(
    media_type: str,
    request: BulkMonitorRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk monitor/unmonitor multiple media items (single query)."""
    tableName = validateMediaType(media_type)

    # Single batch update query instead of N individual queries
    result = await conn.execute(
        f"UPDATE {tableName} SET monitored = $1, updated_at = NOW() WHERE id = ANY($2)",
        request.monitored,
        request.ids,
    )
    processed = int(result.split()[-1])
    failed = len(request.ids) - processed
    errors = [f"{failed} items not found"] if failed > 0 else []

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors,
    )


@router.post("/{media_type}/delete", response_model=BulkOperationResult)
async def bulk_delete(
    media_type: str,
    request: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk delete multiple media items with optional file deletion."""
    tableName = validateMediaType(media_type)
    errors = []

    # If deleting files, fetch paths first in a single query
    if request.delete_files:
        rows = await conn.fetch(
            f"SELECT id, file_path, root_folder_path FROM {tableName} WHERE id = ANY($1)",
            request.ids,
        )
        for row in rows:
            filePath = row.get("file_path")
            if filePath and os.path.exists(filePath):
                try:
                    if os.path.isfile(filePath):
                        os.remove(filePath)
                    elif os.path.isdir(filePath):
                        shutil.rmtree(filePath)
                except Exception as e:
                    errors.append(f"File deletion for {row['id']}: {str(e)}")

    # Single batch delete
    result = await conn.execute(
        f"DELETE FROM {tableName} WHERE id = ANY($1)",
        request.ids,
    )
    processed = int(result.split()[-1])
    failed = len(request.ids) - processed
    if failed > 0:
        errors.append(f"{failed} items not found")

    return BulkOperationResult(
        success=failed == 0 and len(errors) == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/rename", response_model=BulkOperationResult)
async def bulk_rename(
    media_type: str,
    request: BulkRenameRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk rename files for multiple media items using current naming convention."""
    tableName = validateMediaType(media_type)
    errors = []

    # Fetch all items with files in a single query
    rows = await conn.fetch(
        f"SELECT id, file_path, has_file FROM {tableName} WHERE id = ANY($1)",
        request.ids,
    )

    foundIds = {row["id"] for row in rows}
    notFound = [id for id in request.ids if id not in foundIds]
    noFile = [row["id"] for row in rows if not row.get("has_file") or not row.get("file_path")]

    processed = len(rows) - len(noFile)
    failed = len(notFound) + len(noFile)

    if notFound:
        errors.append(f"{len(notFound)} items not found")
    if noFile:
        errors.append(f"{len(noFile)} items have no files to rename")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/refresh-metadata", response_model=BulkOperationResult)
async def bulk_refresh_metadata(
    media_type: str,
    request: BulkRefreshMetadataRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk refresh metadata for multiple media items."""
    tableName = validateMediaType(media_type)

    # Single query to check which items exist
    existingCount = await conn.fetchval(
        f"SELECT COUNT(*) FROM {tableName} WHERE id = ANY($1)",
        request.ids,
    )
    processed = existingCount
    failed = len(request.ids) - existingCount
    errors = [f"{failed} items not found"] if failed > 0 else []

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/rescan", response_model=BulkOperationResult)
async def bulk_rescan(
    media_type: str,
    request: BulkRescanRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk rescan files for multiple media items."""
    tableName = validateMediaType(media_type)
    errors = []

    # Fetch all items in a single query
    rows = await conn.fetch(
        f"SELECT id, file_path FROM {tableName} WHERE id = ANY($1)",
        request.ids,
    )

    foundIds = {row["id"] for row in rows}
    notFound = len(request.ids) - len(foundIds)
    if notFound > 0:
        errors.append(f"{notFound} items not found")

    # Process file status and batch update
    for row in rows:
        filePath = row.get("file_path")
        if filePath:
            fileExists = os.path.exists(filePath)
            fileSize = os.path.getsize(filePath) if fileExists and os.path.isfile(filePath) else None

            await conn.execute(
                f"UPDATE {tableName} SET has_file = $1, file_size = $2, updated_at = NOW() WHERE id = $3",
                fileExists, fileSize, row["id"],
            )

    return BulkOperationResult(
        success=notFound == 0,
        processed=len(rows),
        failed=notFound,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/tags", response_model=BulkOperationResult)
async def bulk_update_tags(
    media_type: str,
    request: BulkTagsRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk add/remove tags from multiple media items (batch operations)."""
    if media_type not in VALID_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )

    if not request.add_tags and not request.remove_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one tag to add or remove",
        )

    tagRepo = MediaTagRepository(conn)

    # Use batch operations instead of N*M individual queries
    async with conn.transaction():
        for tagId in request.remove_tags:
            await tagRepo.removeTagsBatch(media_type, request.ids, tagId)

        for tagId in request.add_tags:
            await tagRepo.addTagsBatch(media_type, request.ids, tagId)

    return BulkOperationResult(
        success=True,
        processed=len(request.ids),
        failed=0,
        total=len(request.ids),
        errors=[],
    )


@router.post("/{media_type}/media-profile", response_model=BulkOperationResult)
async def bulk_change_media_profile(
    media_type: str,
    request: BulkMediaProfileRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk change media profile for multiple items (single query)."""
    tableName = validateMediaType(media_type)
    profileRepo = MediaProfileRepository(conn)

    if not await profileRepo.exists(request.media_profile_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media profile not found",
        )

    # Single batch update query
    result = await conn.execute(
        f"UPDATE {tableName} SET media_profile_id = $1, updated_at = NOW() WHERE id = ANY($2)",
        request.media_profile_id,
        request.ids,
    )
    processed = int(result.split()[-1])
    failed = len(request.ids) - processed
    errors = [f"{failed} items not found"] if failed > 0 else []

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors,
    )


@router.post("/rename-all", response_model=BulkOperationResult)
async def bulk_rename_all(
    request: BulkRenameAllRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Rename all files in library to current naming convention."""
    processed = 0
    failed = 0
    errors = []

    mediaTypes = [request.media_type] if request.media_type else ["movie", "show", "anime", "album"]

    for mediaType in mediaTypes:
        if mediaType not in VALID_MEDIA_TYPES:
            continue

        tableName = TABLE_MAP[mediaType]

        # Count items with files in a single query per media type
        count = await conn.fetchval(
            f"SELECT COUNT(*) FROM {tableName} WHERE has_file = true AND file_path IS NOT NULL"
        )
        processed += count

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=processed + failed,
        errors=errors[:10],
    )
