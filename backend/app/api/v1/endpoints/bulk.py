from fastapi import APIRouter, Depends, HTTPException, status
from collections import Counter
import asyncpg
import os
import shutil

from app.db import get_db
from app.services import rename_plan
from app.services import jellyfin
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
    RenamePreviewEntry,
    RenamePreviewCounts,
    RenamePreviewResponse,
    RenameApplyRequest,
    RenameApplyResult,
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


def previewResponse(entries) -> RenamePreviewResponse:
    """Build the preview response from classified rename entries."""
    return RenamePreviewResponse(
        entries=[_entryModel(entry) for entry in entries],
        counts=RenamePreviewCounts(**rename_plan.statusCounts(entries)),
        total=len(entries),
    )


def _entryModel(entry) -> RenamePreviewEntry:
    return RenamePreviewEntry(
        mediaType=entry.mediaType,
        itemId=entry.itemId,
        itemTitle=entry.itemTitle,
        oldPath=entry.oldPath,
        newPath=entry.newPath,
        status=entry.status,
        message=entry.message,
    )


async def applyRenameEntries(conn, entries) -> RenameApplyResult:
    """Apply previewed change entries through rename_plan and summarise the outcome."""
    results = await rename_plan.applyEntries(conn, [entry.model_dump() for entry in entries])
    counts = Counter(result.status for result in results)
    applied = counts.get(rename_plan.STATUS_APPLIED, 0)
    failed = counts.get(rename_plan.STATUS_ERROR, 0)
    errors = [
        f"{result.mediaType} {result.itemId}: {result.message}"
        for result in results
        if result.status == rename_plan.STATUS_ERROR
    ]
    return RenameApplyResult(
        success=failed == 0,
        processed=applied,
        failed=failed,
        total=len(results),
        errors=errors[:10],
        applied=applied,
        stale=counts.get(rename_plan.STATUS_STALE, 0),
        conflict=counts.get(rename_plan.STATUS_CONFLICT, 0),
        entries=[_entryModel(result) for result in results],
    )


async def _refresh_metadata_item(conn, media_type: str, row: dict) -> bool:
    """Re-fetch metadata from the source provider and update display fields."""
    if media_type == "movie":
        if not row.get("tmdb_id"):
            return False
        from app.services.metadata.tmdb import tmdb_service

        data = await tmdb_service.get_movie(row["tmdb_id"])
        if not data:
            return False
        await conn.execute(
            "UPDATE movies SET title = $1, overview = $2, poster_path = $3, backdrop_path = $4, "
            "rating = $5, popularity = $6, updated_at = NOW() WHERE id = $7",
            data.get("title") or row.get("title"),
            data.get("overview"),
            data.get("poster_path"),
            data.get("backdrop_path"),
            data.get("vote_average"),
            data.get("popularity"),
            row["id"],
        )
        return True

    if media_type == "show":
        if not row.get("tmdb_id"):
            return False
        from app.services.metadata.tmdb import tmdb_service

        data = await tmdb_service.get_tv(row["tmdb_id"])
        if not data:
            return False
        await conn.execute(
            "UPDATE shows SET title = $1, overview = $2, poster_path = $3, backdrop_path = $4, "
            "updated_at = NOW() WHERE id = $5",
            data.get("name") or row.get("title"),
            data.get("overview"),
            data.get("poster_path"),
            data.get("backdrop_path"),
            row["id"],
        )
        return True

    if media_type == "anime":
        if not row.get("anilist_id"):
            return False
        from app.services.metadata.anilist import anilist_service

        data = await anilist_service.get_anime(row["anilist_id"])
        if not data:
            return False
        titles = data.get("title") or {}
        title = titles.get("english") or titles.get("romaji") or row.get("title")
        cover = (data.get("coverImage") or {}).get("extraLarge") or (data.get("coverImage") or {}).get("large")
        await conn.execute(
            "UPDATE anime SET title = $1, overview = $2, poster_path = $3, backdrop_path = $4, "
            "updated_at = NOW() WHERE id = $5",
            title,
            data.get("description"),
            cover,
            data.get("bannerImage"),
            row["id"],
        )
        return True

    if media_type == "album":
        if not row.get("deezer_id"):
            return False
        from app.services.metadata.deezer import deezer_service

        data = await deezer_service.get_album(row["deezer_id"])
        if not data:
            return False
        await conn.execute(
            "UPDATE albums SET title = $1, cover = $2, cover_medium = $3, cover_big = $4, "
            "cover_xl = $5, updated_at = NOW() WHERE id = $6",
            data.get("title") or row.get("title"),
            data.get("cover"),
            data.get("cover_medium"),
            data.get("cover_big"),
            data.get("cover_xl"),
            row["id"],
        )
        return True

    if media_type == "artist":
        if not row.get("deezer_id"):
            return False
        from app.services.metadata.deezer import deezer_service

        data = await deezer_service.get_artist(row["deezer_id"])
        if not data:
            return False
        await conn.execute(
            "UPDATE artists SET name = $1, picture = $2, picture_medium = $3, picture_big = $4, "
            "picture_xl = $5, updated_at = NOW() WHERE id = $6",
            data.get("name") or row.get("name"),
            data.get("picture"),
            data.get("picture_medium"),
            data.get("picture_big"),
            data.get("picture_xl"),
            row["id"],
        )
        return True

    return False


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
            f"SELECT id, file_path FROM {tableName} WHERE id = ANY($1)",
            request.ids,
        )
        deletedPaths = []
        for row in rows:
            filePath = row.get("file_path")
            if filePath and os.path.exists(filePath):
                try:
                    if os.path.isfile(filePath):
                        os.remove(filePath)
                        deletedPaths.append(filePath)
                    elif os.path.isdir(filePath):
                        shutil.rmtree(filePath)
                        deletedPaths.append(filePath)
                except Exception as e:
                    errors.append(f"File deletion for {row['id']}: {str(e)}")
        if deletedPaths:
            jellyfin.queueLibraryUpdate(deletedPaths, jellyfin.UPDATE_DELETED)

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


@router.post("/{media_type}/rename/preview", response_model=RenamePreviewResponse)
async def bulk_rename_preview(
    media_type: str,
    request: BulkRenameRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Show where the current naming format puts each file of the given items. Changes nothing."""
    tableName = validateMediaType(media_type)
    rows = await conn.fetch(f"SELECT * FROM {tableName} WHERE id = ANY($1)", request.ids)
    plans = await rename_plan.buildPreview(conn, {media_type: rows})
    return previewResponse([entry for plan in plans for entry in plan.entries])


@router.post("/{media_type}/rename", response_model=RenameApplyResult)
async def bulk_rename(
    media_type: str,
    request: RenameApplyRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Move the files of a preview to their previewed targets. Stale and conflicting entries are skipped."""
    validateMediaType(media_type)
    if any(entry.mediaType != media_type for entry in request.entries):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Every entry must be of media type {media_type}",
        )
    return await applyRenameEntries(conn, request.entries)


@router.post("/{media_type}/refresh-metadata", response_model=BulkOperationResult)
async def bulk_refresh_metadata(
    media_type: str,
    request: BulkRefreshMetadataRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Re-pull metadata from the source provider (TMDB/AniList/Deezer) for the given items."""
    tableName = validateMediaType(media_type)
    rows = await conn.fetch(f"SELECT * FROM {tableName} WHERE id = ANY($1)", request.ids)
    foundIds = {row["id"] for row in rows}
    notFound = [i for i in request.ids if i not in foundIds]

    processed = 0
    failed = len(notFound)
    errors = [f"{len(notFound)} items not found"] if notFound else []

    for row in rows:
        try:
            if await _refresh_metadata_item(conn, media_type, dict(row)):
                processed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            if len(errors) < 10:
                errors.append(f"Refresh {row['id']}: {str(e)}")

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
                fileExists,
                fileSize,
                row["id"],
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


@router.post("/rename-all/preview", response_model=RenamePreviewResponse)
async def bulk_rename_all_preview(
    request: BulkRenameAllRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Show where the current naming formats put every library file. media_type or
    media_types narrows the media types, and media_profile_id narrows to items using
    that profile. Changes nothing.
    """
    if request.media_types:
        mediaTypes = request.media_types
    elif request.media_type:
        mediaTypes = [request.media_type]
    else:
        mediaTypes = list(rename_plan.RENAMEABLE_TYPES)

    rowsByType = {}
    for mediaType in mediaTypes:
        if mediaType not in rename_plan.RENAMEABLE_TYPES:
            continue
        tableName = TABLE_MAP[mediaType]
        query = f"SELECT * FROM {tableName} WHERE has_file = true AND file_path IS NOT NULL"
        if request.media_profile_id is not None:
            rowsByType[mediaType] = await conn.fetch(f"{query} AND media_profile_id = $1", request.media_profile_id)
        else:
            rowsByType[mediaType] = await conn.fetch(query)

    plans = await rename_plan.buildPreview(conn, rowsByType)
    return previewResponse([entry for plan in plans for entry in plan.entries])


@router.post("/rename-all", response_model=RenameApplyResult)
async def bulk_rename_all(
    request: RenameApplyRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Move the files of a library wide preview to their previewed targets. Entries may span media types."""
    invalid = {entry.mediaType for entry in request.entries} - set(VALID_MEDIA_TYPES)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )
    return await applyRenameEntries(conn, request.entries)
