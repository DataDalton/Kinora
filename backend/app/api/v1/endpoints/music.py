from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import asyncpg
import os
import shutil

from app.db import get_db
from app.db.repositories import ArtistRepository, AlbumRepository, TrackRepository


class MusicMonitoringUpdate(BaseModel):
    monitored: Optional[bool] = None
    upgradeAllowed: Optional[bool] = None


def parseReleaseDate(dateStr: str | None):
    """Parse release date string from Deezer API into date object."""
    if not dateStr:
        return None
    try:
        return datetime.strptime(dateStr, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


from app.schemas.music import (
    Artist, ArtistCreate, ArtistUpdate, ArtistSearch,
    Album, AlbumCreate, AlbumUpdate, AlbumSearch,
    Track, TrackCreate, TrackUpdate, TrackSearch
)
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.deezer import deezer_service

router = APIRouter()


# Artist Endpoints
@router.get("/artists")
async def get_artists(
    skip: int = 0,
    limit: int = 100,
    monitored_only: bool = False,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all artists from library with their tags (single query with JSON aggregation)."""
    whereClause = "WHERE monitored = TRUE" if monitored_only else ""

    rows = await conn.fetch(
        f"""
        SELECT a.*,
               COALESCE(
                   json_agg(
                       json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                   ) FILTER (WHERE t.id IS NOT NULL),
                   '[]'::json
               ) as tags
        FROM artists a
        LEFT JOIN media_tags mt ON a.id = mt.media_id AND mt.media_type = 'artist'
        LEFT JOIN tags t ON mt.tag_id = t.id
        {whereClause}
        GROUP BY a.id
        ORDER BY a.created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit, skip
    )
    return [dict(row) for row in rows]


@router.get("/artists/{artist_id}", response_model=Artist)
async def get_artist(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get a specific artist by ID."""
    repo = ArtistRepository(conn)
    artist = await repo.getById(artist_id)

    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    return Artist(**artist)


@router.post("/artists", response_model=Artist, status_code=status.HTTP_201_CREATED)
async def add_artist(
    artist_data: ArtistCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add an artist to library."""
    repo = ArtistRepository(conn)

    # Check if artist already exists by Deezer ID
    if artist_data.deezer_id:
        existing = await repo.getByDeezerId(artist_data.deezer_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artist already exists in library",
            )

    data = {
        "name": artist_data.name,
        "picture": artist_data.picture,
        "picture_medium": artist_data.picture_medium,
        "picture_big": artist_data.picture_big,
        "picture_xl": artist_data.picture_xl,
        "deezer_id": artist_data.deezer_id,
        "monitored": artist_data.monitored,
        "root_folder_path": artist_data.root_folder_path,
        "nb_album": artist_data.nb_album,
        "nb_fan": artist_data.nb_fan,
    }

    artist = await repo.create(data)
    return Artist(**artist)


@router.put("/artists/{artist_id}", response_model=Artist)
async def update_artist(
    artist_id: int,
    artist_data: ArtistUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update an artist in library."""
    repo = ArtistRepository(conn)

    existing = await repo.getById(artist_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    updateData = artist_data.model_dump(exclude_unset=True)
    if not updateData:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    updated = await repo.update(artist_id, updateData)
    return Artist(**updated)


@router.delete("/artists/{artist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artist(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an artist from library."""
    repo = ArtistRepository(conn)
    deleted = await repo.delete(artist_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )


# Album Endpoints
@router.get("/albums")
async def get_albums(
    skip: int = 0,
    limit: int = 100,
    artist_id: int = None,
    monitored_only: bool = False,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all albums from library with their tags (single query with JSON aggregation)."""
    conditions = []
    params = [limit, skip]
    paramIdx = 3

    if artist_id:
        conditions.append(f"al.artist_id = ${paramIdx}")
        params.append(artist_id)
        paramIdx += 1
    if monitored_only:
        conditions.append("al.monitored = TRUE")

    whereClause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await conn.fetch(
        f"""
        SELECT al.*,
               COALESCE(
                   json_agg(
                       json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                   ) FILTER (WHERE t.id IS NOT NULL),
                   '[]'::json
               ) as tags
        FROM albums al
        LEFT JOIN media_tags mt ON al.id = mt.media_id AND mt.media_type = 'album'
        LEFT JOIN tags t ON mt.tag_id = t.id
        {whereClause}
        GROUP BY al.id
        ORDER BY al.release_date DESC
        LIMIT $1 OFFSET $2
        """,
        *params
    )
    return [dict(row) for row in rows]


@router.get("/albums/{album_id}", response_model=Album)
async def get_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get a specific album by ID."""
    repo = AlbumRepository(conn)
    album = await repo.getById(album_id)

    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    return Album(**album)


@router.post("/albums", response_model=Album, status_code=status.HTTP_201_CREATED)
async def add_album(
    album_data: AlbumCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add an album to library. If artist_id is a Deezer ID (not in artists table), creates the artist first."""
    albumRepo = AlbumRepository(conn)
    artistRepo = ArtistRepository(conn)

    # Check if album already exists by Deezer ID
    if album_data.deezer_id:
        existing = await albumRepo.getByDeezerId(album_data.deezer_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Album already exists in library",
            )

    # Handle artist_id - could be internal ID or Deezer ID
    internalArtistId = None
    artistName = None

    if album_data.artist_id:
        # First check if it's an internal artist ID
        artist = await artistRepo.getById(album_data.artist_id)

        if artist:
            internalArtistId = artist["id"]
            artistName = artist["name"]
        else:
            # Check if it's a Deezer artist ID
            artist = await artistRepo.getByDeezerId(album_data.artist_id)

            if artist:
                internalArtistId = artist["id"]
                artistName = artist["name"]
            else:
                # Artist doesn't exist - fetch from Deezer and create
                try:
                    deezerArtist = await deezer_service.get_artist(album_data.artist_id)
                    if deezerArtist:
                        newArtist = await artistRepo.create({
                            "name": deezerArtist.get("name"),
                            "picture": deezerArtist.get("picture"),
                            "picture_medium": deezerArtist.get("picture_medium"),
                            "picture_big": deezerArtist.get("picture_big"),
                            "picture_xl": deezerArtist.get("picture_xl"),
                            "deezer_id": deezerArtist.get("id"),
                            "monitored": True,
                            "has_files": False,
                            "nb_album": deezerArtist.get("nb_album"),
                            "nb_fan": deezerArtist.get("nb_fan"),
                        })
                        internalArtistId = newArtist["id"]
                        artistName = newArtist["name"]
                except Exception as e:
                    print(f"Could not fetch artist from Deezer: {e}")

    albumData = {
        "title": album_data.title,
        "cover": album_data.cover,
        "cover_medium": album_data.cover_medium,
        "cover_big": album_data.cover_big,
        "cover_xl": album_data.cover_xl,
        "release_date": album_data.release_date,
        "deezer_id": album_data.deezer_id,
        "artist_id": internalArtistId,
        "upc": album_data.upc,
        "monitored": album_data.monitored,
        "has_file": False,
        "media_profile_id": album_data.media_profile_id,
        "root_folder_path": album_data.root_folder_path,
        "artist_name": artistName,
        "status": "wanted",
        "explicit_lyrics": album_data.explicit_lyrics,
        "record_type": album_data.record_type,
    }

    album = await albumRepo.create(albumData)
    return Album(**album)


@router.put("/albums/{album_id}", response_model=Album)
async def update_album(
    album_id: int,
    album_data: AlbumUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update an album in library."""
    repo = AlbumRepository(conn)

    existing = await repo.getById(album_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    updateData = album_data.model_dump(exclude_unset=True)
    if not updateData:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    updated = await repo.update(album_id, updateData)
    return Album(**updated)


@router.delete("/albums/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an album from library."""
    repo = AlbumRepository(conn)
    deleted = await repo.delete(album_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )


# Search Endpoints (using Deezer API)
@router.get("/search/artists", response_model=List[ArtistSearch])
async def search_artists(
    query: str,
    limit: int = 25,
    current_user: User = Depends(get_current_user),
):
    """Search for artists using Deezer API."""
    results = await deezer_service.search_artist(query, limit)
    return [
        ArtistSearch(
            deezer_id=artist["id"],
            name=artist["name"],
            picture=artist.get("picture"),
            picture_medium=artist.get("picture_medium"),
            picture_big=artist.get("picture_big"),
            picture_xl=artist.get("picture_xl"),
            nb_album=artist.get("nb_album"),
            nb_fan=artist.get("nb_fan"),
        )
        for artist in results
    ]


@router.get("/search/albums", response_model=List[AlbumSearch])
async def search_albums(
    query: str,
    limit: int = 25,
    current_user: User = Depends(get_current_user),
):
    """Search for albums using Deezer API."""
    results = await deezer_service.search_album(query, limit)
    return [
        AlbumSearch(
            deezer_id=album["id"],
            title=album["title"],
            cover=album.get("cover"),
            cover_medium=album.get("cover_medium"),
            cover_big=album.get("cover_big"),
            cover_xl=album.get("cover_xl"),
            release_date=album.get("release_date"),
            nb_tracks=album.get("nb_tracks"),
            explicit_lyrics=album.get("explicit_lyrics", False),
            record_type=album.get("record_type"),
            artist=album.get("artist"),
        )
        for album in results
    ]


@router.get("/search/tracks", response_model=List[TrackSearch])
async def search_tracks(
    query: str,
    limit: int = 25,
    current_user: User = Depends(get_current_user),
):
    """Search for tracks using Deezer API."""
    results = await deezer_service.search_track(query, limit)
    return [
        TrackSearch(
            deezer_id=track["id"],
            title=track["title"],
            duration=track.get("duration"),
            track_position=track.get("track_position"),
            disk_number=track.get("disk_number"),
            explicit_lyrics=track.get("explicit_lyrics", False),
            preview=track.get("preview"),
            artist=track.get("artist"),
            album=track.get("album"),
        )
        for track in results
    ]


@router.get("/artist/{deezer_id}/details")
async def get_artist_details(
    deezer_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get detailed artist information from Deezer."""
    artistData = await deezer_service.get_artist(deezer_id)
    albumsData = await deezer_service.get_artist_albums(deezer_id)

    return {
        "artist": deezer_service.parse_artist_data(artistData),
        "albums": albumsData,
    }


@router.get("/album/{deezer_id}/details")
async def get_album_details(
    deezer_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get detailed album information from Deezer including tracks."""
    albumData = await deezer_service.get_album(deezer_id)
    return deezer_service.parse_album_data(albumData)


# Track Endpoints
@router.get("/tracks", response_model=List[Track])
async def get_tracks(
    skip: int = 0,
    limit: int = 100,
    album_id: int = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all tracks from library with album cover data."""
    if album_id:
        rows = await conn.fetch(
            """
            SELECT t.*, a.cover as album_cover, a.cover_medium as album_cover_medium,
                   a.cover_big as album_cover_big, a.cover_xl as album_cover_xl,
                   a.release_date as album_release_date
            FROM tracks t
            LEFT JOIN albums a ON t.album_id = a.id
            WHERE t.album_id = $1
            ORDER BY t.disk_number, t.track_position
            LIMIT $2 OFFSET $3
            """,
            album_id, limit, skip
        )
    else:
        rows = await conn.fetch(
            """
            SELECT t.*, a.cover as album_cover, a.cover_medium as album_cover_medium,
                   a.cover_big as album_cover_big, a.cover_xl as album_cover_xl,
                   a.release_date as album_release_date
            FROM tracks t
            LEFT JOIN albums a ON t.album_id = a.id
            ORDER BY t.disk_number, t.track_position
            LIMIT $1 OFFSET $2
            """,
            limit, skip
        )
    return [Track(**dict(row)) for row in rows]


@router.get("/tracks/{track_id}", response_model=Track)
async def get_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get a specific track by ID with album cover data."""
    row = await conn.fetchrow(
        """
        SELECT t.*, a.cover as album_cover, a.cover_medium as album_cover_medium,
               a.cover_big as album_cover_big, a.cover_xl as album_cover_xl,
               a.release_date as album_release_date
        FROM tracks t
        LEFT JOIN albums a ON t.album_id = a.id
        WHERE t.id = $1
        """,
        track_id
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    return Track(**dict(row))


@router.post("/tracks", response_model=Track, status_code=status.HTTP_201_CREATED)
async def add_track(
    track_data: TrackCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add a track to library."""
    repo = TrackRepository(conn)

    # Check if track already exists by Deezer ID
    if track_data.deezer_id:
        existing = await repo.getByDeezerId(track_data.deezer_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Track already exists in library",
            )

    data = {
        "title": track_data.title,
        "duration": track_data.duration,
        "track_position": track_data.track_position,
        "disk_number": track_data.disk_number,
        "deezer_id": track_data.deezer_id,
        "album_id": track_data.album_id,
        "isrc": track_data.isrc,
        "explicit_lyrics": track_data.explicit_lyrics,
        "preview": track_data.preview,
        "artist_name": track_data.artist_name,
        "album_title": track_data.album_title,
    }

    track = await repo.create(data)
    return Track(**track)


@router.put("/tracks/{track_id}", response_model=Track)
async def update_track(
    track_id: int,
    track_data: TrackUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update a track in library."""
    repo = TrackRepository(conn)

    existing = await repo.getById(track_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    updateData = track_data.model_dump(exclude_unset=True)
    if not updateData:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Build update query
    setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updateData.keys()))
    row = await conn.fetchrow(
        f"UPDATE tracks SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
        track_id, *updateData.values()
    )
    return Track(**dict(row))


@router.delete("/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a track from library."""
    repo = TrackRepository(conn)
    deleted = await repo.delete(track_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )


# Batch Operations - Add Full Discography
@router.post("/artists/{artist_id}/add-discography", status_code=status.HTTP_201_CREATED)
async def add_artist_discography(
    artist_id: int,
    media_profile_id: int = None,
    monitored: bool = True,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add all albums from an artist's discography to the library."""
    artistRepo = ArtistRepository(conn)
    albumRepo = AlbumRepository(conn)

    artist = await artistRepo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    if not artist["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artist has no Deezer ID for fetching discography",
        )

    # Fetch albums from Deezer
    try:
        albumsData = await deezer_service.get_artist_albums(artist["deezer_id"], limit=100)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch discography from Deezer: {str(e)}",
        )

    if not albumsData:
        return {
            "message": "No albums found in Deezer for this artist",
            "added": [],
            "skipped": [],
            "albums": [],
        }

    addedAlbums = []
    skippedAlbums = []

    for albumInfo in albumsData:
        # Check if album already exists
        existing = await albumRepo.getByDeezerId(albumInfo["id"])
        if existing:
            skippedAlbums.append(albumInfo["title"])
            continue

        # Add album to library
        newAlbum = await albumRepo.create({
            "title": albumInfo.get("title"),
            "cover": albumInfo.get("cover"),
            "cover_medium": albumInfo.get("cover_medium"),
            "cover_big": albumInfo.get("cover_big"),
            "cover_xl": albumInfo.get("cover_xl"),
            "release_date": parseReleaseDate(albumInfo.get("release_date")),
            "deezer_id": albumInfo.get("id"),
            "artist_id": artist_id,
            "monitored": monitored,
            "media_profile_id": media_profile_id,
            "root_folder_path": artist["root_folder_path"],
            "nb_tracks": albumInfo.get("nb_tracks"),
            "record_type": albumInfo.get("record_type"),
            "explicit_lyrics": albumInfo.get("explicit_lyrics", False),
            "artist_name": artist["name"],
            "status": "wanted",
            "has_file": False,
        })
        addedAlbums.append(newAlbum)

    return {
        "message": f"Added {len(addedAlbums)} albums, skipped {len(skippedAlbums)} existing",
        "added": [a["title"] for a in addedAlbums],
        "skipped": skippedAlbums,
        "albums": addedAlbums,
    }


# Batch Operations - Add Album with Tracks
@router.post("/albums/{album_id}/add-tracks", status_code=status.HTTP_201_CREATED)
async def add_album_tracks(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add all tracks from an album to the library (fetches from Deezer)."""
    albumRepo = AlbumRepository(conn)
    trackRepo = TrackRepository(conn)

    album = await albumRepo.getById(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    if not album["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Album has no Deezer ID for fetching tracks",
        )

    # Fetch album details with tracks from Deezer
    try:
        albumData = await deezer_service.get_album(album["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch album data from Deezer: {str(e)}",
        )

    tracksData = albumData.get("tracks", {}).get("data", [])

    if not tracksData:
        return {
            "message": "No tracks found in Deezer data for this album",
            "added": [],
            "skipped": [],
            "tracks": [],
        }

    addedTracks = []
    skippedTracks = []

    for trackInfo in tracksData:
        # Check if track already exists
        existing = await trackRepo.getByDeezerId(trackInfo["id"])
        if existing:
            skippedTracks.append(trackInfo["title"])
            continue

        # Add track to library
        newTrack = await trackRepo.create({
            "title": trackInfo.get("title"),
            "duration": trackInfo.get("duration"),
            "track_position": trackInfo.get("track_position"),
            "disk_number": trackInfo.get("disk_number", 1),
            "deezer_id": trackInfo.get("id"),
            "album_id": album_id,
            "isrc": trackInfo.get("isrc"),
            "explicit_lyrics": trackInfo.get("explicit_lyrics", False),
            "preview": trackInfo.get("preview"),
            "artist_name": trackInfo.get("artist", {}).get("name"),
            "album_title": album["title"],
            "has_file": False,
        })
        addedTracks.append(newTrack)

    # Update album track count
    await albumRepo.update(album_id, {"nb_tracks": len(addedTracks) + len(skippedTracks)})

    return {
        "message": f"Added {len(addedTracks)} tracks, skipped {len(skippedTracks)} existing",
        "added": [t["title"] for t in addedTracks],
        "skipped": skippedTracks,
        "tracks": addedTracks,
    }


# Download Operations
@router.post("/albums/{album_id}/search-download")
async def search_and_download_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Search for an album torrent and add to download client."""
    from app.services.automation.search_engine import search_engine
    from app.services.media_profile import media_profile_service

    albumRepo = AlbumRepository(conn)
    artistRepo = ArtistRepository(conn)

    album = await albumRepo.getById(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    # Get artist for search query
    artist = None
    if album["artist_id"]:
        artist = await artistRepo.getById(album["artist_id"])

    # Build search query
    artistName = artist["name"] if artist else album.get("artist_name", "")
    albumTitle = album["title"]
    searchQuery = f"{artistName} {albumTitle}"

    # Get media profile
    profile = None
    if album["media_profile_id"]:
        profile = await media_profile_service.get_profile(album["media_profile_id"])

    if not profile:
        # Use default music profile settings
        from app.services.media_profile import MediaProfile
        profile = MediaProfile(
            id=0,
            name="Default Music",
            music_preferred_quality=["flac", "mp3_320", "mp3_256"],
        )

    # Search and download
    torrentHash = await search_engine.search_music_and_download(
        query=searchQuery,
        profile=profile,
        save_path=album.get("root_folder_path"),
        tags=["music", artistName],
    )

    if torrentHash:
        # Update album status
        await albumRepo.update(album_id, {"status": "downloading"})
        return {
            "message": "Download started",
            "torrent_hash": torrentHash,
            "query": searchQuery,
        }
    else:
        return {
            "message": "No suitable release found",
            "query": searchQuery,
        }


@router.post("/tracks/{track_id}/search-download")
async def search_and_download_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Search for a track's album and add to download client."""
    from app.services.automation.search_engine import search_engine
    from app.services.media_profile import media_profile_service

    trackRepo = TrackRepository(conn)
    albumRepo = AlbumRepository(conn)

    track = await trackRepo.getById(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    # Get album for search query
    album = None
    if track["album_id"]:
        album = await albumRepo.getById(track["album_id"])

    # Build search query
    artistName = track.get("artist_name", "")
    trackTitle = track["title"]
    albumTitle = album["title"] if album else track.get("album_title", "")
    searchQuery = f"{artistName} {albumTitle}" if albumTitle else f"{artistName} {trackTitle}"

    # Get media profile from album
    profile = None
    if album and album.get("media_profile_id"):
        profile = await media_profile_service.get_profile(album["media_profile_id"])

    if not profile:
        from app.services.media_profile import MediaProfile
        profile = MediaProfile(
            id=0,
            name="Default Music",
            music_preferred_quality=["flac", "mp3_320", "mp3_256"],
        )

    # Search and download
    torrentHash = await search_engine.search_music_and_download(
        query=searchQuery,
        profile=profile,
        save_path=album.get("root_folder_path") if album else None,
        tags=["music", artistName],
    )

    if torrentHash:
        # Update album status if available
        if album:
            await albumRepo.update(album["id"], {"status": "downloading"})
        return {
            "message": "Download started",
            "torrent_hash": torrentHash,
            "query": searchQuery,
        }
    else:
        return {
            "message": "No suitable release found",
            "query": searchQuery,
        }


@router.post("/artists/{artist_id}/search-download-all")
async def search_and_download_discography(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Search and download all wanted albums for an artist."""
    from app.services.automation.search_engine import search_engine
    from app.services.media_profile import media_profile_service, MediaProfile

    artistRepo = ArtistRepository(conn)
    albumRepo = AlbumRepository(conn)

    artist = await artistRepo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    # Get all wanted albums for this artist
    albums = await conn.fetch(
        "SELECT * FROM albums WHERE artist_id = $1 AND status = 'wanted' AND monitored = TRUE",
        artist_id,
    )

    if not albums:
        return {
            "message": "No wanted albums to download",
            "started": [],
            "failed": [],
        }

    started = []
    failed = []

    for album in albums:
        searchQuery = f"{artist['name']} {album['title']}"

        # Get media profile
        profile = None
        if album["media_profile_id"]:
            profile = await media_profile_service.get_profile(album["media_profile_id"])

        if not profile:
            profile = MediaProfile(
                id=0,
                name="Default Music",
                music_preferred_quality=["flac", "mp3_320", "mp3_256"],
            )

        torrentHash = await search_engine.search_music_and_download(
            query=searchQuery,
            profile=profile,
            save_path=album.get("root_folder_path") or artist.get("root_folder_path"),
            tags=["music", artist["name"]],
        )

        if torrentHash:
            await albumRepo.update(album["id"], {"status": "downloading"})
            started.append({"album": album["title"], "hash": torrentHash})
        else:
            failed.append(album["title"])

    return {
        "message": f"Started {len(started)} downloads, {len(failed)} failed",
        "started": started,
        "failed": failed,
    }


# Batch Monitoring Operations
@router.put("/artists/{artist_id}/monitor-all-albums")
async def monitor_all_artist_albums(
    artist_id: int,
    monitored: bool = True,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Monitor or unmonitor all albums for an artist (single batch update)."""
    artistRepo = ArtistRepository(conn)

    artist = await artistRepo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    result = await conn.execute(
        "UPDATE albums SET monitored = $1, updated_at = NOW() WHERE artist_id = $2",
        monitored,
        artist_id,
    )

    count = int(result.split()[-1]) if result else 0

    return {
        "message": f"{'Monitored' if monitored else 'Unmonitored'} {count} albums",
        "updated_count": count,
    }


@router.put("/artists/{artist_id}/monitoring")
async def update_artist_monitoring(
    artist_id: int,
    data: MusicMonitoringUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update monitoring settings for an artist."""
    repo = ArtistRepository(conn)

    artist = await repo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    updateData = {}
    if data.monitored is not None:
        updateData["monitored"] = data.monitored
    if data.upgradeAllowed is not None:
        updateData["upgrade_allowed"] = data.upgradeAllowed

    if not updateData:
        return Artist(**artist)

    updated = await repo.update(artist_id, updateData)
    return Artist(**updated)


@router.put("/albums/{album_id}/monitoring")
async def update_album_monitoring(
    album_id: int,
    data: MusicMonitoringUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update monitoring settings for an album."""
    repo = AlbumRepository(conn)

    album = await repo.getById(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    updateData = {}
    if data.monitored is not None:
        updateData["monitored"] = data.monitored
    if data.upgradeAllowed is not None:
        updateData["upgrade_allowed"] = data.upgradeAllowed

    if not updateData:
        return Album(**album)

    updated = await repo.update(album_id, updateData)
    return Album(**updated)


@router.put("/tracks/{track_id}/monitoring")
async def update_track_monitoring(
    track_id: int,
    data: MusicMonitoringUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update monitoring settings for a track."""
    repo = TrackRepository(conn)

    track = await repo.getById(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    updateData = {}
    if data.monitored is not None:
        updateData["monitored"] = data.monitored
    if data.upgradeAllowed is not None:
        updateData["upgrade_allowed"] = data.upgradeAllowed

    if not updateData:
        return await enrichTrackWithAlbumData(track, conn)

    updated = await repo.update(track_id, updateData)
    return await enrichTrackWithAlbumData(updated, conn)


# Delete with files
@router.delete("/artists/{artist_id}/delete")
async def delete_artist_with_files(
    artist_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an artist and optionally their files from disk."""
    repo = ArtistRepository(conn)

    artist = await repo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    deletedFiles = []
    errors = []

    if delete_files:
        albums = await conn.fetch(
            "SELECT file_path FROM albums WHERE artist_id = $1 AND file_path IS NOT NULL",
            artist_id,
        )

        for album in albums:
            if album["file_path"] and os.path.exists(album["file_path"]):
                try:
                    if os.path.isdir(album["file_path"]):
                        shutil.rmtree(album["file_path"])
                    else:
                        os.remove(album["file_path"])
                    deletedFiles.append(album["file_path"])
                except Exception as e:
                    errors.append(f"Failed to delete {album['file_path']}: {str(e)}")

        if artist["root_folder_path"] and os.path.exists(artist["root_folder_path"]):
            try:
                if os.path.isdir(artist["root_folder_path"]):
                    if not os.listdir(artist["root_folder_path"]):
                        os.rmdir(artist["root_folder_path"])
            except Exception as e:
                errors.append(f"Failed to remove artist folder: {str(e)}")

    await repo.delete(artist_id)

    return {
        "message": "Artist deleted successfully",
        "deleted_files": deletedFiles,
        "errors": errors if errors else None,
    }


@router.delete("/albums/{album_id}/delete")
async def delete_album_with_files(
    album_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an album and optionally its files from disk."""
    repo = AlbumRepository(conn)

    album = await repo.getById(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    deletedFiles = []
    errors = []

    if delete_files and album["file_path"]:
        if os.path.exists(album["file_path"]):
            try:
                if os.path.isdir(album["file_path"]):
                    shutil.rmtree(album["file_path"])
                else:
                    os.remove(album["file_path"])
                deletedFiles.append(album["file_path"])
            except Exception as e:
                errors.append(f"Failed to delete {album['file_path']}: {str(e)}")

    await repo.delete(album_id)

    return {
        "message": "Album deleted successfully",
        "deleted_files": deletedFiles,
        "errors": errors if errors else None,
    }


@router.delete("/tracks/{track_id}/delete")
async def delete_track_with_files(
    track_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a track and optionally its files from disk."""
    repo = TrackRepository(conn)

    track = await repo.getById(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    deletedFiles = []
    errors = []

    if delete_files and track.get("file_path"):
        if os.path.exists(track["file_path"]):
            try:
                os.remove(track["file_path"])
                deletedFiles.append(track["file_path"])
            except Exception as e:
                errors.append(f"Failed to delete {track['file_path']}: {str(e)}")

    await repo.delete(track_id)

    return {
        "message": "Track deleted successfully",
        "deleted_files": deletedFiles,
        "errors": errors if errors else None,
    }


# Refresh Metadata
@router.post("/artists/{artist_id}/refresh-metadata")
async def refresh_artist_metadata(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Refresh artist metadata from Deezer."""
    repo = ArtistRepository(conn)

    artist = await repo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    if not artist["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artist has no Deezer ID for refreshing metadata",
        )

    try:
        deezerData = await deezer_service.get_artist(artist["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch artist data from Deezer: {str(e)}",
        )

    if not deezerData:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found on Deezer",
        )

    updated = await repo.update(artist_id, {
        "name": deezerData.get("name"),
        "picture": deezerData.get("picture"),
        "picture_medium": deezerData.get("picture_medium"),
        "picture_big": deezerData.get("picture_big"),
        "picture_xl": deezerData.get("picture_xl"),
        "nb_album": deezerData.get("nb_album"),
        "nb_fan": deezerData.get("nb_fan"),
    })

    return {
        "message": "Artist metadata refreshed successfully",
        "artist": Artist(**updated),
    }


@router.post("/albums/{album_id}/refresh-metadata")
async def refresh_album_metadata(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Refresh album metadata from Deezer."""
    repo = AlbumRepository(conn)

    album = await repo.getById(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    if not album["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Album has no Deezer ID for refreshing metadata",
        )

    try:
        deezerData = await deezer_service.get_album(album["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch album data from Deezer: {str(e)}",
        )

    if not deezerData:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found on Deezer",
        )

    updated = await repo.update(album_id, {
        "title": deezerData.get("title"),
        "cover": deezerData.get("cover"),
        "cover_medium": deezerData.get("cover_medium"),
        "cover_big": deezerData.get("cover_big"),
        "cover_xl": deezerData.get("cover_xl"),
        "release_date": parseReleaseDate(deezerData.get("release_date")),
        "nb_tracks": deezerData.get("nb_tracks"),
        "record_type": deezerData.get("record_type"),
        "upc": deezerData.get("upc"),
    })

    return {
        "message": "Album metadata refreshed successfully",
        "album": Album(**updated),
    }


@router.post("/tracks/{track_id}/refresh-metadata")
async def refresh_track_metadata(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Refresh track metadata from Deezer."""
    repo = TrackRepository(conn)

    track = await repo.getById(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    if not track["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Track has no Deezer ID for refreshing metadata",
        )

    try:
        deezerData = await deezer_service.get_track(track["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch track data from Deezer: {str(e)}",
        )

    if not deezerData:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found on Deezer",
        )

    updated = await repo.update(track_id, {
        "title": deezerData.get("title"),
        "duration": deezerData.get("duration"),
        "track_position": deezerData.get("track_position"),
        "disk_number": deezerData.get("disk_number", 1),
        "isrc": deezerData.get("isrc"),
        "explicit_lyrics": deezerData.get("explicit_lyrics", False),
        "preview": deezerData.get("preview"),
    })

    return {
        "message": "Track metadata refreshed successfully",
        "track": Track(**updated),
    }


# Get albums by artist with filtering
@router.get("/artists/{artist_id}/albums", response_model=List[Album])
async def get_artist_albums(
    artist_id: int,
    record_type: Optional[str] = Query(None, description="Filter by record type: album, single, ep, compilation"),
    monitored_only: bool = False,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all albums for a specific artist with optional filtering."""
    artistRepo = ArtistRepository(conn)

    artist = await artistRepo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    conditions = ["artist_id = $1"]
    params = [artist_id]
    paramCount = 2

    if record_type:
        conditions.append(f"record_type = ${paramCount}")
        params.append(record_type)
        paramCount += 1

    if monitored_only:
        conditions.append("monitored = TRUE")

    query = f"SELECT * FROM albums WHERE {' AND '.join(conditions)} ORDER BY release_date DESC"

    rows = await conn.fetch(query, *params)
    return [Album(**dict(row)) for row in rows]


@router.get("/artists/{artist_id}/discography")
async def get_artist_discography(
    artist_id: int,
    record_type: Optional[str] = Query(None, description="Filter by record type: album, single, ep, compilation"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all albums from Deezer for an artist, marking which ones are in library."""
    artistRepo = ArtistRepository(conn)
    albumRepo = AlbumRepository(conn)

    artist = await artistRepo.getById(artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    if not artist["deezer_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artist has no Deezer ID for fetching discography",
        )

    # Fetch all albums from Deezer
    try:
        deezerAlbums = await deezer_service.get_artist_albums(artist["deezer_id"], limit=100)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch discography from Deezer: {str(e)}",
        )

    # Get library album Deezer IDs for comparison
    libraryRows = await conn.fetch(
        "SELECT deezer_id, id, status, monitored, has_file FROM albums WHERE artist_id = $1 AND deezer_id IS NOT NULL",
        artist_id
    )
    libraryAlbumMap = {row["deezer_id"]: dict(row) for row in libraryRows}

    # Filter by record type if specified
    if record_type:
        deezerAlbums = [a for a in deezerAlbums if a.get("record_type", "").lower() == record_type.lower()]

    # Build combined response
    result = []
    for album in deezerAlbums:
        deezerId = album.get("id")
        inLibrary = deezerId in libraryAlbumMap

        albumData = {
            "deezer_id": deezerId,
            "title": album.get("title"),
            "cover": album.get("cover"),
            "cover_medium": album.get("cover_medium"),
            "cover_big": album.get("cover_big"),
            "cover_xl": album.get("cover_xl"),
            "release_date": album.get("release_date"),
            "nb_tracks": album.get("nb_tracks"),
            "record_type": album.get("record_type"),
            "explicit_lyrics": album.get("explicit_lyrics", False),
            "in_library": inLibrary,
        }

        if inLibrary:
            libraryData = libraryAlbumMap[deezerId]
            albumData["library_id"] = libraryData["id"]
            albumData["status"] = libraryData["status"]
            albumData["monitored"] = libraryData["monitored"]
            albumData["has_file"] = libraryData["has_file"]
        else:
            albumData["library_id"] = None
            albumData["status"] = None
            albumData["monitored"] = False
            albumData["has_file"] = False

        result.append(albumData)

    # Sort by release date descending
    result.sort(key=lambda x: x.get("release_date") or "", reverse=True)

    return result
