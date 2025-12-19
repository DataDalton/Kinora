from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncpg
import os
import shutil
import json

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


@router.put("/{anime_id}/monitoring")
async def update_anime_monitoring(
    anime_id: int,
    monitored: Optional[bool] = None,
    upgrade_allowed: Optional[bool] = None,
    episode_monitoring: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update anime monitoring settings
    """
    anime = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
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

    if episode_monitoring is not None:
        update_fields.append(f"episode_monitoring = ${param_count}")
        values.append(episode_monitoring)
        param_count += 1

    if not update_fields:
        return {"message": "No updates provided"}

    values.append(anime_id)
    query = f"""
        UPDATE anime
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return dict(row)


@router.delete("/{anime_id}/delete")
async def delete_anime_with_files(
    anime_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Delete anime from library with option to delete files from disk
    """
    anime = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    files_deleted = []
    errors = []

    if delete_files and anime.get("root_folder_path"):
        folder_path = anime["root_folder_path"]
        try:
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                files_deleted.append(folder_path)
        except Exception as e:
            errors.append(f"Failed to delete {folder_path}: {str(e)}")

    await conn.execute("DELETE FROM anime_episodes WHERE anime_id = $1", anime_id)
    await conn.execute("DELETE FROM download_history WHERE media_type = 'anime' AND media_id = $1", anime_id)
    await conn.execute("DELETE FROM blocklist WHERE media_type = 'anime' AND media_id = $1", anime_id)
    await conn.execute("DELETE FROM media_tags WHERE media_type = 'anime' AND media_id = $1", anime_id)
    await conn.execute("DELETE FROM anime WHERE id = $1", anime_id)

    return {
        "message": "Anime deleted successfully",
        "files_deleted": files_deleted,
        "errors": errors,
    }


@router.post("/{anime_id}/refresh-metadata")
async def refresh_anime_metadata(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Refresh anime metadata from AniList
    """
    anime = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    if not anime["anilist_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anime has no AniList ID, cannot refresh metadata",
        )

    try:
        anilist_data = await anilist_service.get_anime(anime["anilist_id"])
        parsed_data = anilist_service.parse_anime_data(anilist_data)

        genres_json = json.dumps(parsed_data["genres"]) if parsed_data["genres"] else None
        studios_json = json.dumps(parsed_data["studios"]) if parsed_data["studios"] else None

        await conn.execute(
            """
            UPDATE anime SET
                title = $1, original_title = $2, overview = $3, poster_path = $4,
                backdrop_path = $5, release_date = $6, genres = $7, rating = $8,
                popularity = $9, mal_id = $10, episodes = $11, duration = $12,
                season_year = $13, season_period = $14, format = $15, source = $16,
                studios = $17, is_adult = $18, updated_at = NOW()
            WHERE id = $19
            """,
            parsed_data["title"],
            parsed_data["original_title"],
            parsed_data["overview"],
            parsed_data["poster_path"],
            parsed_data["backdrop_path"],
            parsed_data["release_date"],
            genres_json,
            parsed_data["rating"],
            parsed_data["popularity"],
            parsed_data["mal_id"],
            parsed_data["episodes"],
            parsed_data["duration"],
            parsed_data["season_year"],
            parsed_data["season_period"],
            parsed_data["format"],
            parsed_data["source"],
            studios_json,
            parsed_data["is_adult"],
            anime_id,
        )

        updated = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
        return dict(updated)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh metadata: {str(e)}",
        )


@router.post("/{anime_id}/rescan")
async def rescan_anime_files(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Rescan anime files on disk and update database
    """
    anime = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    folder_path = anime.get("root_folder_path")
    has_file = False
    file_count = 0

    if folder_path and os.path.isdir(folder_path):
        video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(video_extensions):
                    has_file = True
                    file_count += 1

    await conn.execute(
        """
        UPDATE anime SET has_file = $1, updated_at = NOW()
        WHERE id = $2
        """,
        has_file,
        anime_id,
    )

    updated = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    return {**dict(updated), "files_found": file_count}


@router.get("/{anime_id}/credits")
async def get_anime_credits(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get anime characters and staff from AniList
    """
    anime = await conn.fetchrow("SELECT anilist_id FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    if not anime["anilist_id"]:
        return {"characters": [], "staff": []}

    try:
        anilist_data = await anilist_service.get_anime(anime["anilist_id"])

        characters = [
            {
                "id": char.get("id"),
                "name": char.get("name", {}).get("full"),
                "image": char.get("image", {}).get("large"),
            }
            for char in anilist_data.get("characters", {}).get("nodes", [])
        ]

        staff = [
            {
                "id": person.get("id"),
                "name": person.get("name", {}).get("full"),
                "role": ", ".join(person.get("primaryOccupations", [])) if person.get("primaryOccupations") else "Staff",
            }
            for person in anilist_data.get("staff", {}).get("nodes", [])
        ]

        studios = [
            studio.get("name")
            for studio in anilist_data.get("studios", {}).get("nodes", [])
        ]

        return {"characters": characters, "staff": staff, "studios": studios}

    except Exception as e:
        return {"characters": [], "staff": [], "studios": [], "error": str(e)}


@router.get("/{anime_id}/episodes")
async def get_anime_episodes(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get episodes for an anime
    """
    anime = await conn.fetchrow("SELECT * FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    episodes = await conn.fetch(
        """
        SELECT * FROM anime_episodes
        WHERE anime_id = $1
        ORDER BY episode_number
        """,
        anime_id,
    )

    return {
        "episodes": [dict(ep) for ep in episodes],
        "total_episodes": anime["episodes"],
        "absolute_numbering": anime.get("absolute_numbering", True),
    }


@router.put("/{anime_id}/episodes/{episode_number}")
async def update_anime_episode(
    anime_id: int,
    episode_number: int,
    monitored: Optional[bool] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update a specific episode's monitoring status
    """
    anime = await conn.fetchrow("SELECT id FROM anime WHERE id = $1", anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    episode = await conn.fetchrow(
        "SELECT * FROM anime_episodes WHERE anime_id = $1 AND episode_number = $2",
        anime_id, episode_number
    )

    if not episode:
        await conn.execute(
            """
            INSERT INTO anime_episodes (anime_id, episode_number, monitored)
            VALUES ($1, $2, $3)
            """,
            anime_id, episode_number, monitored if monitored is not None else True
        )
    else:
        if monitored is not None:
            await conn.execute(
                """
                UPDATE anime_episodes SET monitored = $1, updated_at = NOW()
                WHERE anime_id = $2 AND episode_number = $3
                """,
                monitored, anime_id, episode_number
            )

    updated = await conn.fetchrow(
        "SELECT * FROM anime_episodes WHERE anime_id = $1 AND episode_number = $2",
        anime_id, episode_number
    )
    return dict(updated) if updated else {"anime_id": anime_id, "episode_number": episode_number, "monitored": monitored}
