from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
import asyncpg

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services.metadata.anilist import anilist_service

router = APIRouter()


class AnimeCreate(BaseModel):
    anilist_id: int
    monitored: bool = True
    media_profile_id: Optional[int] = None
    episode_monitoring: str = "all"


@router.get("/")
async def get_anime(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    monitored: Optional[bool] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all anime from library with pagination and filtering
    """
    offset = (page - 1) * limit

    query = "SELECT * FROM anime WHERE 1=1"
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
        "anime": [dict(row) for row in rows],
        "page": page,
        "limit": limit,
    }


@router.get("/{anime_id}")
async def get_anime_by_id(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get a specific anime by ID
    """
    row = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    return dict(row)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_anime(
    anime_data: AnimeCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Add an anime to library
    """
    existing = await conn.fetchrow(
        "SELECT id FROM anime WHERE anilist_id = $1",
        anime_data.anilist_id
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anime already exists in library",
        )

    metadata = await anilist_service.get_anime(anime_data.anilist_id)
    parsed_data = anilist_service.parse_anime_data(metadata)

    row = await conn.fetchrow(
        """
        INSERT INTO anime (
            title, original_title, overview, poster_path, backdrop_path,
            release_date, genres, rating, popularity,
            status, anilist_id, mal_id, monitored,
            media_profile_id, episodes, duration, season_year,
            season_period, format, source, studios, is_adult,
            absolute_numbering, has_file, episode_monitoring
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
        parsed_data["popularity"],
        "wanted",
        parsed_data["anilist_id"],
        parsed_data["mal_id"],
        anime_data.monitored,
        anime_data.media_profile_id,
        parsed_data["episodes"],
        parsed_data["duration"],
        parsed_data["season_year"],
        parsed_data["season_period"],
        parsed_data["format"],
        parsed_data["source"],
        parsed_data["studios"],
        parsed_data["is_adult"],
        True,
        False,
        anime_data.episode_monitoring,
    )

    return dict(row)


@router.put("/{anime_id}")
async def update_anime(
    anime_id: int,
    updates: dict,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update anime in library
    """
    existing = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    for field, value in updates.items():
        update_fields.append(f"{field} = ${param_count}")
        update_values.append(value)
        param_count += 1

    update_fields.append("updated_at = NOW()")
    update_values.append(anime_id)

    query = f"""
        UPDATE anime
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *update_values)
    return dict(row)


@router.delete("/{anime_id}")
async def delete_anime(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Remove anime from library
    """
    result = await conn.execute("DELETE FROM anime WHERE id = $1", anime_id)

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    return {"message": "Anime removed from library successfully"}
