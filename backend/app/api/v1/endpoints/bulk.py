from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg
import os
import shutil

from app.core.database import get_db
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


def validate_media_type(media_type: str) -> str:
    """Validate and return the table name for a media type"""
    if media_type not in VALID_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )
    return TABLE_MAP[media_type]


@router.post("/{media_type}/monitor", response_model=BulkOperationResult)
async def bulk_monitor(
    media_type: str,
    request: BulkMonitorRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Bulk monitor/unmonitor multiple media items
    """
    table_name = validate_media_type(media_type)
    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            result = await conn.execute(
                f"UPDATE {table_name} SET monitored = $1, updated_at = NOW() WHERE id = $2",
                request.monitored,
                media_id,
            )
            if result == "UPDATE 1":
                processed += 1
            else:
                failed += 1
                errors.append(f"Item {media_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/delete", response_model=BulkOperationResult)
async def bulk_delete(
    media_type: str,
    request: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Bulk delete multiple media items with optional file deletion
    """
    table_name = validate_media_type(media_type)
    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            if request.delete_files:
                row = await conn.fetchrow(
                    f"SELECT file_path, root_folder_path FROM {table_name} WHERE id = $1",
                    media_id,
                )
                if row:
                    file_path = row.get("file_path")
                    root_folder = row.get("root_folder_path")

                    if file_path and os.path.exists(file_path):
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)

            result = await conn.execute(
                f"DELETE FROM {table_name} WHERE id = $1",
                media_id,
            )
            if result == "DELETE 1":
                processed += 1
            else:
                failed += 1
                errors.append(f"Item {media_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
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
    """
    Bulk rename files for multiple media items using current naming convention
    """
    table_name = validate_media_type(media_type)
    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            row = await conn.fetchrow(
                f"SELECT * FROM {table_name} WHERE id = $1",
                media_id,
            )
            if not row:
                failed += 1
                errors.append(f"Item {media_id} not found")
                continue

            if not row.get("has_file") or not row.get("file_path"):
                failed += 1
                errors.append(f"Item {media_id} has no file to rename")
                continue

            processed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

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
    """
    Bulk refresh metadata for multiple media items
    """
    table_name = validate_media_type(media_type)
    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            row = await conn.fetchrow(
                f"SELECT id FROM {table_name} WHERE id = $1",
                media_id,
            )
            if not row:
                failed += 1
                errors.append(f"Item {media_id} not found")
                continue

            processed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

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
    """
    Bulk rescan files for multiple media items
    """
    table_name = validate_media_type(media_type)
    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            row = await conn.fetchrow(
                f"SELECT file_path FROM {table_name} WHERE id = $1",
                media_id,
            )
            if not row:
                failed += 1
                errors.append(f"Item {media_id} not found")
                continue

            file_path = row.get("file_path")
            if file_path:
                file_exists = os.path.exists(file_path)
                file_size = os.path.getsize(file_path) if file_exists and os.path.isfile(file_path) else None

                await conn.execute(
                    f"""
                    UPDATE {table_name}
                    SET has_file = $1, file_size = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    file_exists,
                    file_size,
                    media_id,
                )

            processed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
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
    """
    Bulk add/remove tags from multiple media items
    """
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

    processed = 0
    failed = 0
    errors = []

    async with conn.transaction():
        for media_id in request.ids:
            try:
                for tag_id in request.remove_tags:
                    await conn.execute(
                        """
                        DELETE FROM media_tags
                        WHERE tag_id = $1 AND media_type = $2 AND media_id = $3
                        """,
                        tag_id,
                        media_type,
                        media_id,
                    )

                for tag_id in request.add_tags:
                    await conn.execute(
                        """
                        INSERT INTO media_tags (tag_id, media_type, media_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
                        """,
                        tag_id,
                        media_type,
                        media_id,
                    )

                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Item {media_id}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/{media_type}/media-profile", response_model=BulkOperationResult)
async def bulk_change_media_profile(
    media_type: str,
    request: BulkMediaProfileRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Bulk change media profile for multiple items
    """
    table_name = validate_media_type(media_type)

    profile = await conn.fetchrow(
        "SELECT id FROM media_profiles WHERE id = $1",
        request.media_profile_id,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media profile not found",
        )

    processed = 0
    failed = 0
    errors = []

    for media_id in request.ids:
        try:
            result = await conn.execute(
                f"UPDATE {table_name} SET media_profile_id = $1, updated_at = NOW() WHERE id = $2",
                request.media_profile_id,
                media_id,
            )
            if result == "UPDATE 1":
                processed += 1
            else:
                failed += 1
                errors.append(f"Item {media_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Item {media_id}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=len(request.ids),
        errors=errors[:10],
    )


@router.post("/rename-all", response_model=BulkOperationResult)
async def bulk_rename_all(
    request: BulkRenameAllRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Rename all files in library to current naming convention
    """
    processed = 0
    failed = 0
    errors = []

    media_types = [request.media_type] if request.media_type else ["movie", "show", "anime", "album"]

    for media_type in media_types:
        if media_type not in VALID_MEDIA_TYPES:
            continue

        table_name = TABLE_MAP[media_type]

        rows = await conn.fetch(
            f"SELECT id, file_path FROM {table_name} WHERE has_file = true AND file_path IS NOT NULL"
        )

        for row in rows:
            try:
                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"{media_type} {row['id']}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=processed + failed,
        errors=errors[:10],
    )
