from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from pydantic import BaseModel
import asyncpg
import os
import shutil

from app.db import get_db
from app.db.repositories import MovieRepository
from app.schemas.movie import Movie, MovieCreate, MovieUpdate
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.tmdb import tmdb_service

router = APIRouter()


class MovieMonitoringUpdate(BaseModel):
    monitored: Optional[bool] = None
    upgradeAllowed: Optional[bool] = None


class MovieAddRequest(BaseModel):
    tmdb_id: int
    monitored: bool = True
    media_profile_id: Optional[int] = None


@router.get("/")
async def get_movies(
    skip: int = 0,
    limit: int = 100,
    monitored_only: bool = False,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all movies from library with their tags (single query with JSON aggregation)."""
    repo = MovieRepository(conn)
    return await repo.listWithTags(limit=limit, offset=skip, monitoredOnly=monitored_only)


@router.get("/{movie_id}")
async def get_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get a specific movie by ID with its tags."""
    repo = MovieRepository(conn)
    movie = await repo.getWithTags(movie_id)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return movie


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_movie(
    movie_data: MovieAddRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add a movie to library by fetching metadata from TMDB."""
    repo = MovieRepository(conn)

    if await repo.existsByTmdbId(movie_data.tmdb_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already exists in library",
        )

    # Fetch metadata from TMDB
    metadata = await tmdb_service.get_movie(movie_data.tmdb_id)
    parsedData = tmdb_service.parse_movie_data(metadata)

    movieData = {
        **parsedData,
        "status": "wanted",
        "monitored": movie_data.monitored,
        "media_profile_id": movie_data.media_profile_id,
        "has_file": False,
    }

    return await repo.create(movieData)


@router.put("/{movie_id}", response_model=Movie)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update a movie in library."""
    repo = MovieRepository(conn)

    updateData = movie_data.model_dump(exclude_unset=True)
    if not updateData:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    movie = await repo.update(movie_id, updateData)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return movie


@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Remove a movie from library."""
    repo = MovieRepository(conn)
    deleted = await repo.delete(movie_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return None


@router.put("/{movie_id}/monitoring")
async def update_movie_monitoring(
    movie_id: int,
    data: MovieMonitoringUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update movie monitoring settings."""
    sentFields = data.model_dump(exclude_unset=True)
    updateData = {}

    if "monitored" in sentFields:
        updateData["monitored"] = data.monitored
    if "upgradeAllowed" in sentFields:
        updateData["upgrade_allowed"] = data.upgradeAllowed

    if not updateData:
        return {"message": "No updates provided"}

    # Update with raw SQL and return dict (like shows do) to avoid Pydantic validation
    setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updateData.keys()))
    row = await conn.fetchrow(
        f"UPDATE movies SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
        movie_id, *updateData.values()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return dict(row)


@router.delete("/{movie_id}/delete")
async def delete_movie_with_files(
    movie_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a movie from library with option to delete files from disk."""
    repo = MovieRepository(conn)
    movie = await repo.getById(movie_id)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    filesDeleted = []
    errors = []

    if delete_files and movie.file_path:
        filePath = movie.file_path
        try:
            if os.path.isfile(filePath):
                os.remove(filePath)
                filesDeleted.append(filePath)
                parentDir = os.path.dirname(filePath)
                if parentDir and os.path.isdir(parentDir):
                    remaining = os.listdir(parentDir)
                    if not remaining or all(f.endswith(('.nfo', '.jpg', '.png', '.srt', '.sub')) for f in remaining):
                        shutil.rmtree(parentDir)
                        filesDeleted.append(parentDir)
            elif os.path.isdir(filePath):
                shutil.rmtree(filePath)
                filesDeleted.append(filePath)
        except Exception as e:
            errors.append(f"Failed to delete {filePath}: {str(e)}")

    await repo.deleteWithRelations(movie_id)

    return {
        "message": "Movie deleted successfully",
        "files_deleted": filesDeleted,
        "errors": errors,
    }


@router.post("/{movie_id}/refresh-metadata")
async def refresh_movie_metadata(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Refresh movie metadata from TMDB."""
    repo = MovieRepository(conn)
    movie = await repo.getById(movie_id)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    if not movie.tmdb_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie has no TMDB ID, cannot refresh metadata",
        )

    try:
        tmdbData = await tmdb_service.get_movie(movie.tmdb_id)
        parsedData = tmdb_service.parse_movie_data(tmdbData)
        return await repo.refreshMetadata(movie_id, parsedData)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh metadata: {str(e)}",
        )


@router.post("/{movie_id}/rescan")
async def rescan_movie_files(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Rescan movie files on disk and update database."""
    repo = MovieRepository(conn)
    movie = await repo.getById(movie_id)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    filePath = movie.file_path
    hasFile = False
    fileSize = None

    if filePath and os.path.exists(filePath):
        if os.path.isfile(filePath):
            hasFile = True
            fileSize = os.path.getsize(filePath)
        elif os.path.isdir(filePath):
            videoExtensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
            for f in os.listdir(filePath):
                if f.lower().endswith(videoExtensions):
                    hasFile = True
                    fullPath = os.path.join(filePath, f)
                    fileSize = os.path.getsize(fullPath)
                    break

    return await repo.updateFileInfo(movie_id, hasFile, fileSize=fileSize)


@router.get("/{movie_id}/credits")
async def get_movie_credits(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get movie cast and crew from TMDB."""
    repo = MovieRepository(conn)
    movie = await repo.getById(movie_id)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    if not movie.tmdb_id:
        return {"cast": [], "crew": []}

    try:
        tmdbData = await tmdb_service.get_movie(movie.tmdb_id)
        credits = tmdbData.get("credits", {})

        cast = [
            {
                "id": person.get("id"),
                "name": person.get("name"),
                "character": person.get("character"),
                "profile_path": person.get("profile_path"),
                "order": person.get("order"),
            }
            for person in credits.get("cast", [])[:20]
        ]

        crewJobs = ["Director", "Writer", "Screenplay", "Producer", "Executive Producer", "Cinematography", "Original Music Composer"]
        crew = [
            {
                "id": person.get("id"),
                "name": person.get("name"),
                "job": person.get("job"),
                "department": person.get("department"),
                "profile_path": person.get("profile_path"),
            }
            for person in credits.get("crew", [])
            if person.get("job") in crewJobs
        ]

        return {"cast": cast, "crew": crew}

    except Exception as e:
        return {"cast": [], "crew": [], "error": str(e)}
