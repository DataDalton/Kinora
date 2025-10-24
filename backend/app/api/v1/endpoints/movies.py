from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg

from app.core.database import get_db
from app.schemas.movie import Movie, MovieCreate, MovieUpdate
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

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
