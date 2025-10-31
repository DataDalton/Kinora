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

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.library_scanner import LibraryScanner
from app.services.media_matcher import MediaMatcher
from app.services.file_manager import FileManager
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
    if scan_request.media_type not in ['movie', 'show', 'anime']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid media_type. Must be 'movie', 'show', or 'anime'"
        )

    # Validate directory exists
    if not os.path.exists(scan_request.directory_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {scan_request.directory_path}"
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
            skip_samples=scan_request.skip_samples
        )

        # Match files to metadata
        match_results = matcher.batch_match_files(
            scanned_files=scanned_files,
            similarity_threshold=0.7
        )

        return ScanResponse(
            scanned_count=len(scanned_files),
            matched_count=len(match_results['matched']),
            unmatched_count=len(match_results['unmatched']),
            matched_files=match_results['matched'],
            unmatched_files=match_results['unmatched']
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scanning directory: {str(e)}"
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
    if import_request.media_type not in ['movie', 'show', 'anime']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid media_type"
        )

    # Validate copy mode
    if import_request.copy_mode not in ['move', 'copy']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid copy_mode. Must be 'move' or 'copy'"
        )

    # Validate root folder
    if not os.path.exists(import_request.root_folder_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Root folder not found: {import_request.root_folder_path}"
        )

    imported_items = []
    failed_items = []

    try:
        file_manager = FileManager()

        for matched_file in import_request.scanned_files:
            try:
                # Import based on media type
                if import_request.media_type == 'movie':
                    result = await _import_movie(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager
                    )
                elif import_request.media_type == 'show':
                    result = await _import_show(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager
                    )
                elif import_request.media_type == 'anime':
                    result = await _import_anime(
                        conn=conn,
                        matched_file=matched_file,
                        root_folder_path=import_request.root_folder_path,
                        copy_mode=import_request.copy_mode,
                        monitored=import_request.monitored,
                        media_profile_id=import_request.media_profile_id,
                        file_manager=file_manager
                    )

                imported_items.append(result)

            except Exception as e:
                failed_items.append({
                    'file': matched_file.get('scanned_file', {}).get('file_path'),
                    'error': str(e)
                })

        return ImportResponse(
            success_count=len(imported_items),
            failed_count=len(failed_items),
            imported_items=imported_items,
            failed_items=failed_items
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing files: {str(e)}"
        )


async def _import_movie(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager
) -> dict:
    """Import a single movie file."""
    scanned_file = matched_file.get('scanned_file', {})
    source_path = scanned_file.get('file_path')

    # Check if movie already exists by TMDB ID
    tmdb_id = matched_file.get('id')
    existing = await conn.fetchrow(
        "SELECT id, file_path FROM movies WHERE tmdb_id = $1", tmdb_id
    )

    if existing:
        # Update existing movie with file info
        movie_id = existing['id']

        # Organize file
        new_file_path = file_manager.format_movie_filename(
            title=matched_file.get('title'),
            year=matched_file.get('release_date', '')[:4] if matched_file.get('release_date') else None,
            quality=scanned_file.get('quality'),
            tmdb_id=tmdb_id,
            pattern="{title} ({year})"
        )

        destination_path = os.path.join(root_folder_path, new_file_path)

        # Organize file (move or copy)
        file_manager.organize_file(
            source_path=source_path,
            destination_path=destination_path,
            operation='move' if copy_mode == 'move' else 'copy'
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
            scanned_file.get('file_size'),
            scanned_file.get('quality'),
            movie_id
        )

    else:
        # Insert new movie
        row = await conn.fetchrow(
            """
            INSERT INTO movies (
                title, original_title, overview, poster_path, backdrop_path,
                release_date, genres, rating, vote_count, popularity,
                tmdb_id, imdb_id, monitored, media_profile_id, root_folder_path,
                has_file, file_path, file_size, quality_detected, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
            RETURNING id
            """,
            matched_file.get('title'),
            matched_file.get('original_title'),
            matched_file.get('overview'),
            matched_file.get('poster_path'),
            matched_file.get('backdrop_path'),
            matched_file.get('release_date'),
            matched_file.get('genres'),
            matched_file.get('vote_average'),
            matched_file.get('vote_count'),
            matched_file.get('popularity'),
            tmdb_id,
            matched_file.get('imdb_id'),
            monitored,
            media_profile_id,
            root_folder_path,
            True,
            source_path,  # Will be updated after organization
            scanned_file.get('file_size'),
            scanned_file.get('quality'),
            'completed'
        )

        movie_id = row['id']

        # Organize file
        new_file_path = file_manager.format_movie_filename(
            title=matched_file.get('title'),
            year=matched_file.get('release_date', '')[:4] if matched_file.get('release_date') else None,
            quality=scanned_file.get('quality'),
            tmdb_id=tmdb_id,
            pattern="{title} ({year})"
        )

        destination_path = os.path.join(root_folder_path, new_file_path)

        file_manager.organize_file(
            source_path=source_path,
            destination_path=destination_path,
            operation='move' if copy_mode == 'move' else 'copy'
        )

        # Update file path
        await conn.execute(
            "UPDATE movies SET file_path = $1 WHERE id = $2",
            destination_path,
            movie_id
        )

    return {
        'id': movie_id,
        'title': matched_file.get('title'),
        'file_path': destination_path
    }


async def _import_show(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager
) -> dict:
    """Import a single show episode file."""
    # TODO: Implement show import logic
    # This is more complex as we need to handle seasons and episodes
    raise NotImplementedError("Show import not yet implemented")


async def _import_anime(
    conn: asyncpg.Connection,
    matched_file: dict,
    root_folder_path: str,
    copy_mode: str,
    monitored: bool,
    media_profile_id: Optional[int],
    file_manager: FileManager
) -> dict:
    """Import a single anime file."""
    # TODO: Implement anime import logic
    raise NotImplementedError("Anime import not yet implemented")


@router.get("/estimate")
async def estimate_scan(
    directory_path: str,
    current_user: User = Depends(get_current_user),
):
    """
    Estimate scan time for a directory.
    """
    if not os.path.exists(directory_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {directory_path}"
        )

    try:
        scanner = LibraryScanner()
        estimate = scanner.estimate_scan_time(directory_path)
        return estimate

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error estimating scan time: {str(e)}"
        )
