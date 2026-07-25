from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from typing import Optional
import asyncpg
import os
import shutil

from app.db import get_db
from app.schemas.files import (
    MediaFiles,
    FileInfo,
    QualityCutoff,
    RenameFileRequest,
    ManualImportRequest,
    DeleteFilesRequest,
    FileOperationResult,
)
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services import media_files
from app.services import music_quality
from app.services.quality_definitions import QualityHierarchy

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


def _list_media_paths(file_path: str, media_type: str) -> list[str]:
    """
    List the physical media files for an item without probing them. Movies keep each
    downloaded version in the item folder, so all are listed. Shows and anime point at
    a single episode file. Albums and artists point at a folder of tracks.
    """
    from app.services.metadata_extractor import MetadataExtractor

    extractor = MetadataExtractor()
    is_audio = media_type in ("album", "artist")

    candidate_paths: list[str] = []
    base_dir = None
    if os.path.isdir(file_path):
        base_dir = file_path
    elif media_type == "movie":
        base_dir = os.path.dirname(file_path)
    else:
        candidate_paths = [file_path]

    if base_dir and os.path.isdir(base_dir):
        for name in sorted(os.listdir(base_dir)):
            item_path = os.path.join(base_dir, name)
            if os.path.isfile(item_path):
                candidate_paths.append(item_path)

    if is_audio:
        return [p for p in candidate_paths if extractor.is_audio_file(p)]
    return [p for p in candidate_paths if extractor.is_video_file(p)]


async def _compute_quality_cutoff(conn, media_type: str, media_id: int) -> Optional[QualityCutoff]:
    """
    Cutoff status for the detail-page badge. Music compares the album tier against the
    profile's music_quality_cutoff; video compares the file resolution against the
    highest resolution the profile allows. Returns None when no profile or no cutoff
    applies (so the badge is hidden rather than misleading).
    """
    if media_type not in ("movie", "show", "anime", "album"):
        return None

    table = TABLE_MAP[media_type]
    item = await conn.fetchrow(
        f"SELECT media_profile_id, quality_detected, upgrade_allowed FROM {table} WHERE id = $1",
        media_id,
    )
    if not item or not item["media_profile_id"]:
        return None

    profile = await conn.fetchrow(
        "SELECT upgrade_allowed, music_quality_cutoff, movie_resolutions, "
        "show_resolutions, anime_resolutions FROM media_profiles WHERE id = $1",
        item["media_profile_id"],
    )
    if not profile:
        return None

    effective_upgrade = item["upgrade_allowed"] if item["upgrade_allowed"] is not None else profile["upgrade_allowed"]
    current = item["quality_detected"]

    if media_type == "album":
        cutoff = profile["music_quality_cutoff"]
        if not cutoff:
            return None
        meets = music_quality.rank(current) >= music_quality.rank(cutoff) if current else False
        return QualityCutoff(
            meets_cutoff=meets,
            current_quality=music_quality.label(current) if current else None,
            cutoff_quality=music_quality.label(cutoff),
            upgrade_allowed=bool(effective_upgrade),
        )

    resolution_column = {
        "movie": "movie_resolutions",
        "show": "show_resolutions",
        "anime": "anime_resolutions",
    }[media_type]
    allowed = profile[resolution_column] or []
    if not allowed:
        return None
    scores = QualityHierarchy.RESOLUTION_SCORES
    top = max(allowed, key=lambda resolution: scores.get(resolution, 0))
    meets = scores.get(current, 0) >= scores.get(top, 0) if current else False
    return QualityCutoff(
        meets_cutoff=meets,
        current_quality=current,
        cutoff_quality=top,
        upgrade_allowed=bool(effective_upgrade),
    )


@router.get("/{media_type}/{media_id}", response_model=MediaFiles)
async def get_media_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get files associated with a media item
    """
    table_name = validate_media_type(media_type)

    title_column = "title" if media_type != "artist" else "name"
    # root_folder is display-only. Resolve its path from the item's root_folder_id,
    # since the root_folder_path column was replaced by root_folder_id.
    row = await conn.fetchrow(
        f"""
        SELECT m.id, m.{title_column} as title, m.file_path,
               rf.root_path as root_folder_path
        FROM {table_name} m
        LEFT JOIN root_folders rf ON m.root_folder_id = rf.id
        WHERE m.id = $1
        """,
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    files = []
    total_size = 0

    file_path = row.get("file_path")
    root_folder = row.get("root_folder_path")

    if file_path and os.path.exists(file_path):
        is_audio = media_type in ("album", "artist")
        # Listing the folder touches disk, so run it off the event loop.
        paths = await run_in_threadpool(_list_media_paths, file_path, media_type)
        # Read persisted metadata, probing (once) only files without a stored row.
        stored = await media_files.sync_and_get(conn, media_type, media_id, paths, is_audio)
        files = [
            FileInfo(
                file_path=r["file_path"],
                file_name=r["file_name"],
                file_size=r["file_size"],
                quality=r["quality"],
                resolution=r["resolution"],
                codec=r["codec"],
                audio_codec=r["audio_codec"],
                audio_channels=r["audio_channels"],
                container=r["container"],
                bit_depth=r["bit_depth"],
                hdr=r["hdr"] or False,
                created_at=r["created_at"].isoformat() if r.get("created_at") else None,
            )
            for r in stored
        ]
        total_size = sum(f.file_size or 0 for f in files)

    # Mode of the most recent completed download for this item (drives the Manual badge).
    grab_mode = await conn.fetchval(
        """
        SELECT grab_mode FROM download_history
        WHERE media_type = $1 AND media_id = $2 AND status = 'completed'
        ORDER BY completed_at DESC NULLS LAST LIMIT 1
        """,
        media_type,
        media_id,
    )

    quality_cutoff = await _compute_quality_cutoff(conn, media_type, media_id)

    return MediaFiles(
        media_type=media_type,
        media_id=media_id,
        media_title=row["title"],
        root_folder=root_folder,
        files=files,
        total_size=total_size,
        grab_mode=grab_mode,
        quality_cutoff=quality_cutoff,
    )


@router.post("/{media_type}/{media_id}/rename", response_model=FileOperationResult)
async def rename_file(
    media_type: str,
    media_id: int,
    request: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Rename a file associated with a media item
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    directory = os.path.dirname(request.file_path)
    extension = os.path.splitext(request.file_path)[1]
    new_path = os.path.join(directory, request.new_name + extension)

    if os.path.exists(new_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file with that name already exists",
        )

    try:
        os.rename(request.file_path, new_path)

        if row.get("file_path") == request.file_path:
            await conn.execute(
                f"UPDATE {table_name} SET file_path = $1, updated_at = NOW() WHERE id = $2",
                new_path,
                media_id,
            )

        return FileOperationResult(
            success=True,
            message="File renamed successfully",
            old_path=request.file_path,
            new_path=new_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rename file: {str(e)}",
        )


@router.post("/{media_type}/{media_id}/auto-rename", response_model=FileOperationResult)
async def auto_rename_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Automatically rename files using media profile naming format
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT * FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file associated with this media item",
        )

    return FileOperationResult(
        success=True,
        message="Auto-rename completed",
        old_path=file_path,
        new_path=file_path,
    )


@router.post("/{media_type}/{media_id}/manual-import", response_model=FileOperationResult)
async def manual_import(
    media_type: str,
    media_id: int,
    request: ManualImportRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Manually assign a file to a media item
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_size = os.path.getsize(request.file_path) if os.path.isfile(request.file_path) else None

    try:
        await conn.execute(
            f"""
            UPDATE {table_name}
            SET file_path = $1, has_file = true, file_size = $2, updated_at = NOW()
            WHERE id = $3
            """,
            request.file_path,
            file_size,
            media_id,
        )

        return FileOperationResult(
            success=True,
            message="File imported successfully",
            new_path=request.file_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import file: {str(e)}",
        )


@router.post("/{media_type}/{media_id}/rescan", response_model=FileOperationResult)
async def rescan_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Rescan file system for changes to media item files
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    file_exists = file_path and os.path.exists(file_path)
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

    return FileOperationResult(
        success=True,
        message=f"Rescan complete. File {'found' if file_exists else 'not found'}.",
        old_path=file_path,
    )


@router.delete("/{media_type}/{media_id}", response_model=FileOperationResult)
async def delete_media(
    media_type: str,
    media_id: int,
    request: DeleteFilesRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a media item from library, optionally deleting files from disk
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    files_deleted = False

    if request.delete_files and file_path and os.path.exists(file_path):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                files_deleted = True
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                files_deleted = True
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete files: {str(e)}",
            )

    await conn.execute(f"DELETE FROM {table_name} WHERE id = $1", media_id)
    await media_files.delete_for_item(conn, media_type, media_id)

    message = "Removed from library"
    if request.delete_files:
        message += " and files deleted from disk" if files_deleted else " (no files found to delete)"

    return FileOperationResult(
        success=True,
        message=message,
        old_path=file_path if files_deleted else None,
    )


@router.delete("/{media_type}/{media_id}/version", response_model=FileOperationResult)
async def delete_version(
    media_type: str,
    media_id: int,
    file_path: str,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a single version file of an item from disk, keeping the item and its other
    versions. Only a file tracked for this item may be removed. When the deleted file
    was the item's primary file, the item is repointed at the largest remaining version.
    """
    table_name = validate_media_type(media_type)

    tracked = await conn.fetchrow(
        "SELECT id FROM media_files WHERE media_type = $1 AND media_id = $2 AND file_path = $3",
        media_type,
        media_id,
        file_path,
    )
    if not tracked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found for this item",
        )

    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {str(e)}",
            )

    await media_files.delete_one(conn, file_path)

    # Repoint the item's primary file when the deleted version was the primary. Pick the
    # largest remaining version, or clear the file when none remain.
    item = await conn.fetchrow(f"SELECT file_path FROM {table_name} WHERE id = $1", media_id)
    if item and item["file_path"] == file_path:
        remaining = await conn.fetchrow(
            "SELECT file_path, file_size FROM media_files "
            "WHERE media_type = $1 AND media_id = $2 "
            "ORDER BY file_size DESC NULLS LAST LIMIT 1",
            media_type,
            media_id,
        )
        if remaining:
            await conn.execute(
                f"UPDATE {table_name} SET file_path = $1, file_size = $2, updated_at = NOW() WHERE id = $3",
                remaining["file_path"],
                remaining["file_size"],
                media_id,
            )
        else:
            await conn.execute(
                f"UPDATE {table_name} SET file_path = NULL, has_file = FALSE, updated_at = NOW() WHERE id = $1",
                media_id,
            )

    return FileOperationResult(
        success=True,
        message="Version deleted",
        old_path=file_path,
    )
