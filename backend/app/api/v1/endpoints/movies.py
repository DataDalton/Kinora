from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import asyncpg
import os
import shutil
import json

from app.core.database import get_db
from app.schemas.movie import Movie, MovieCreate, MovieUpdate
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.tmdb import tmdb_service

router = APIRouter()


@router.get("/", response_model=List[Movie])
async def get_movies(
    skip: int = 0,
    limit: int = 100,
    monitored_only: bool = False,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all movies from library
    """
    query = "SELECT * FROM movies"
    if monitored_only:
        query += " WHERE monitored = TRUE"
    query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {skip}"

    rows = await conn.fetch(query)
    return [Movie(**dict(row)) for row in rows]


@router.get("/{movie_id}", response_model=Movie)
async def get_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific movie by ID
    """
    row = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return Movie(**dict(row))


@router.post("/", response_model=Movie, status_code=status.HTTP_201_CREATED)
async def add_movie(
    movie_data: MovieCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add a movie to library
    """
    # Check if movie already exists by TMDB ID
    if movie_data.tmdb_id:
        existing = await conn.fetchrow(
            "SELECT id FROM movies WHERE tmdb_id = $1", movie_data.tmdb_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already exists in library",
            )

    row = await conn.fetchrow(
        """
        INSERT INTO movies (
            title, original_title, overview, poster_path, backdrop_path,
            release_date, genres, rating, vote_count, popularity,
            tmdb_id, imdb_id, monitored, media_profile_id, root_folder_path
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        RETURNING *
        """,
        movie_data.title,
        movie_data.original_title,
        movie_data.overview,
        movie_data.poster_path,
        movie_data.backdrop_path,
        movie_data.release_date,
        movie_data.genres,
        movie_data.rating,
        movie_data.vote_count,
        movie_data.popularity,
        movie_data.tmdb_id,
        movie_data.imdb_id,
        movie_data.monitored,
        movie_data.media_profile_id,
        movie_data.root_folder_path,
    )

    return Movie(**dict(row))


@router.put("/{movie_id}", response_model=Movie)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update a movie in library
    """
    # Check if movie exists
    existing = await conn.fetchrow("SELECT id FROM movies WHERE id = $1", movie_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    # Build update query dynamically
    update_fields = []
    values = []
    param_count = 1

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    values.append(movie_id)
    query = f"""
        UPDATE movies
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Movie(**dict(row))


@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Remove a movie from library
    """
    result = await conn.execute("DELETE FROM movies WHERE id = $1", movie_id)

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    return None


@router.put("/{movie_id}/monitoring")
async def update_movie_monitoring(
    movie_id: int,
    monitored: Optional[bool] = None,
    upgrade_allowed: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update movie monitoring settings
    """
    movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    update_fields = []
    values = []
    param_count = 1

    if monitored is not None:
        update_fields.append(f"monitored = ${param_count}")
        values.append(monitored)
        param_count += 1

    if upgrade_allowed is not None:
        update_fields.append(f"upgrade_allowed = ${param_count}")
        values.append(upgrade_allowed)
        param_count += 1
    elif "upgrade_allowed" in (await conn.fetchrow("SELECT column_name FROM information_schema.columns WHERE table_name='movies' AND column_name='upgrade_allowed'") or {}):
        update_fields.append(f"upgrade_allowed = ${param_count}")
        values.append(upgrade_allowed)
        param_count += 1

    if not update_fields:
        return {"message": "No updates provided"}

    values.append(movie_id)
    query = f"""
        UPDATE movies
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Movie(**dict(row))


@router.delete("/{movie_id}/delete")
async def delete_movie_with_files(
    movie_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a movie from library with option to delete files from disk
    """
    movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    files_deleted = []
    errors = []

    if delete_files and movie["file_path"]:
        file_path = movie["file_path"]
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                files_deleted.append(file_path)
                parent_dir = os.path.dirname(file_path)
                if parent_dir and os.path.isdir(parent_dir):
                    remaining = os.listdir(parent_dir)
                    if not remaining or all(f.endswith(('.nfo', '.jpg', '.png', '.srt', '.sub')) for f in remaining):
                        shutil.rmtree(parent_dir)
                        files_deleted.append(parent_dir)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                files_deleted.append(file_path)
        except Exception as e:
            errors.append(f"Failed to delete {file_path}: {str(e)}")

    await conn.execute("DELETE FROM download_history WHERE media_type = 'movie' AND media_id = $1", movie_id)
    await conn.execute("DELETE FROM blocklist WHERE media_type = 'movie' AND media_id = $1", movie_id)
    await conn.execute("DELETE FROM media_tags WHERE media_type = 'movie' AND media_id = $1", movie_id)
    await conn.execute("DELETE FROM movies WHERE id = $1", movie_id)

    return {
        "message": "Movie deleted successfully",
        "files_deleted": files_deleted,
        "errors": errors,
    }


@router.post("/{movie_id}/refresh-metadata")
async def refresh_movie_metadata(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Refresh movie metadata from TMDB
    """
    movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    if not movie["tmdb_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie has no TMDB ID, cannot refresh metadata",
        )

    try:
        tmdb_data = await tmdb_service.get_movie(movie["tmdb_id"])
        parsed_data = tmdb_service.parse_movie_data(tmdb_data)

        await conn.execute(
            """
            UPDATE movies SET
                title = $1, original_title = $2, overview = $3, poster_path = $4,
                backdrop_path = $5, release_date = $6, genres = $7, rating = $8,
                vote_count = $9, popularity = $10, imdb_id = $11, runtime = $12,
                budget = $13, revenue = $14, tagline = $15, production_companies = $16,
                collection_id = $17, collection_name = $18, updated_at = NOW()
            WHERE id = $19
            """,
            parsed_data["title"],
            parsed_data["original_title"],
            parsed_data["overview"],
            parsed_data["poster_path"],
            parsed_data["backdrop_path"],
            parsed_data["release_date"],
            parsed_data["genres"],
            parsed_data["rating"],
            parsed_data["vote_count"],
            parsed_data["popularity"],
            parsed_data["imdb_id"],
            parsed_data["runtime"],
            parsed_data["budget"],
            parsed_data["revenue"],
            parsed_data["tagline"],
            parsed_data["production_companies"],
            parsed_data["collection_id"],
            parsed_data["collection_name"],
            movie_id,
        )

        updated_movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
        return Movie(**dict(updated_movie))

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
    """
    Rescan movie files on disk and update database
    """
    movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    file_path = movie["file_path"]
    has_file = False
    file_size = None

    if file_path and os.path.exists(file_path):
        if os.path.isfile(file_path):
            has_file = True
            file_size = os.path.getsize(file_path)
        elif os.path.isdir(file_path):
            video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
            for f in os.listdir(file_path):
                if f.lower().endswith(video_extensions):
                    has_file = True
                    full_path = os.path.join(file_path, f)
                    file_size = os.path.getsize(full_path)
                    break

    await conn.execute(
        """
        UPDATE movies SET has_file = $1, file_size = $2, updated_at = NOW()
        WHERE id = $3
        """,
        has_file,
        file_size,
        movie_id,
    )

    updated_movie = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", movie_id)
    return Movie(**dict(updated_movie))


@router.get("/{movie_id}/credits")
async def get_movie_credits(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get movie cast and crew from TMDB
    """
    movie = await conn.fetchrow("SELECT tmdb_id, metadata FROM movies WHERE id = $1", movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    if not movie["tmdb_id"]:
        return {"cast": [], "crew": []}

    try:
        tmdb_data = await tmdb_service.get_movie(movie["tmdb_id"])
        credits = tmdb_data.get("credits", {})

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

        crew = [
            {
                "id": person.get("id"),
                "name": person.get("name"),
                "job": person.get("job"),
                "department": person.get("department"),
                "profile_path": person.get("profile_path"),
            }
            for person in credits.get("crew", [])
            if person.get("job") in ["Director", "Writer", "Screenplay", "Producer", "Executive Producer", "Cinematography", "Original Music Composer"]
        ]

        return {"cast": cast, "crew": crew}

    except Exception as e:
        return {"cast": [], "crew": [], "error": str(e)}
