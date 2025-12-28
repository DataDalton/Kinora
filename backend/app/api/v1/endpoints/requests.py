from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import asyncpg

from app.db import get_db
from app.db.repositories import MovieRepository, ShowRepository, AnimeRepository, AlbumRepository
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.schemas.request import (
    MediaRequestCreate, MediaRequestResponse,
    MediaRequestReview, MediaRequestCount
)
from app.core.permissions import userHasPermission, getUserPermissions
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service

router = APIRouter()


async def canRequestMediaType(conn: asyncpg.Connection, userId: int, mediaType: str) -> bool:
    """Check if user has request permission for specific media type"""
    permissionMap = {
        "movie": "movies.request",
        "show": "shows.request",
        "anime": "anime.request",
        "album": "music.request",
        "music": "music.request",
    }

    permission = permissionMap.get(mediaType)
    if not permission:
        return False

    return await userHasPermission(conn, userId, permission)


async def canApproveMediaType(conn: asyncpg.Connection, userId: int, mediaType: str) -> bool:
    """Check if user has approval permission for specific media type"""
    # Map media types to their approval permissions
    permissionMap = {
        "movie": "movies.approve",
        "show": "shows.approve",
        "anime": "anime.approve",
        "album": "music.approve",
        "music": "music.approve",
    }

    permission = permissionMap.get(mediaType)
    if not permission:
        return False

    # Check both specific permission and requests.manage (global approve)
    hasSpecific = await userHasPermission(conn, userId, permission)
    hasManage = await userHasPermission(conn, userId, "requests.manage")
    return hasSpecific or hasManage


async def canApprove(conn: asyncpg.Connection, userId: int) -> bool:
    """Check if user has any approval permission"""
    userPerms = await getUserPermissions(conn, userId)
    approvePerms = ["movies.approve", "shows.approve", "anime.approve", "music.approve", "requests.manage"]
    return any(p in userPerms for p in approvePerms)


def formatRequestResponse(row: dict) -> MediaRequestResponse:
    """Format a database row into a MediaRequestResponse"""
    return MediaRequestResponse(
        id=row["id"],
        user_id=row["user_id"],
        username=row.get("username", ""),
        media_type=row["media_type"],
        external_id=row["external_id"],
        title=row["title"],
        poster_path=row.get("poster_path"),
        year=row.get("year"),
        overview=row.get("overview"),
        status=row["status"],
        request_notes=row.get("request_notes"),
        requested_at=row["requested_at"],
        reviewed_at=row.get("reviewed_at"),
        reviewed_by=row.get("reviewed_by"),
        reviewer_username=row.get("reviewer_username"),
        review_notes=row.get("review_notes"),
        created_media_id=row.get("created_media_id")
    )


@router.get("/", response_model=List[MediaRequestResponse])
async def list_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List media requests.
    Users see their own requests.
    Users with requests.approve permission see all pending requests.
    """
    hasApprovePermission = await canApprove(conn, current_user.id)

    # Build query based on user permissions
    conditions = []
    params = []
    paramCount = 1

    if hasApprovePermission:
        # Approvers can see: their own requests OR all pending requests
        conditions.append(f"(mr.user_id = ${paramCount} OR mr.status = 'pending')")
        params.append(current_user.id)
        paramCount += 1
    else:
        # Regular users can only see their own requests
        conditions.append(f"mr.user_id = ${paramCount}")
        params.append(current_user.id)
        paramCount += 1

    # Add status filter
    if status_filter:
        conditions.append(f"mr.status = ${paramCount}")
        params.append(status_filter)
        paramCount += 1

    whereClause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await conn.fetch(
        f"""
        SELECT mr.*,
               requester.username as username,
               reviewer.username as reviewer_username
        FROM media_requests mr
        LEFT JOIN users requester ON mr.user_id = requester.id
        LEFT JOIN users reviewer ON mr.reviewed_by = reviewer.id
        {whereClause}
        ORDER BY mr.requested_at DESC
        """,
        *params
    )

    return [formatRequestResponse(dict(row)) for row in rows]


@router.post("/", response_model=MediaRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    request_data: MediaRequestCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new media request.
    Requires type-specific request permission (e.g., movies.request).
    Checks for duplicate pending requests.
    """
    # Verify user has permission to request this media type
    hasRequestPermission = await canRequestMediaType(conn, current_user.id, request_data.mediaType)
    if not hasRequestPermission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to request {request_data.mediaType} media"
        )

    # Check for duplicate pending request
    existing = await conn.fetchrow(
        """
        SELECT id FROM media_requests
        WHERE media_type = $1 AND external_id = $2 AND status = 'pending'
        """,
        request_data.mediaType,
        request_data.externalId
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending request for this media already exists"
        )

    # Create the request
    row = await conn.fetchrow(
        """
        INSERT INTO media_requests (
            user_id, media_type, external_id, title, poster_path, year, overview,
            metadata, request_notes, media_profile_id, root_folder_id, auto_search, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'pending')
        RETURNING *
        """,
        current_user.id,
        request_data.mediaType,
        request_data.externalId,
        request_data.title,
        request_data.posterPath,
        request_data.year,
        request_data.overview,
        request_data.metadata,
        request_data.requestNotes,
        request_data.mediaProfileId,
        request_data.rootFolderId,
        request_data.autoSearch
    )

    # Fetch with username
    result = await conn.fetchrow(
        """
        SELECT mr.*, u.username
        FROM media_requests mr
        LEFT JOIN users u ON mr.user_id = u.id
        WHERE mr.id = $1
        """,
        row["id"]
    )

    return formatRequestResponse(dict(result))


@router.get("/count", response_model=MediaRequestCount)
async def get_request_counts(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get request counts by status for requests the user can see.
    """
    hasApprovePermission = await canApprove(conn, current_user.id)

    if hasApprovePermission:
        # Approvers can see: their own requests OR all pending requests
        counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'denied') as denied,
                COUNT(*) as total
            FROM media_requests
            WHERE user_id = $1 OR status = 'pending'
            """,
            current_user.id
        )
    else:
        # Regular users can only see their own requests
        counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'denied') as denied,
                COUNT(*) as total
            FROM media_requests
            WHERE user_id = $1
            """,
            current_user.id
        )

    return MediaRequestCount(
        pending=counts["pending"] or 0,
        approved=counts["approved"] or 0,
        denied=counts["denied"] or 0,
        total=counts["total"] or 0
    )


@router.get("/{request_id}", response_model=MediaRequestResponse)
async def get_request(
    request_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific request by ID.
    User can view own requests, approvers can view all requests.
    """
    row = await conn.fetchrow(
        """
        SELECT mr.*,
               requester.username as username,
               reviewer.username as reviewer_username
        FROM media_requests mr
        LEFT JOIN users requester ON mr.user_id = requester.id
        LEFT JOIN users reviewer ON mr.reviewed_by = reviewer.id
        WHERE mr.id = $1
        """,
        request_id
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )

    # Check access: own request or has approval permission
    isOwnRequest = row["user_id"] == current_user.id
    hasApprovePermission = await canApprove(conn, current_user.id)

    if not isOwnRequest and not hasApprovePermission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this request"
        )

    return formatRequestResponse(dict(row))


@router.post("/{request_id}/approve", response_model=MediaRequestResponse)
async def approve_request(
    request_id: int,
    review: MediaRequestReview = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approve a media request.
    Requires {media_type}.approve permission.
    Creates the media item and optionally triggers auto_search.
    """
    # Get the request
    request = await conn.fetchrow(
        "SELECT * FROM media_requests WHERE id = $1",
        request_id
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )

    if request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {request['status']}"
        )

    # Check approval permission
    if not await canApproveMediaType(conn, current_user.id, request["media_type"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to approve {request['media_type']} requests"
        )

    # Create the media based on type
    createdMediaId = None
    mediaType = request["media_type"]
    externalId = request["external_id"]
    mediaProfileId = request["media_profile_id"]

    try:
        if mediaType == "movie":
            createdMediaId = await createMovie(conn, externalId, mediaProfileId)
        elif mediaType == "show":
            createdMediaId = await createShow(conn, externalId, mediaProfileId)
        elif mediaType == "anime":
            createdMediaId = await createAnime(conn, externalId, mediaProfileId)
        elif mediaType in ("album", "music"):
            createdMediaId = await createAlbum(conn, externalId, mediaProfileId)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown media type: {mediaType}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create media: {str(e)}"
        )

    # Update request status
    reviewNotes = review.notes if review else None
    row = await conn.fetchrow(
        """
        UPDATE media_requests
        SET status = 'approved',
            reviewed_at = NOW(),
            reviewed_by = $1,
            review_notes = $2,
            created_media_id = $3
        WHERE id = $4
        RETURNING *
        """,
        current_user.id,
        reviewNotes,
        createdMediaId,
        request_id
    )

    # Fetch with usernames
    result = await conn.fetchrow(
        """
        SELECT mr.*,
               requester.username as username,
               reviewer.username as reviewer_username
        FROM media_requests mr
        LEFT JOIN users requester ON mr.user_id = requester.id
        LEFT JOIN users reviewer ON mr.reviewed_by = reviewer.id
        WHERE mr.id = $1
        """,
        request_id
    )

    return formatRequestResponse(dict(result))


@router.post("/{request_id}/deny", response_model=MediaRequestResponse)
async def deny_request(
    request_id: int,
    review: MediaRequestReview = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deny a media request.
    Requires {media_type}.approve permission.
    """
    # Get the request
    request = await conn.fetchrow(
        "SELECT * FROM media_requests WHERE id = $1",
        request_id
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )

    if request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {request['status']}"
        )

    # Check approval permission
    if not await canApproveMediaType(conn, current_user.id, request["media_type"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to deny {request['media_type']} requests"
        )

    # Update request status
    reviewNotes = review.notes if review else None
    row = await conn.fetchrow(
        """
        UPDATE media_requests
        SET status = 'denied',
            reviewed_at = NOW(),
            reviewed_by = $1,
            review_notes = $2
        WHERE id = $3
        RETURNING *
        """,
        current_user.id,
        reviewNotes,
        request_id
    )

    # Fetch with usernames
    result = await conn.fetchrow(
        """
        SELECT mr.*,
               requester.username as username,
               reviewer.username as reviewer_username
        FROM media_requests mr
        LEFT JOIN users requester ON mr.user_id = requester.id
        LEFT JOIN users reviewer ON mr.reviewed_by = reviewer.id
        WHERE mr.id = $1
        """,
        request_id
    )

    return formatRequestResponse(dict(result))


@router.post("/{request_id}/cancel", response_model=MediaRequestResponse)
async def cancel_request(
    request_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel own pending request.
    Users can only cancel their own pending requests.
    """
    # Get the request
    request = await conn.fetchrow(
        "SELECT * FROM media_requests WHERE id = $1",
        request_id
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )

    # Check ownership
    if request["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own requests"
        )

    if request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only cancel pending requests. This request is {request['status']}"
        )

    # Update request status
    row = await conn.fetchrow(
        """
        UPDATE media_requests
        SET status = 'cancelled'
        WHERE id = $1
        RETURNING *
        """,
        request_id
    )

    # Fetch with usernames
    result = await conn.fetchrow(
        """
        SELECT mr.*,
               requester.username as username,
               reviewer.username as reviewer_username
        FROM media_requests mr
        LEFT JOIN users requester ON mr.user_id = requester.id
        LEFT JOIN users reviewer ON mr.reviewed_by = reviewer.id
        WHERE mr.id = $1
        """,
        request_id
    )

    return formatRequestResponse(dict(result))


# Media creation helper functions

async def createMovie(conn: asyncpg.Connection, tmdbId: int, mediaProfileId: int = None) -> int:
    """Create a movie from TMDB ID"""
    repo = MovieRepository(conn)

    # Check if already exists
    if await repo.existsByTmdbId(tmdbId):
        existing = await conn.fetchrow(
            "SELECT id FROM movies WHERE tmdb_id = $1",
            tmdbId
        )
        return existing["id"]

    # Fetch metadata from TMDB
    metadata = await tmdb_service.get_movie(tmdbId)
    parsedData = tmdb_service.parse_movie_data(metadata)

    movieData = {
        **parsedData,
        "status": "wanted",
        "monitored": True,
        "media_profile_id": mediaProfileId,
        "has_file": False,
    }

    movie = await repo.create(movieData)
    return movie.id


async def createShow(conn: asyncpg.Connection, tmdbId: int, mediaProfileId: int = None) -> int:
    """Create a show from TMDB ID"""
    repo = ShowRepository(conn)

    # Check if already exists
    if await repo.existsByTmdbId(tmdbId):
        existing = await conn.fetchrow(
            "SELECT id FROM shows WHERE tmdb_id = $1",
            tmdbId
        )
        return existing["id"]

    # Fetch metadata from TMDB
    metadata = await tmdb_service.get_tv(tmdbId)
    parsedData = tmdb_service.parse_tv_data(metadata)

    showData = {
        **parsedData,
        "status": "wanted",
        "monitored": True,
        "media_profile_id": mediaProfileId,
        "season_monitoring": "all",
    }

    show = await repo.create(showData)
    return show["id"]


async def createAnime(conn: asyncpg.Connection, anilistId: int, mediaProfileId: int = None) -> int:
    """Create an anime from AniList ID"""
    repo = AnimeRepository(conn)

    # Check if already exists
    if await repo.existsByAnilistId(anilistId):
        existing = await conn.fetchrow(
            "SELECT id FROM anime WHERE anilist_id = $1",
            anilistId
        )
        return existing["id"]

    # Fetch metadata from AniList
    metadata = await anilist_service.get_anime(anilistId)
    parsedData = anilist_service.parse_anime_data(metadata)

    animeData = {
        **parsedData,
        "status": "wanted",
        "monitored": True,
        "media_profile_id": mediaProfileId,
        "absolute_numbering": True,
        "has_file": False,
        "episode_monitoring": "all",
    }

    anime = await repo.create(animeData)
    return anime["id"]


async def createAlbum(conn: asyncpg.Connection, deezerId: int, mediaProfileId: int = None) -> int:
    """Create an album from Deezer ID"""
    repo = AlbumRepository(conn)

    # Check if already exists
    existing = await repo.getByDeezerId(deezerId)
    if existing:
        return existing["id"]

    # Fetch metadata from Deezer
    albumData = await deezer_service.get_album(deezerId)
    parsedData = deezer_service.parse_album_data(albumData)

    # Get artist info
    artistData = albumData.get("artist", {})

    createData = {
        "title": parsedData.get("title"),
        "cover": parsedData.get("cover"),
        "cover_medium": parsedData.get("cover_medium"),
        "cover_big": parsedData.get("cover_big"),
        "cover_xl": parsedData.get("cover_xl"),
        "release_date": parsedData.get("release_date"),
        "deezer_id": deezerId,
        "artist_name": artistData.get("name"),
        "status": "wanted",
        "monitored": True,
        "media_profile_id": mediaProfileId,
        "has_file": False,
        "nb_tracks": parsedData.get("nb_tracks"),
        "record_type": parsedData.get("record_type"),
        "explicit_lyrics": parsedData.get("explicit_lyrics", False),
    }

    album = await repo.create(createData)
    return album["id"]
