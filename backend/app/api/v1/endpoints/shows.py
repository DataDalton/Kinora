from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncpg
import os
import shutil
import json

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services.metadata.tmdb import tmdb_service

router = APIRouter()


class ShowCreate(BaseModel):
    tmdb_id: int
    monitored: bool = True
    media_profile_id: Optional[int] = None
    season_monitoring: str = "all"


class MonitoringUpdate(BaseModel):
    monitored: Optional[bool] = None
    upgradeAllowed: Optional[bool] = None
    seasonMonitoring: Optional[str] = None


class SeasonMonitoringUpdate(BaseModel):
    monitored: bool


class EpisodeMonitoringUpdate(BaseModel):
    monitored: bool


@router.get("/")
async def get_shows(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    monitored: Optional[bool] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all TV shows from library with pagination, filtering, and tags
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
    shows = [dict(row) for row in rows]

    if shows:
        show_ids = [s["id"] for s in shows]
        tags_query = """
            SELECT mt.media_id, t.id, t.name, t.color
            FROM media_tags mt
            JOIN tags t ON t.id = mt.tag_id
            WHERE mt.media_type = 'show' AND mt.media_id = ANY($1)
        """
        tag_rows = await conn.fetch(tags_query, show_ids)

        tags_by_show = {}
        for row in tag_rows:
            show_id = row["media_id"]
            if show_id not in tags_by_show:
                tags_by_show[show_id] = []
            tags_by_show[show_id].append({
                "id": row["id"],
                "name": row["name"],
                "color": row["color"],
            })

        for show in shows:
            show["tags"] = tags_by_show.get(show["id"], [])

    return {
        "shows": shows,
        "page": page,
        "limit": limit,
    }


@router.get("/{show_id}")
async def get_show(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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


@router.put("/{show_id}/monitoring")
async def update_show_monitoring(
    show_id: int,
    data: MonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update show monitoring settings
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    # Use exclude_unset to distinguish between "not sent" and "explicitly set to null"
    sent_fields = data.model_dump(exclude_unset=True)

    update_fields = []
    values = []
    param_count = 1

    if "monitored" in sent_fields:
        update_fields.append(f"monitored = ${param_count}")
        values.append(data.monitored)
        param_count += 1

    if "upgradeAllowed" in sent_fields:
        update_fields.append(f"upgrade_allowed = ${param_count}")
        values.append(data.upgradeAllowed)
        param_count += 1

    if "seasonMonitoring" in sent_fields:
        update_fields.append(f"season_monitoring = ${param_count}")
        values.append(data.seasonMonitoring)
        param_count += 1

    if not update_fields:
        return {"message": "No updates provided"}

    values.append(show_id)
    query = f"""
        UPDATE shows
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return dict(row)


@router.delete("/{show_id}/delete")
async def delete_show_with_files(
    show_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Delete show from library with option to delete files from disk
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    files_deleted = []
    errors = []

    if delete_files and show.get("root_folder_path"):
        folder_path = show["root_folder_path"]
        try:
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                files_deleted.append(folder_path)
        except Exception as e:
            errors.append(f"Failed to delete {folder_path}: {str(e)}")

    await conn.execute("DELETE FROM episodes WHERE show_id = $1", show_id)
    await conn.execute("DELETE FROM seasons WHERE show_id = $1", show_id)
    await conn.execute("DELETE FROM download_history WHERE media_type = 'show' AND media_id = $1", show_id)
    await conn.execute("DELETE FROM blocklist WHERE media_type = 'show' AND media_id = $1", show_id)
    await conn.execute("DELETE FROM media_tags WHERE media_type = 'show' AND media_id = $1", show_id)
    await conn.execute("DELETE FROM shows WHERE id = $1", show_id)

    return {
        "message": "Show deleted successfully",
        "files_deleted": files_deleted,
        "errors": errors,
    }


@router.post("/{show_id}/refresh-metadata")
async def refresh_show_metadata(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Refresh show metadata from TMDB
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    if not show["tmdb_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Show has no TMDB ID, cannot refresh metadata",
        )

    try:
        tmdb_data = await tmdb_service.get_tv(show["tmdb_id"])
        parsed_data = tmdb_service.parse_tv_data(tmdb_data)

        await conn.execute(
            """
            UPDATE shows SET
                title = $1, original_title = $2, overview = $3, poster_path = $4,
                backdrop_path = $5, release_date = $6, genres = $7, rating = $8,
                vote_count = $9, popularity = $10, imdb_id = $11, tvdb_id = $12,
                number_of_seasons = $13, number_of_episodes = $14, episode_run_time = $15,
                networks = $16, production_companies = $17, first_air_date = $18,
                last_air_date = $19, in_production = $20, updated_at = NOW()
            WHERE id = $21
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
            parsed_data["tvdb_id"],
            parsed_data["number_of_seasons"],
            parsed_data["number_of_episodes"],
            parsed_data["episode_run_time"],
            parsed_data["networks"],
            parsed_data["production_companies"],
            parsed_data["first_air_date"],
            parsed_data["last_air_date"],
            parsed_data["in_production"],
            show_id,
        )

        updated = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
        return dict(updated)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh metadata: {str(e)}",
        )


@router.post("/{show_id}/rescan")
async def rescan_show_files(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Rescan show files on disk and update database
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    folder_path = show.get("root_folder_path")
    file_count = 0

    if folder_path and os.path.isdir(folder_path):
        video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(video_extensions):
                    file_count += 1

    updated = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    return {**dict(updated), "files_found": file_count}


@router.get("/{show_id}/credits")
async def get_show_credits(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get show cast and crew from TMDB
    """
    show = await conn.fetchrow("SELECT tmdb_id FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    if not show["tmdb_id"]:
        return {"cast": [], "crew": []}

    try:
        tmdb_data = await tmdb_service.get_tv(show["tmdb_id"])
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
            if person.get("job") in ["Creator", "Director", "Writer", "Executive Producer", "Producer"]
        ]

        return {"cast": cast, "crew": crew}

    except Exception as e:
        return {"cast": [], "crew": [], "error": str(e)}


@router.get("/{show_id}/seasons")
async def get_show_seasons(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get seasons for a show
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    seasons = await conn.fetch(
        """
        SELECT * FROM seasons
        WHERE show_id = $1
        ORDER BY season_number
        """,
        show_id,
    )

    if not seasons and show["tmdb_id"]:
        try:
            tmdb_data = await tmdb_service.get_tv(show["tmdb_id"])
            tmdb_seasons = tmdb_data.get("seasons", [])

            for s in tmdb_seasons:
                if s.get("season_number", 0) > 0:
                    await conn.execute(
                        """
                        INSERT INTO seasons (show_id, season_number, title, overview, poster_path, air_date, episode_count, monitored)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (show_id, season_number) DO NOTHING
                        """,
                        show_id,
                        s.get("season_number"),
                        s.get("name"),
                        s.get("overview"),
                        s.get("poster_path"),
                        tmdb_service._parse_date(s.get("air_date")),
                        s.get("episode_count"),
                        True,
                    )

            seasons = await conn.fetch(
                "SELECT * FROM seasons WHERE show_id = $1 ORDER BY season_number",
                show_id,
            )
        except Exception:
            pass

    return {"seasons": [dict(s) for s in seasons], "total_seasons": show["number_of_seasons"]}


@router.get("/{show_id}/seasons/{season_number}/episodes")
async def get_season_episodes(
    show_id: int,
    season_number: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get episodes for a specific season
    """
    show = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    episodes = await conn.fetch(
        """
        SELECT * FROM episodes
        WHERE show_id = $1 AND season_number = $2
        ORDER BY episode_number
        """,
        show_id, season_number,
    )

    if not episodes and show["tmdb_id"]:
        try:
            season_data = await tmdb_service.get_tv_season(show["tmdb_id"], season_number)
            tmdb_episodes = season_data.get("episodes", [])

            for ep in tmdb_episodes:
                await conn.execute(
                    """
                    INSERT INTO episodes (show_id, season_number, episode_number, title, overview, still_path, air_date, runtime, monitored)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (show_id, season_number, episode_number) DO NOTHING
                    """,
                    show_id,
                    season_number,
                    ep.get("episode_number"),
                    ep.get("name"),
                    ep.get("overview"),
                    ep.get("still_path"),
                    tmdb_service._parse_date(ep.get("air_date")),
                    ep.get("runtime"),
                    True,
                )

            episodes = await conn.fetch(
                "SELECT * FROM episodes WHERE show_id = $1 AND season_number = $2 ORDER BY episode_number",
                show_id, season_number,
            )
        except Exception:
            pass

    return {"episodes": [dict(ep) for ep in episodes], "season_number": season_number}


@router.put("/{show_id}/seasons/{season_number}")
async def update_season_monitoring(
    show_id: int,
    season_number: int,
    data: SeasonMonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update monitoring status for a season
    """
    show = await conn.fetchrow("SELECT id FROM shows WHERE id = $1", show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    await conn.execute(
        """
        UPDATE seasons SET monitored = $1, updated_at = NOW()
        WHERE show_id = $2 AND season_number = $3
        """,
        data.monitored, show_id, season_number,
    )

    await conn.execute(
        """
        UPDATE episodes SET monitored = $1, updated_at = NOW()
        WHERE show_id = $2 AND season_number = $3
        """,
        data.monitored, show_id, season_number,
    )

    season = await conn.fetchrow(
        "SELECT * FROM seasons WHERE show_id = $1 AND season_number = $2",
        show_id, season_number,
    )

    return dict(season) if season else {"message": "Season updated"}


@router.put("/{show_id}/episodes/{episode_id}")
async def update_episode_monitoring(
    show_id: int,
    episode_id: int,
    data: EpisodeMonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update monitoring status for a single episode
    """
    episode = await conn.fetchrow(
        "SELECT * FROM episodes WHERE id = $1 AND show_id = $2",
        episode_id, show_id,
    )

    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not found",
        )

    await conn.execute(
        """
        UPDATE episodes SET monitored = $1, updated_at = NOW()
        WHERE id = $2
        """,
        data.monitored, episode_id,
    )

    updated = await conn.fetchrow("SELECT * FROM episodes WHERE id = $1", episode_id)
    return dict(updated)
