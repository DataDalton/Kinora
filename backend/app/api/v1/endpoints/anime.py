from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncpg
import os
import shutil
import json

from app.db import get_db
from app.db.repositories import AnimeRepository, AnimeEpisodeRepository
from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.schemas.user import UserWithPermissions
from app.services.metadata.anilist import anilist_service
from app.core.permissions import userHasPermission

router = APIRouter()


class AnimeCreate(BaseModel):
    anilist_id: int
    monitored: bool = True
    media_profile_id: Optional[int] = None
    episode_monitoring: str = "all"
    add_sequels: bool = True  # Auto-add all sequel seasons


class AnimeMonitoringUpdate(BaseModel):
    monitored: Optional[bool] = None
    upgradeAllowed: Optional[bool] = None
    episodeMonitoring: Optional[str] = None


@router.get("/")
async def get_anime(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    monitored: Optional[bool] = None,
    grouped: bool = True,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.view")),
):
    """Get all anime from library with pagination, filtering, and tags.

    When grouped=True (default), returns one entry per series with season count.
    When grouped=False, returns all anime entries individually.
    """
    offset = (page - 1) * limit

    # Build WHERE clause
    conditions = []
    params = []
    paramCount = 1

    if status:
        conditions.append(f"a.status = ${paramCount}")
        params.append(status)
        paramCount += 1

    if monitored is not None:
        conditions.append(f"a.monitored = ${paramCount}")
        params.append(monitored)
        paramCount += 1

    # When grouped, only show series parent entries (season_order = 1 or no series)
    if grouped:
        conditions.append(f"(a.season_order = 1 OR a.season_order IS NULL)")

    whereClause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Query with JSON aggregation for tags and season count
    query = f"""
        SELECT a.*,
               COALESCE(
                   json_agg(
                       json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                   ) FILTER (WHERE t.id IS NOT NULL),
                   '[]'::json
               ) as tags,
               (SELECT COUNT(*) FROM anime a2 WHERE a2.series_id = a.id) as season_count
        FROM anime a
        LEFT JOIN media_tags mt ON a.id = mt.media_id AND mt.media_type = 'anime'
        LEFT JOIN tags t ON mt.tag_id = t.id
        {whereClause}
        GROUP BY a.id
        ORDER BY a.title
        LIMIT ${paramCount} OFFSET ${paramCount + 1}
    """
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    animeList = []
    for row in rows:
        anime = dict(row)
        # Ensure season_count is at least 1 (for standalone anime with no series)
        anime["season_count"] = max(1, anime.get("season_count") or 1)
        animeList.append(anime)

    return {"anime": animeList, "page": page, "limit": limit}


@router.get("/{anime_id}")
async def get_anime_by_id(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.view")),
):
    """Get a specific anime by ID."""
    repo = AnimeRepository(conn)
    anime = await repo.getById(anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    return anime


@router.get("/{anime_id}/seasons")
async def get_anime_seasons(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.view")),
):
    """Get all seasons (related anime entries) for a series.

    Returns all anime that share the same series_id, ordered by season_order.
    Similar to how shows have seasons, this returns all entries in an anime series.
    """
    # First, get the anime to find its series_id
    anime = await conn.fetchrow("SELECT id, series_id, title FROM anime WHERE id = $1", anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    # Determine series_id - if this anime has a series_id, use it; otherwise use its own id
    seriesId = anime["series_id"] or anime["id"]

    # Get all anime in this series
    rows = await conn.fetch(
        """
        SELECT id, title, original_title, poster_path, backdrop_path, release_date,
               season_year, season_period, season_order, episodes, status, monitored,
               has_file, anilist_id, rating
        FROM anime
        WHERE series_id = $1 OR (id = $1 AND series_id IS NULL)
        ORDER BY season_order NULLS LAST, season_year NULLS LAST, title
        """,
        seriesId
    )

    seasons = [dict(row) for row in rows]

    return {
        "seasons": seasons,
        "total_seasons": len(seasons),
        "series_title": anime["title"].split(" Season")[0].split(" Part")[0].strip()  # Base title without "Season X"
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_anime(
    anime_data: AnimeCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Add an anime to library. Auto-adds all related seasons (sequels/prequels) by default.

    If user has anime.download permission, adds directly.
    If user only has anime.request permission, creates a request for approval.
    """
    repo = AnimeRepository(conn)

    # Check if user can add directly (has download permission) or needs to create request
    canDownload = await userHasPermission(conn, current_user.id, "anime.download")

    # Fetch metadata from AniList
    metadata = await anilist_service.get_anime(anime_data.anilist_id)
    parsedData = anilist_service.parse_anime_data(metadata)

    if canDownload:
        # User can add directly
        if await repo.existsByAnilistId(anime_data.anilist_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Anime already exists in library",
            )

        animeData = {
            **parsedData,
            "status": "wanted",
            "monitored": anime_data.monitored,
            "media_profile_id": anime_data.media_profile_id,
            "absolute_numbering": True,
            "has_file": False,
            "episode_monitoring": anime_data.episode_monitoring,
        }

        mainAnime = await repo.create(animeData)
        addedAnime = [(mainAnime, parsedData.get("season_year") or 9999)]

        # Auto-add related seasons (sequels and prequels)
        if anime_data.add_sequels:
            relatedSeasons = await anilist_service.get_all_related_seasons(anime_data.anilist_id)

            for related in relatedSeasons:
                # Skip if already in library
                if await repo.existsByAnilistId(related["anilist_id"]):
                    # Link existing anime to series if not already linked
                    existingAnime = await conn.fetchrow(
                        "SELECT id, series_id FROM anime WHERE anilist_id = $1",
                        related["anilist_id"]
                    )
                    if existingAnime and not existingAnime["series_id"]:
                        addedAnime.append((dict(existingAnime), related.get("season_year") or 9999))
                    continue

                try:
                    relatedMetadata = await anilist_service.get_anime(related["anilist_id"])
                    relatedParsed = anilist_service.parse_anime_data(relatedMetadata)

                    relatedData = {
                        **relatedParsed,
                        "status": "wanted",
                        "monitored": anime_data.monitored,
                        "media_profile_id": anime_data.media_profile_id,
                        "absolute_numbering": True,
                        "has_file": False,
                        "episode_monitoring": anime_data.episode_monitoring,
                    }

                    addedRelated = await repo.create(relatedData)
                    addedAnime.append((addedRelated, relatedParsed.get("season_year") or 9999))
                except Exception as e:
                    print(f"Failed to add related anime {related['anilist_id']}: {e}")

        # Sort by season_year to determine order, then assign series_id and season_order
        addedAnime.sort(key=lambda x: x[1])

        # The earliest anime becomes the series parent
        seriesParentId = addedAnime[0][0]["id"]

        # Update all anime in the series with series_id and season_order
        for idx, (anime, _) in enumerate(addedAnime):
            await conn.execute(
                "UPDATE anime SET series_id = $1, season_order = $2, updated_at = NOW() WHERE id = $3",
                seriesParentId, idx + 1, anime["id"]
            )

        # Refresh the main anime to get updated fields
        mainAnime = await repo.getById(mainAnime["id"])

        # Return main anime with count of added entries
        return {
            **mainAnime,
            "related_added": len(addedAnime) - 1,
            "total_added": len(addedAnime),
        }
    else:
        # User needs to create a request for approval
        existingRequest = await conn.fetchrow(
            """
            SELECT id FROM media_requests
            WHERE media_type = 'anime' AND external_id = $1 AND user_id = $2 AND status = 'pending'
            """,
            anime_data.anilist_id,
            current_user.id,
        )

        if existingRequest:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A request for this anime is already pending",
            )

        # Check if anime already exists
        if await repo.existsByAnilistId(anime_data.anilist_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Anime already exists in library",
            )

        # Create a media request
        request_row = await conn.fetchrow(
            """
            INSERT INTO media_requests (user_id, media_type, external_id, title, poster_path, year, overview, metadata, status)
            VALUES ($1, 'anime', $2, $3, $4, $5, $6, $7, 'pending')
            RETURNING id, status, requested_at
            """,
            current_user.id,
            anime_data.anilist_id,
            parsedData.get("title"),
            parsedData.get("poster_path"),
            parsedData.get("season_year"),
            parsedData.get("overview"),
            json.dumps({
                "monitored": anime_data.monitored,
                "media_profile_id": anime_data.media_profile_id,
                "episode_monitoring": anime_data.episode_monitoring,
                "add_sequels": anime_data.add_sequels,
            }),
        )

        return {
            "request_id": request_row["id"],
            "status": "pending",
            "message": "Anime request submitted for approval",
            "title": parsedData.get("title"),
            "requested_at": request_row["requested_at"],
        }


@router.put("/{anime_id}")
async def update_anime(
    anime_id: int,
    updates: dict,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Update anime in library."""
    repo = AnimeRepository(conn)
    anime = await repo.update(anime_id, updates)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    return anime


@router.delete("/{anime_id}")
async def delete_anime(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Remove anime from library."""
    repo = AnimeRepository(conn)
    deleted = await repo.delete(anime_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )

    return {"message": "Anime removed from library successfully"}


@router.put("/{anime_id}/monitoring")
async def update_anime_monitoring(
    anime_id: int,
    data: AnimeMonitoringUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Update anime monitoring settings. Cascades monitored status to all episodes."""
    repo = AnimeRepository(conn)

    sentFields = data.model_dump(exclude_unset=True)
    updateData = {}

    if "monitored" in sentFields:
        updateData["monitored"] = data.monitored
    if "upgradeAllowed" in sentFields:
        updateData["upgrade_allowed"] = data.upgradeAllowed
    if "episodeMonitoring" in sentFields:
        updateData["episode_monitoring"] = data.episodeMonitoring

    if not updateData:
        return {"message": "No updates provided"}

    anime = await repo.update(anime_id, updateData)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    # Cascade monitored status to all episodes
    if "monitored" in sentFields:
        await conn.execute(
            "UPDATE anime_episodes SET monitored = $2, updated_at = NOW() WHERE anime_id = $1",
            anime_id, data.monitored
        )

    return anime


@router.delete("/{anime_id}/delete")
async def delete_anime_with_files(
    anime_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Delete anime from library with option to delete files from disk."""
    repo = AnimeRepository(conn)
    anime = await repo.getById(anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    filesDeleted = []
    errors = []

    if delete_files and anime.get("root_folder_path"):
        folderPath = anime["root_folder_path"]
        try:
            if os.path.isdir(folderPath):
                shutil.rmtree(folderPath)
                filesDeleted.append(folderPath)
        except Exception as e:
            errors.append(f"Failed to delete {folderPath}: {str(e)}")

    # Delete episodes first, then use repo for relations
    await conn.execute("DELETE FROM anime_episodes WHERE anime_id = $1", anime_id)
    await repo.deleteWithRelations(anime_id)

    return {
        "message": "Anime deleted successfully",
        "files_deleted": filesDeleted,
        "errors": errors,
    }


@router.post("/{anime_id}/refresh-metadata")
async def refresh_anime_metadata(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("anime.manage")),
):
    """Refresh anime metadata from AniList."""
    repo = AnimeRepository(conn)
    anime = await repo.getById(anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    if not anime.get("anilist_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anime has no AniList ID, cannot refresh metadata",
        )

    try:
        anilistData = await anilist_service.get_anime(anime["anilist_id"])
        parsedData = anilist_service.parse_anime_data(anilistData)
        return await repo.update(anime_id, parsedData)

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
    """Rescan anime files on disk and update database."""
    repo = AnimeRepository(conn)
    anime = await repo.getById(anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    folderPath = anime.get("root_folder_path")
    hasFile = False
    fileCount = 0

    if folderPath and os.path.isdir(folderPath):
        videoExtensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v')
        for root, dirs, files in os.walk(folderPath):
            for f in files:
                if f.lower().endswith(videoExtensions):
                    hasFile = True
                    fileCount += 1

    updated = await repo.update(anime_id, {"has_file": hasFile})
    return {**updated, "files_found": fileCount}


@router.get("/{anime_id}/credits")
async def get_anime_credits(
    anime_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get anime characters and staff from AniList."""
    repo = AnimeRepository(conn)
    anime = await repo.getById(anime_id)

    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    if not anime.get("anilist_id"):
        return {"characters": [], "staff": []}

    try:
        anilistData = await anilist_service.get_anime(anime["anilist_id"])

        characters = [
            {
                "id": char.get("id"),
                "name": char.get("name", {}).get("full"),
                "image": char.get("image", {}).get("large"),
            }
            for char in anilistData.get("characters", {}).get("nodes", [])
        ]

        staff = [
            {
                "id": person.get("id"),
                "name": person.get("name", {}).get("full"),
                "role": ", ".join(person.get("primaryOccupations", [])) if person.get("primaryOccupations") else "Staff",
            }
            for person in anilistData.get("staff", {}).get("nodes", [])
        ]

        studios = [
            studio.get("name")
            for studio in anilistData.get("studios", {}).get("nodes", [])
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
    """Get episodes for an anime."""
    animeRepo = AnimeRepository(conn)
    episodeRepo = AnimeEpisodeRepository(conn)

    anime = await animeRepo.getById(anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    episodes = await episodeRepo.getByAnimeId(anime_id)

    return {
        "episodes": episodes,
        "total_episodes": anime.get("episodes"),
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
    """Update a specific episode's monitoring status."""
    animeRepo = AnimeRepository(conn)
    episodeRepo = AnimeEpisodeRepository(conn)

    anime = await animeRepo.getById(anime_id)
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anime not found",
        )

    episode = await episodeRepo.getByAnimeAndNumber(anime_id, episode_number)

    if not episode:
        # Create new episode entry
        return await episodeRepo.upsert(anime_id, episode_number, {
            "monitored": monitored if monitored is not None else True
        })
    elif monitored is not None:
        # Update existing episode
        return await episodeRepo.upsert(anime_id, episode_number, {
            "monitored": monitored
        })

    return episode
