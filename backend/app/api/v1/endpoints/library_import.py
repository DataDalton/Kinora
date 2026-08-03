"""
Library import endpoints for scanning and importing existing media files.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel, Field
import asyncpg
import os
import shutil
from datetime import datetime

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.library_scanner import LibraryScanner
from app.services.media_matcher import MediaMatcher
from app.services.file_manager import FileManager
from app.services import naming_tokens
from pathlib import Path
from app.schemas.movie import Movie
from app.schemas.show import Show
from app.schemas.anime import Anime

router = APIRouter()


class ScanRequest(BaseModel):
    """Request to scan a directory for media files."""

    directory_path: str = Field(..., description="Path to directory to scan")
    media_type: str = Field(..., description="Media type: movie, show, or anime")
    recursive: bool = Field(True, description="Scan subdirectories recursively")
    skip_samples: bool = Field(True, description="Skip sample and trailer files")


class ImportRequest(BaseModel):
    """Request to import scanned files into library."""

    scanned_files: List[dict] = Field(..., description="List of scanned file metadata")
    media_type: str = Field(..., description="Media type: movie, show, or anime")
    root_folder_path: str = Field(..., description="Destination root folder for organized files")
    copy_mode: str = Field("move", description="File operation: move or copy")
    media_profile_id: Optional[int] = Field(None, description="Media profile ID for naming conventions")
    monitored: bool = Field(True, description="Monitor imported media")


class ScanResponse(BaseModel):
    """Response from directory scan."""

    scanned_count: int
    matched_count: int
    unmatched_count: int
    matched_files: List[dict]
    unmatched_files: List[dict]


class ImportResponse(BaseModel):
    """Response from import operation."""

    success_count: int
    failed_count: int
    imported_items: List[dict]
    failed_items: List[dict]


@router.post("/scan", response_model=ScanResponse)
async def scan_directory(
    scan_request: ScanRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Scan a directory for media files and match them to metadata.
    """
    # Validate media type
    if scan_request.media_type not in ["movie", "show", "anime"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media_type. Must be 'movie', 'show', or 'anime'"
        )

    # Validate directory exists
    if not os.path.exists(scan_request.directory_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Directory not found: {scan_request.directory_path}"
        )

    try:
        # Initialize services
        scanner = LibraryScanner()
        matcher = MediaMatcher()

        # Scan directory
        scanned_files = scanner.scan_directory(
            directory_path=scan_request.directory_path,
            media_type=scan_request.media_type,
            recursive=scan_request.recursive,
            skip_samples=scan_request.skip_samples,
        )

        # Match files to metadata
        match_results = matcher.batch_match_files(scanned_files=scanned_files, similarity_threshold=0.7)

        return ScanResponse(
            scanned_count=len(scanned_files),
            matched_count=len(match_results["matched"]),
            unmatched_count=len(match_results["unmatched"]),
            matched_files=match_results["matched"],
            unmatched_files=match_results["unmatched"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error scanning directory: {str(e)}"
        )


@router.post("/import", response_model=ImportResponse)
async def import_files(
    import_request: ImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Import matched files into library.
    Adds to database and organizes files according to naming conventions.
    """
    # Validate media type
    if import_request.media_type not in ["movie", "show", "anime"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media_type")

    # Validate copy mode
    if import_request.copy_mode not in ["move", "copy"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid copy_mode. Must be 'move' or 'copy'"
        )

    # Validate root folder
    if not os.path.exists(import_request.root_folder_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Root folder not found: {import_request.root_folder_path}"
        )

    imported_items = []
    failed_items = []

    try:
        file_manager = FileManager()

        for matched_file in import_request.scanned_files:
            try:
                # Import based on media type
                if import_request.media_type == "movie":
                    result = await _import_movie(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager,
                    )
                elif import_request.media_type == "show":
                    result = await _import_show(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager,
                    )
                elif import_request.media_type == "anime":
                    result = await _import_anime(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager,
                    )

                imported_items.append(result)

            except Exception as e:
                failed_items.append({"file": matched_file.get("scanned_file", {}).get("file_path"), "error": str(e)})

        # Evaluate on_import transcoding rules against each adopted file. Rules are split
        # by trigger so a library import can be transcoded on different terms than a fresh
        # download, or left alone entirely.
        if imported_items:
            try:
                from app.tasks.transcoding import check_and_apply_transcoding_rules

                for item in imported_items:
                    if item.get("id") and item.get("file_path"):
                        check_and_apply_transcoding_rules.delay(
                            item["id"], import_request.media_type, item["file_path"], "on_import"
                        )
            except Exception as e:
                print(f"Could not queue transcoding rule check: {e}")

        return ImportResponse(
            success_count=len(imported_items),
            failed_count=len(failed_items),
            imported_items=imported_items,
            failed_items=failed_items,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error importing files: {str(e)}"
        )


async def _resolve_movie_dest(conn, matched_file, tmdb_id, media_profile_id, source_path, root_folder_path):
    """Build the destination path for an imported movie via the naming token engine."""
    prof = None
    if media_profile_id:
        prof = await conn.fetchrow(
            "SELECT movie_naming_format, movie_folder_format, illegal_char_replacement, "
            "colon_replacement FROM media_profiles WHERE id = $1",
            media_profile_id,
        )
    naming = (prof and prof["movie_naming_format"]) or "{Movie CleanTitle} ({Release Year})"
    folder = (prof and prof["movie_folder_format"]) or "{Movie CleanTitle} ({Release Year})"
    illegal = (prof and prof["illegal_char_replacement"]) or ""
    colon = (prof and prof["colon_replacement"]) or " -"
    row = {
        "title": matched_file.get("title"),
        "release_date": matched_file.get("release_date"),
        "tmdb_id": tmdb_id,
        "imdb_id": matched_file.get("imdb_id"),
    }
    ctx = naming_tokens.build_movie_context(row, source_path, Path(source_path).name)
    folder_name = naming_tokens.render(folder, ctx, illegal_replacement=illegal, colon_replacement=colon)
    filename = naming_tokens.render(
        naming,
        ctx,
        illegal_replacement=illegal,
        colon_replacement=colon,
        extension=Path(source_path).suffix,
    )
    return os.path.join(root_folder_path, folder_name, filename)


async def _import_movie(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager,
) -> dict:
    """Import a single movie file."""
    scanned_file = matched_file.get("scanned_file", {})
    source_path = scanned_file.get("file_path")

    # Check if movie already exists by TMDB ID. The matcher normalizes the id to
    # tmdb_id, so read that first and fall back to the raw id.
    tmdb_id = matched_file.get("tmdb_id") or matched_file.get("id")
    existing = await conn.fetchrow("SELECT id, file_path FROM movies WHERE tmdb_id = $1", tmdb_id)

    if existing:
        # Update existing movie with file info
        movie_id = existing["id"]

        # Organize file
        destination_path = await _resolve_movie_dest(
            conn, matched_file, tmdb_id, media_profile_id, source_path, root_folder_path
        )

        # Organize file (move or copy)
        file_manager.organize_file(
            source_path=source_path,
            destination_path=destination_path,
            operation="move" if copy_mode == "move" else "copy",
        )

        # Update database
        await conn.execute(
            """
            UPDATE movies
            SET file_path = $1, file_size = $2, quality_detected = $3,
                has_file = TRUE, status = 'completed', updated_at = NOW()
            WHERE id = $4
            """,
            destination_path,
            scanned_file.get("file_size"),
            scanned_file.get("quality"),
            movie_id,
        )

    else:
        # Insert new movie
        row = await conn.fetchrow(
            """
            INSERT INTO movies (
                title, original_title, overview, poster_path, backdrop_path,
                release_date, genres, rating, vote_count, popularity,
                tmdb_id, imdb_id, monitored, media_profile_id,
                has_file, file_path, file_size, quality_detected, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            RETURNING id
            """,
            matched_file.get("title"),
            matched_file.get("original_title"),
            matched_file.get("overview"),
            matched_file.get("poster_path"),
            matched_file.get("backdrop_path"),
            matched_file.get("release_date"),
            matched_file.get("genres"),
            matched_file.get("vote_average"),
            matched_file.get("vote_count"),
            matched_file.get("popularity"),
            tmdb_id,
            matched_file.get("imdb_id"),
            monitored,
            media_profile_id,
            True,
            source_path,  # Will be updated after organization
            scanned_file.get("file_size"),
            scanned_file.get("quality"),
            "completed",
        )

        movie_id = row["id"]

        # Organize file
        destination_path = await _resolve_movie_dest(
            conn, matched_file, tmdb_id, media_profile_id, source_path, root_folder_path
        )

        file_manager.organize_file(
            source_path=source_path,
            destination_path=destination_path,
            operation="move" if copy_mode == "move" else "copy",
        )

        # Update file path
        await conn.execute("UPDATE movies SET file_path = $1 WHERE id = $2", destination_path, movie_id)

    return {"id": movie_id, "title": matched_file.get("title"), "file_path": destination_path}


async def _resolve_root_folder_id(conn, root_folder_path: str) -> Optional[int]:
    """Resolve the root_folders.id for a destination root path."""
    return await conn.fetchval("SELECT id FROM root_folders WHERE root_path = $1", root_folder_path)


async def _resolve_show_dest(conn, show_row, scanned_file, media_profile_id, source_path, root_folder_path):
    """Build the destination path for an imported show episode via the naming engine."""
    prof = None
    if media_profile_id:
        prof = await conn.fetchrow(
            "SELECT show_naming_format, show_folder_format, illegal_char_replacement, "
            "colon_replacement FROM media_profiles WHERE id = $1",
            media_profile_id,
        )
    naming = (prof and prof["show_naming_format"]) or "{Show Title} - S{Season:00}E{Episode:00}"
    folder = (prof and prof["show_folder_format"]) or "{Show Title}/Season {Season:00}"
    illegal = (prof and prof["illegal_char_replacement"]) or ""
    colon = (prof and prof["colon_replacement"]) or " -"
    episode_info = {
        "season_number": scanned_file.get("season") or 1,
        "episode_number": scanned_file.get("episode"),
        "episode_title": scanned_file.get("episode_title") or "",
    }
    ctx = naming_tokens.build_show_context(show_row, episode_info, source_path, Path(source_path).name)
    folder_name = naming_tokens.render(folder, ctx, illegal_replacement=illegal, colon_replacement=colon)
    filename = naming_tokens.render(
        naming, ctx, illegal_replacement=illegal, colon_replacement=colon, extension=Path(source_path).suffix
    )
    return os.path.join(root_folder_path, folder_name, filename)


async def _import_show(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager,
) -> dict:
    """
    Import a single show episode file. Find-or-create the show by TMDB id, organize
    the episode with the naming engine, and point the show at the organized file.
    This mirrors how the download organizer handles a completed show download.
    """
    scanned_file = matched_file.get("scanned_file", {})
    source_path = scanned_file.get("file_path")
    if not source_path:
        raise ValueError("Scanned file has no path")

    tmdb_id = matched_file.get("tmdb_id") or matched_file.get("id")
    root_folder_id = await _resolve_root_folder_id(conn, root_folder_path)

    existing = await conn.fetchrow("SELECT id FROM shows WHERE tmdb_id = $1", tmdb_id) if tmdb_id else None
    if existing:
        show_id = existing["id"]
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO shows (
                title, original_title, overview, poster_path, backdrop_path,
                first_air_date, release_date, genres, rating, vote_count, popularity,
                tmdb_id, imdb_id, tvdb_id, monitored, media_profile_id, root_folder_id,
                number_of_seasons, number_of_episodes, has_file, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
            RETURNING id
            """,
            matched_file.get("title"),
            matched_file.get("original_title"),
            matched_file.get("overview"),
            matched_file.get("poster_path"),
            matched_file.get("backdrop_path"),
            matched_file.get("first_air_date"),
            matched_file.get("release_date"),
            matched_file.get("genres"),
            matched_file.get("rating"),
            matched_file.get("vote_count"),
            matched_file.get("popularity"),
            tmdb_id,
            matched_file.get("imdb_id"),
            matched_file.get("tvdb_id"),
            monitored,
            media_profile_id,
            root_folder_id,
            matched_file.get("number_of_seasons"),
            matched_file.get("number_of_episodes"),
            True,
            "completed",
        )
        show_id = row["id"]

    show_row = {
        "title": matched_file.get("title"),
        "first_air_date": matched_file.get("first_air_date"),
        "release_date": matched_file.get("release_date"),
        "tmdb_id": tmdb_id,
        "tvdb_id": matched_file.get("tvdb_id"),
    }
    destination_path = await _resolve_show_dest(
        conn, show_row, scanned_file, media_profile_id, source_path, root_folder_path
    )

    file_manager.organize_file(
        source_path=source_path,
        destination_path=destination_path,
        operation="move" if copy_mode == "move" else "copy",
    )

    await conn.execute(
        """
        UPDATE shows
        SET file_path = $1, file_size = $2, quality_detected = $3, has_file = TRUE,
            status = 'completed', root_folder_id = COALESCE(root_folder_id, $4), updated_at = NOW()
        WHERE id = $5
        """,
        destination_path,
        scanned_file.get("file_size"),
        scanned_file.get("quality"),
        root_folder_id,
        show_id,
    )

    return {"id": show_id, "title": matched_file.get("title"), "file_path": destination_path}


async def _resolve_anime_dest(conn, anime_row, scanned_file, media_profile_id, source_path, root_folder_path):
    """Build the destination path for an imported anime episode via the naming engine."""
    prof = None
    if media_profile_id:
        prof = await conn.fetchrow(
            "SELECT anime_naming_format, anime_folder_format, illegal_char_replacement, "
            "colon_replacement FROM media_profiles WHERE id = $1",
            media_profile_id,
        )
    naming = (prof and prof["anime_naming_format"]) or "{Anime Title} - {Episode:00}"
    folder = (prof and prof["anime_folder_format"]) or "{Anime Title}"
    illegal = (prof and prof["illegal_char_replacement"]) or ""
    colon = (prof and prof["colon_replacement"]) or " -"
    episode_info = {
        "season_number": scanned_file.get("season") or 1,
        "episode_number": scanned_file.get("episode"),
        "absolute_episode": scanned_file.get("episode"),
        "episode_title": scanned_file.get("episode_title") or "",
    }
    ctx = naming_tokens.build_anime_context(anime_row, episode_info, source_path, Path(source_path).name)
    folder_name = naming_tokens.render(folder, ctx, illegal_replacement=illegal, colon_replacement=colon)
    filename = naming_tokens.render(
        naming, ctx, illegal_replacement=illegal, colon_replacement=colon, extension=Path(source_path).suffix
    )
    return os.path.join(root_folder_path, folder_name, filename)


async def _import_anime(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager,
) -> dict:
    """
    Import a single anime file. Find-or-create the anime by Anilist id, organize the
    episode with the naming engine, and point the anime at the organized file.
    """
    scanned_file = matched_file.get("scanned_file", {})
    source_path = scanned_file.get("file_path")
    if not source_path:
        raise ValueError("Scanned file has no path")

    anilist_id = matched_file.get("anilist_id") or matched_file.get("id")
    root_folder_id = await _resolve_root_folder_id(conn, root_folder_path)

    existing = await conn.fetchrow("SELECT id FROM anime WHERE anilist_id = $1", anilist_id) if anilist_id else None
    if existing:
        anime_id = existing["id"]
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO anime (
                title, original_title, overview, poster_path, backdrop_path, release_date,
                genres, rating, popularity, anilist_id, mal_id, monitored, media_profile_id,
                root_folder_id, episodes, duration, season_year, season_period, format,
                source, studios, is_adult, has_file, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
            RETURNING id
            """,
            matched_file.get("title"),
            matched_file.get("original_title"),
            matched_file.get("overview"),
            matched_file.get("poster_path"),
            matched_file.get("backdrop_path"),
            matched_file.get("release_date"),
            matched_file.get("genres"),
            matched_file.get("rating"),
            matched_file.get("popularity"),
            anilist_id,
            matched_file.get("mal_id"),
            monitored,
            media_profile_id,
            root_folder_id,
            matched_file.get("episodes"),
            matched_file.get("duration"),
            matched_file.get("season_year"),
            matched_file.get("season_period"),
            matched_file.get("format"),
            matched_file.get("source"),
            matched_file.get("studios"),
            matched_file.get("is_adult", False),
            True,
            "completed",
        )
        anime_id = row["id"]

    anime_row = {
        "title": matched_file.get("title"),
        "season_year": matched_file.get("season_year"),
        "tmdb_id": matched_file.get("tmdb_id"),
        "anilist_id": anilist_id,
        "mal_id": matched_file.get("mal_id"),
    }
    destination_path = await _resolve_anime_dest(
        conn, anime_row, scanned_file, media_profile_id, source_path, root_folder_path
    )

    file_manager.organize_file(
        source_path=source_path,
        destination_path=destination_path,
        operation="move" if copy_mode == "move" else "copy",
    )

    await conn.execute(
        """
        UPDATE anime
        SET file_path = $1, file_size = $2, quality_detected = $3, has_file = TRUE,
            status = 'completed', root_folder_id = COALESCE(root_folder_id, $4), updated_at = NOW()
        WHERE id = $5
        """,
        destination_path,
        scanned_file.get("file_size"),
        scanned_file.get("quality"),
        root_folder_id,
        anime_id,
    )

    return {"id": anime_id, "title": matched_file.get("title"), "file_path": destination_path}


@router.get("/estimate")
async def estimate_scan(
    directory_path: str,
    current_user: User = Depends(get_current_user),
):
    """
    Estimate scan time for a directory.
    """
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Directory not found: {directory_path}")

    try:
        scanner = LibraryScanner()
        estimate = scanner.estimate_scan_time(directory_path)
        return estimate

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error estimating scan time: {str(e)}"
        )
