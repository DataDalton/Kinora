from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncpg
import os
import shutil

from app.db import get_db
from app.db.repositories import ShowRepository, SeasonRepository, EpisodeRepository
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
    """Get all TV shows from library with pagination, filtering, and tags (single query)."""
    offset = (page - 1) * limit

    # Build WHERE clause
    conditions = []
    params = []
    paramCount = 1

    if status:
        conditions.append(f"s.status = ${paramCount}")
        params.append(status)
        paramCount += 1

    if monitored is not None:
        conditions.append(f"s.monitored = ${paramCount}")
        params.append(monitored)
        paramCount += 1

    whereClause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Single query with JSON aggregation for tags
    query = f"""
        SELECT s.*,
               COALESCE(
                   json_agg(
                       json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                   ) FILTER (WHERE t.id IS NOT NULL),
                   '[]'::json
               ) as tags
        FROM shows s
        LEFT JOIN media_tags mt ON s.id = mt.media_id AND mt.media_type = 'show'
        LEFT JOIN tags t ON mt.tag_id = t.id
        {whereClause}
        GROUP BY s.id
        ORDER BY s.title
        LIMIT ${paramCount} OFFSET ${paramCount + 1}
    """
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    shows = [dict(row) for row in rows]

    return {"shows": shows, "page": page, "limit": limit}


@router.get("/{show_id}")
async def get_show(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get a specific TV show by ID."""
    repo = ShowRepository(conn)
    show = await repo.getById(show_id)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    return show


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_show(
    show_data: ShowCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Add a TV show to library."""
    repo = ShowRepository(conn)

    if await repo.existsByTmdbId(show_data.tmdb_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Show already exists in library",
        )

    metadata = await tmdb_service.get_tv(show_data.tmdb_id)
    parsedData = tmdb_service.parse_tv_data(metadata)

    showData = {
        **parsedData,
        "status": "wanted",
        "monitored": show_data.monitored,
        "media_profile_id": show_data.media_profile_id,
        "season_monitoring": show_data.season_monitoring,
    }

    return await repo.create(showData)


@router.put("/{show_id}")
async def update_show(
    show_id: int,
    updates: dict,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update TV show in library."""
    repo = ShowRepository(conn)
    show = await repo.update(show_id, updates)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    return show


@router.delete("/{show_id}")
async def delete_show(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Remove TV show from library."""
    repo = ShowRepository(conn)
    deleted = await repo.delete(show_id)

    if not deleted:
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
    """Update show monitoring settings. Cascades monitored status to all seasons and episodes."""
    repo = ShowRepository(conn)

    sentFields = data.model_dump(exclude_unset=True)
    updateData = {}

    if "monitored" in sentFields:
        updateData["monitored"] = data.monitored
    if "upgradeAllowed" in sentFields:
        updateData["upgrade_allowed"] = data.upgradeAllowed
    if "seasonMonitoring" in sentFields:
        updateData["season_monitoring"] = data.seasonMonitoring

    if not updateData:
        return {"message": "No updates provided"}

    show = await repo.update(show_id, updateData)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    # Cascade monitored status to all seasons and episodes
    if "monitored" in sentFields:
        await conn.execute(
            "UPDATE seasons SET monitored = $2, updated_at = NOW() WHERE show_id = $1",
            show_id, data.monitored
        )
        await conn.execute(
            "UPDATE episodes SET monitored = $2, updated_at = NOW() WHERE show_id = $1",
            show_id, data.monitored
        )

    return show


@router.delete("/{show_id}/delete")
async def delete_show_with_files(
    show_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Delete show from library with option to delete files from disk."""
    repo = ShowRepository(conn)
    show = await repo.getById(show_id)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    filesDeleted = []
    errors = []

    if delete_files and show.get("root_folder_path"):
        folderPath = show["root_folder_path"]
        try:
            if os.path.isdir(folderPath):
                shutil.rmtree(folderPath)
                filesDeleted.append(folderPath)
        except Exception as e:
            errors.append(f"Failed to delete {folderPath}: {str(e)}")

    # Delete episodes and seasons first (cascading), then use repo for relations
    await conn.execute("DELETE FROM episodes WHERE show_id = $1", show_id)
    await conn.execute("DELETE FROM seasons WHERE show_id = $1", show_id)
    await repo.deleteWithRelations(show_id)

    return {
        "message": "Show deleted successfully",
        "files_deleted": filesDeleted,
        "errors": errors,
    }


@router.post("/{show_id}/refresh-metadata")
async def refresh_show_metadata(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Refresh show metadata from TMDB."""
    repo = ShowRepository(conn)
    show = await repo.getById(show_id)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    if not show.get("tmdb_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Show has no TMDB ID, cannot refresh metadata",
        )

    try:
        tmdbData = await tmdb_service.get_tv(show["tmdb_id"])
        parsedData = tmdb_service.parse_tv_data(tmdbData)
        return await repo.update(show_id, parsedData)

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
    """Rescan show files on disk and update database."""
    repo = ShowRepository(conn)
    show = await repo.getById(show_id)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    folderPath = show.get("root_folder_path")
    fileCount = 0

    if folderPath and os.path.isdir(folderPath):
        videoExtensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
        for root, dirs, files in os.walk(folderPath):
            for f in files:
                if f.lower().endswith(videoExtensions):
                    fileCount += 1

    return {**show, "files_found": fileCount}


@router.get("/{show_id}/credits")
async def get_show_credits(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get show cast and crew from TMDB."""
    repo = ShowRepository(conn)
    show = await repo.getById(show_id)

    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    if not show.get("tmdb_id"):
        return {"cast": [], "crew": []}

    try:
        tmdbData = await tmdb_service.get_tv(show["tmdb_id"])
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

        crewJobs = ["Creator", "Director", "Writer", "Executive Producer", "Producer"]
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


@router.get("/{show_id}/seasons")
async def get_show_seasons(
    show_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get seasons for a show."""
    showRepo = ShowRepository(conn)
    seasonRepo = SeasonRepository(conn)

    show = await showRepo.getById(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    seasons = await seasonRepo.getByShowId(show_id)

    # Fetch from TMDB if no seasons in DB
    if not seasons and show.get("tmdb_id"):
        try:
            tmdbData = await tmdb_service.get_tv(show["tmdb_id"])
            tmdbSeasons = tmdbData.get("seasons", [])

            for s in tmdbSeasons:
                if s.get("season_number", 0) > 0:
                    await seasonRepo.upsert(show_id, s.get("season_number"), {
                        "title": s.get("name"),
                        "overview": s.get("overview"),
                        "poster_path": s.get("poster_path"),
                        "air_date": tmdb_service._parse_date(s.get("air_date")),
                        "episode_count": s.get("episode_count"),
                        "monitored": True,
                    })

            seasons = await seasonRepo.getByShowId(show_id)
        except Exception:
            pass

    return {"seasons": seasons, "total_seasons": show.get("number_of_seasons", 0)}


@router.get("/{show_id}/seasons/{season_number}/episodes")
async def get_season_episodes(
    show_id: int,
    season_number: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get episodes for a specific season."""
    showRepo = ShowRepository(conn)
    episodeRepo = EpisodeRepository(conn)

    show = await showRepo.getById(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    # Get episodes for this season from our DB
    allEpisodes = await episodeRepo.getByShowId(show_id)
    episodes = [ep for ep in allEpisodes if ep.get("season_number") == season_number]

    # Fetch from TMDB if no episodes in DB
    if not episodes and show.get("tmdb_id"):
        try:
            seasonData = await tmdb_service.get_tv_season(show["tmdb_id"], season_number)
            tmdbEpisodes = seasonData.get("episodes", [])

            for ep in tmdbEpisodes:
                await episodeRepo.upsert(show_id, season_number, ep.get("episode_number"), {
                    "title": ep.get("name"),
                    "overview": ep.get("overview"),
                    "still_path": ep.get("still_path"),
                    "air_date": tmdb_service._parse_date(ep.get("air_date")),
                    "runtime": ep.get("runtime"),
                    "monitored": True,
                    "has_file": False,
                })

            allEpisodes = await episodeRepo.getByShowId(show_id)
            episodes = [ep for ep in allEpisodes if ep.get("season_number") == season_number]
        except Exception as e:
            print(f"Error fetching episodes from TMDB: {e}")

    return {"episodes": episodes, "season_number": season_number}


@router.put("/{show_id}/seasons/{season_number}")
async def update_season_monitoring(
    show_id: int,
    season_number: int,
    data: SeasonMonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update monitoring status for a season."""
    showRepo = ShowRepository(conn)
    seasonRepo = SeasonRepository(conn)

    show = await showRepo.getById(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Show not found",
        )

    # Update season and its episodes in bulk
    await conn.execute(
        "UPDATE seasons SET monitored = $1, updated_at = NOW() WHERE show_id = $2 AND season_number = $3",
        data.monitored, show_id, season_number,
    )
    await conn.execute(
        "UPDATE episodes SET monitored = $1, updated_at = NOW() WHERE show_id = $2 AND season_number = $3",
        data.monitored, show_id, season_number,
    )

    season = await seasonRepo.getByShowAndNumber(show_id, season_number)
    return season if season else {"message": "Season updated"}


@router.put("/{show_id}/episodes/{episode_id}")
async def update_episode_monitoring(
    show_id: int,
    episode_id: int,
    data: EpisodeMonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update monitoring status for a single episode."""
    episodeRepo = EpisodeRepository(conn)
    episode = await episodeRepo.getById(episode_id)

    if not episode or episode.get("show_id") != show_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not found",
        )

    await conn.execute(
        "UPDATE episodes SET monitored = $1, updated_at = NOW() WHERE id = $2",
        data.monitored, episode_id,
    )

    return await episodeRepo.getById(episode_id)
