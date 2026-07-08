from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import asyncpg
import os
import shutil
from pathlib import Path

from app.db import get_db
from app.services import naming_tokens
from app.tasks.download_monitor import parse_episode_info
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


_NAMING_DEFAULTS = {
    "movie": ("{Movie CleanTitle} ({Release Year})", "{Movie CleanTitle} ({Release Year})"),
    "show": ("{Show Title} - S{Season:00}E{Episode:00}", "{Show Title}/Season {Season:00}"),
    "anime": ("{Anime Title} - {Episode:00}", "{Anime Title}"),
}
_VIDEO_EXT = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg", ".m2ts", ".ts", ".webm"}
_AUDIO_EXT = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"}


async def _root_path_for(conn, table: str, root_folder_id) -> Optional[str]:
    if not root_folder_id:
        return None
    return await conn.fetchval("SELECT root_path FROM root_folders WHERE id = $1", root_folder_id)


async def _video_naming_config(conn, media_type, media_profile_id):
    prof = None
    if media_profile_id:
        prof = await conn.fetchrow(
            "SELECT movie_naming_format, movie_folder_format, show_naming_format, show_folder_format, "
            "anime_naming_format, anime_folder_format, illegal_char_replacement, colon_replacement "
            "FROM media_profiles WHERE id = $1",
            media_profile_id,
        )
    default_file, default_folder = _NAMING_DEFAULTS[media_type]
    naming = (prof and prof[f"{media_type}_naming_format"]) or default_file
    folder = (prof and prof[f"{media_type}_folder_format"]) or default_folder
    illegal = (prof and prof["illegal_char_replacement"]) or ""
    colon = (prof and prof["colon_replacement"]) or " -"
    return naming, folder, illegal, colon


def _item_top_folder(file_path: str, root_path: Optional[str]) -> str:
    """Return the item's top-level folder (root/<ItemFolder>) or the file's directory."""
    if not root_path:
        return file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
    try:
        rel = os.path.relpath(file_path, root_path)
    except ValueError:
        return os.path.dirname(file_path)
    first = rel.split(os.sep)[0]
    if first in ("", ".", ".."):
        return os.path.dirname(file_path)
    return os.path.join(root_path, first)


def _walk_media(folder: str, extensions: set) -> List[str]:
    if os.path.isfile(folder):
        return [folder]
    found = []
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() in extensions:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


async def _rename_media_item(conn, media_type: str, row: dict) -> int:
    """
    Re-render an item's file(s) with the current profile naming format and move them.
    Returns the number of files moved. Never deletes source data.
    """
    file_path = row.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return 0
    root_path = await _root_path_for(conn, TABLE_MAP[media_type], row.get("root_folder_id"))
    moved = 0

    if media_type == "movie":
        naming, folder, illegal, colon = await _video_naming_config(conn, "movie", row.get("media_profile_id"))
        ctx = naming_tokens.build_movie_context(dict(row), file_path, os.path.basename(file_path))
        folder_name = naming_tokens.render(folder, ctx, illegal_replacement=illegal, colon_replacement=colon)
        filename = naming_tokens.render(
            naming, ctx, illegal_replacement=illegal, colon_replacement=colon, extension=Path(file_path).suffix
        )
        base = root_path or os.path.dirname(os.path.dirname(file_path))
        new_path = os.path.join(base, folder_name, filename)
        if os.path.normpath(new_path) != os.path.normpath(file_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(file_path, new_path)
            await conn.execute(
                "UPDATE movies SET file_path = $1, updated_at = NOW() WHERE id = $2", new_path, row["id"]
            )
            moved = 1
        return moved

    if media_type in ("show", "anime"):
        naming, folder, illegal, colon = await _video_naming_config(conn, media_type, row.get("media_profile_id"))
        top = _item_top_folder(file_path, root_path)
        base = root_path or os.path.dirname(top)
        first_new = None
        for src in _walk_media(top, _VIDEO_EXT):
            ep = parse_episode_info(os.path.basename(src))
            if ep.get("episode_number") is None:
                continue
            episode_info = {
                "season_number": ep.get("season_number") or 1,
                "episode_number": ep["episode_number"],
                "episode_title": ep.get("episode_title") or "",
                "absolute_episode": ep.get("absolute_episode"),
            }
            if media_type == "show":
                ctx = naming_tokens.build_show_context(dict(row), episode_info, src, os.path.basename(src))
            else:
                ctx = naming_tokens.build_anime_context(dict(row), episode_info, src, os.path.basename(src))
            folder_name = naming_tokens.render(folder, ctx, illegal_replacement=illegal, colon_replacement=colon)
            filename = naming_tokens.render(
                naming, ctx, illegal_replacement=illegal, colon_replacement=colon, extension=Path(src).suffix
            )
            new_path = os.path.join(base, folder_name, filename)
            if os.path.normpath(new_path) != os.path.normpath(src):
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(src, new_path)
                moved += 1
            if first_new is None:
                first_new = new_path
        if first_new:
            await conn.execute(
                f"UPDATE {TABLE_MAP[media_type]} SET file_path = $1, updated_at = NOW() WHERE id = $2",
                first_new,
                row["id"],
            )
        return moved

    if media_type == "album":
        moved = await _rename_album(conn, row, root_path)
        return moved

    # artists have no files of their own to rename
    return 0


async def _rename_album(conn, row: dict, root_path: Optional[str]) -> int:
    """Re-render an album's track files using the music naming formats."""
    from app.services.file_manager import FileManager

    file_path = row.get("file_path")
    prof = None
    if row.get("media_profile_id"):
        prof = await conn.fetchrow(
            "SELECT music_artist_folder_format, music_album_folder_format, music_track_naming_format, "
            "music_multi_disc_format, illegal_char_replacement, colon_replacement "
            "FROM media_profiles WHERE id = $1",
            row["media_profile_id"],
        )
    artist_fmt = (prof and prof["music_artist_folder_format"]) or "{artist}"
    album_fmt = (prof and prof["music_album_folder_format"]) or "{album} ({year})"
    track_fmt = (prof and prof["music_track_naming_format"]) or "{track:00} - {title}"
    multi_fmt = (prof and prof["music_multi_disc_format"]) or "{disc:00}-{track:00} - {title}"
    illegal = (prof and prof["illegal_char_replacement"]) or ""
    colon = (prof and prof["colon_replacement"]) or " -"

    fm = FileManager()
    top = _item_top_folder(file_path, root_path)
    base = root_path or os.path.dirname(top)
    audio_files = _walk_media(top, _AUDIO_EXT)
    if not audio_files:
        return 0

    track_rows = await conn.fetch(
        "SELECT disk_number, track_position, title FROM tracks WHERE album_id = $1 ORDER BY disk_number, track_position",
        row["id"],
    )
    use_meta = len(track_rows) == len(audio_files)
    is_multi_disc = any((t["disk_number"] or 1) > 1 for t in track_rows)
    year = row["release_date"].year if row.get("release_date") else None
    genres = row.get("genres") or []
    genre = (genres[0].get("name") if isinstance(genres[0], dict) else genres[0]) if genres else None

    first_new = None
    moved = 0
    for idx, src in enumerate(audio_files, start=1):
        if use_meta:
            meta = track_rows[idx - 1]
            disc_number = meta["disk_number"] or 1
            track_number = meta["track_position"] or idx
            track_title = meta["title"] or Path(src).stem
        else:
            disc_number, track_number, track_title = 1, idx, Path(src).stem
        track_data = {
            "artist": row.get("artist_name") or "Unknown Artist",
            "album": row.get("title"),
            "year": year,
            "track_number": track_number,
            "disc_number": disc_number,
            "title": track_title,
            "genre": genre,
            "extension": Path(src).suffix,
        }
        artist_folder = fm.format_music_filename(
            pattern=artist_fmt,
            track_data=track_data,
            include_extension=False,
            illegal_replacement=illegal,
            colon_replacement=colon,
        )
        album_folder = fm.format_music_filename(
            pattern=album_fmt,
            track_data=track_data,
            include_extension=False,
            illegal_replacement=illegal,
            colon_replacement=colon,
        )
        track_name = fm.format_music_filename(
            pattern=(multi_fmt if is_multi_disc else track_fmt),
            track_data=track_data,
            include_extension=True,
            illegal_replacement=illegal,
            colon_replacement=colon,
        )
        new_path = os.path.join(base, artist_folder, album_folder, track_name)
        if os.path.normpath(new_path) != os.path.normpath(src):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(src, new_path)
            moved += 1
        if first_new is None:
            first_new = os.path.dirname(new_path)
    if first_new:
        await conn.execute("UPDATE albums SET file_path = $1, updated_at = NOW() WHERE id = $2", first_new, row["id"])
    return moved


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
    """Rename files for the given items to the current naming convention (real move on disk)."""
    tableName = validateMediaType(media_type)
    errors = []

    rows = await conn.fetch(f"SELECT * FROM {tableName} WHERE id = ANY($1)", request.ids)
    foundIds = {row["id"] for row in rows}
    notFound = [i for i in request.ids if i not in foundIds]

    processed = 0
    failed = len(notFound)
    if notFound:
        errors.append(f"{len(notFound)} items not found")

    for row in rows:
        item = dict(row)
        if not item.get("has_file") or not item.get("file_path"):
            failed += 1
            continue
        try:
            await _rename_media_item(conn, media_type, item)
            processed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Rename {item['id']}: {str(e)}")

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


@router.post("/rename-all", response_model=BulkOperationResult)
async def bulk_rename_all(
    request: BulkRenameAllRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Rename every library file to the current naming convention (real move on disk)."""
    processed = 0
    failed = 0
    errors = []

    mediaTypes = [request.media_type] if request.media_type else ["movie", "show", "anime", "album"]

    for mediaType in mediaTypes:
        if mediaType not in VALID_MEDIA_TYPES:
            continue
        tableName = TABLE_MAP[mediaType]
        rows = await conn.fetch(f"SELECT * FROM {tableName} WHERE has_file = true AND file_path IS NOT NULL")
        for row in rows:
            try:
                await _rename_media_item(conn, mediaType, dict(row))
                processed += 1
            except Exception as e:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{mediaType} {row['id']}: {str(e)}")

    return BulkOperationResult(
        success=failed == 0,
        processed=processed,
        failed=failed,
        total=processed + failed,
        errors=errors[:10],
    )
