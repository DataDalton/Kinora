from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
import asyncpg

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services.metadata.tmdb import tmdb_service

router = APIRouter()


class ShowCreate(BaseModel):
    tmdb_id: int
    monitored: bool = True
    media_profile_id: Optional[int] = None
    season_monitoring: str = "all"


@router.get("/")
async def get_shows(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    monitored: Optional[bool] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all TV shows from library with pagination and filtering
    """
    offset = (page - 1) * limit

    query = "SELECT * FROM shows WHERE 1=1"
    params = []
    param_count = 1

    if status:
        query += f" AND status = ${param_count}"
        params.append(status)
        param_count += 1

    if monitored is not None:
        query += f" AND monitored = ${param_count}"
        params.append(monitored)
        param_count += 1

    query += f" ORDER BY title LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)

    return {
        "shows": [dict(row) for row in rows],
        "page": page,
        "limit": limit,
    }


@router.get("/{show_id}")
async def get_show(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific TV show by ID
    """
    row = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    return dict(row)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_show(
    show_data: ShowCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Add a TV show to library
    """
    existing = await conn.fetchrow(
        "SELECT id FROM shows WHERE tmdb_id = $1",
        show_data.tmdb_id
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Show already exists in library",
        )

    metadata = await tmdb_service.get_tv(show_data.tmdb_id)
    parsed_data = tmdb_service.parse_tv_data(metadata)

    row = await conn.fetchrow(
        """
        INSERT INTO shows (
            title, original_title, overview, poster_path, backdrop_path,
            release_date, genres, rating, vote_count, popularity,
            status, tmdb_id, imdb_id, tvdb_id, monitored,
            media_profile_id, number_of_seasons, number_of_episodes,
            episode_run_time, networks, production_companies,
            first_air_date, last_air_date, in_production, season_monitoring
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18,
            $19, $20, $21, $22, $23, $24, $25
        )
        RETURNING *
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
        "wanted",
        parsed_data["tmdb_id"],
        parsed_data["imdb_id"],
        parsed_data["tvdb_id"],
        show_data.monitored,
        show_data.media_profile_id,
        parsed_data["number_of_seasons"],
        parsed_data["number_of_episodes"],
        parsed_data["episode_run_time"],
        parsed_data["networks"],
        parsed_data["production_companies"],
        parsed_data["first_air_date"],
        parsed_data["last_air_date"],
        parsed_data["in_production"],
        show_data.season_monitoring,
    )

    return dict(row)


@router.put("/{show_id}")
async def update_show(
    show_id: int,
    updates: dict,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update TV show in library
    """
    existing = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    for field, value in updates.items():
        update_fields.append(f"{field} = ${param_count}")
        update_values.append(value)
        param_count += 1

    update_fields.append("updated_at = NOW()")
    update_values.append(show_id)

    query = f"""
        UPDATE shows
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *update_values)
    return dict(row)


@router.delete("/{show_id}")
async def delete_show(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Remove TV show from library
    """
    result = await conn.execute("DELETE FROM shows WHERE id = $1", show_id)

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    return {"message": "Show removed from library successfully"}
