from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import asyncpg
import os
import shutil

from app.core.database import get_db


class MusicMonitoringUpdate(BaseModel):
    monitored: Optional[bool] = None
    upgradeAllowed: Optional[bool] = None


def parse_release_date(date_str: str | None):
    """Parse release date string from Deezer API into date object"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
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
    """
    Get all artists from library with their tags
    """
    query = "SELECT * FROM artists"
    if monitored_only:
        query += " WHERE monitored = TRUE"
    query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {skip}"

    rows = await conn.fetch(query)
    artists = [dict(row) for row in rows]

    if artists:
        artist_ids = [a["id"] for a in artists]
        tags_query = """
            SELECT mt.media_id, t.id, t.name, t.color
            FROM media_tags mt
            JOIN tags t ON t.id = mt.tag_id
            WHERE mt.media_type = 'artist' AND mt.media_id = ANY($1)
        """
        tag_rows = await conn.fetch(tags_query, artist_ids)

        tags_by_artist = {}
        for row in tag_rows:
            artist_id = row["media_id"]
            if artist_id not in tags_by_artist:
                tags_by_artist[artist_id] = []
            tags_by_artist[artist_id].append({
                "id": row["id"],
                "name": row["name"],
                "color": row["color"],
            })

        for artist in artists:
            artist["tags"] = tags_by_artist.get(artist["id"], [])

    return artists


@router.get("/artists/{artist_id}", response_model=Artist)
async def get_artist(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific artist by ID
    """
    row = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    return Artist(**dict(row))


@router.post("/artists", response_model=Artist, status_code=status.HTTP_201_CREATED)
async def add_artist(
    artist_data: ArtistCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add an artist to library
    """
    # Check if artist already exists by Deezer ID
    if artist_data.deezer_id:
        existing = await conn.fetchrow(
            "SELECT id FROM artists WHERE deezer_id = $1", artist_data.deezer_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artist already exists in library",
            )

    row = await conn.fetchrow(
        """
        INSERT INTO artists (
            name, picture, picture_medium, picture_big, picture_xl,
            deezer_id, monitored, root_folder_path, nb_album, nb_fan
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        artist_data.name,
        artist_data.picture,
        artist_data.picture_medium,
        artist_data.picture_big,
        artist_data.picture_xl,
        artist_data.deezer_id,
        artist_data.monitored,
        artist_data.root_folder_path,
        artist_data.nb_album,
        artist_data.nb_fan,
    )

    return Artist(**dict(row))


@router.put("/artists/{artist_id}", response_model=Artist)
async def update_artist(
    artist_id: int,
    artist_data: ArtistUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update an artist in library
    """
    existing = await conn.fetchrow("SELECT id FROM artists WHERE id = $1", artist_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    update_fields = []
    values = []
    param_count = 1

    for field, value in artist_data.model_dump(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    values.append(artist_id)
    query = f"""
        UPDATE artists
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Artist(**dict(row))


@router.delete("/artists/{artist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artist(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete an artist from library
    """
    result = await conn.execute("DELETE FROM artists WHERE id = $1", artist_id)

    if result == "DELETE 0":
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
    """
    Get all albums from library with their tags
    """
    query = "SELECT * FROM albums"
    conditions = []

    if artist_id:
        conditions.append(f"artist_id = {artist_id}")
    if monitored_only:
        conditions.append("monitored = TRUE")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY release_date DESC LIMIT {limit} OFFSET {skip}"

    rows = await conn.fetch(query)
    albums = [dict(row) for row in rows]

    if albums:
        album_ids = [a["id"] for a in albums]
        tags_query = """
            SELECT mt.media_id, t.id, t.name, t.color
            FROM media_tags mt
            JOIN tags t ON t.id = mt.tag_id
            WHERE mt.media_type = 'album' AND mt.media_id = ANY($1)
        """
        tag_rows = await conn.fetch(tags_query, album_ids)

        tags_by_album = {}
        for row in tag_rows:
            album_id = row["media_id"]
            if album_id not in tags_by_album:
                tags_by_album[album_id] = []
            tags_by_album[album_id].append({
                "id": row["id"],
                "name": row["name"],
                "color": row["color"],
            })

        for album in albums:
            album["tags"] = tags_by_album.get(album["id"], [])

    return albums


@router.get("/albums/{album_id}", response_model=Album)
async def get_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific album by ID
    """
    row = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    return Album(**dict(row))


@router.post("/albums", response_model=Album, status_code=status.HTTP_201_CREATED)
async def add_album(
    album_data: AlbumCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add an album to library
    If artist_id is a Deezer ID (not in artists table), creates the artist first
    """
    # Check if album already exists by Deezer ID
    if album_data.deezer_id:
        existing = await conn.fetchrow(
            "SELECT id FROM albums WHERE deezer_id = $1", album_data.deezer_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Album already exists in library",
            )

    # Handle artist_id - could be internal ID or Deezer ID
    internal_artist_id = None
    artist_name = None

    if album_data.artist_id:
        # First check if it's an internal artist ID
        artist_row = await conn.fetchrow(
            "SELECT id, name FROM artists WHERE id = $1", album_data.artist_id
        )

        if artist_row:
            internal_artist_id = artist_row["id"]
            artist_name = artist_row["name"]
        else:
            # Check if it's a Deezer artist ID
            artist_row = await conn.fetchrow(
                "SELECT id, name FROM artists WHERE deezer_id = $1", album_data.artist_id
            )

            if artist_row:
                internal_artist_id = artist_row["id"]
                artist_name = artist_row["name"]
            else:
                # Artist doesn't exist - fetch from Deezer and create
                try:
                    artist_data = await deezer_service.get_artist(album_data.artist_id)
                    if artist_data:
                        new_artist = await conn.fetchrow(
                            """
                            INSERT INTO artists (
                                name, picture, picture_medium, picture_big, picture_xl,
                                deezer_id, monitored, nb_album, nb_fan
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7, $8)
                            RETURNING id, name
                            """,
                            artist_data.get("name"),
                            artist_data.get("picture"),
                            artist_data.get("picture_medium"),
                            artist_data.get("picture_big"),
                            artist_data.get("picture_xl"),
                            artist_data.get("id"),
                            artist_data.get("nb_album"),
                            artist_data.get("nb_fan"),
                        )
                        internal_artist_id = new_artist["id"]
                        artist_name = new_artist["name"]
                except Exception as e:
                    print(f"Could not fetch artist from Deezer: {e}")

    row = await conn.fetchrow(
        """
        INSERT INTO albums (
            title, cover, cover_medium, cover_big, cover_xl, release_date,
            deezer_id, artist_id, upc, monitored, media_profile_id, root_folder_path,
            artist_name, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 'wanted')
        RETURNING *
        """,
        album_data.title,
        album_data.cover,
        album_data.cover_medium,
        album_data.cover_big,
        album_data.cover_xl,
        album_data.release_date,
        album_data.deezer_id,
        internal_artist_id,
        album_data.upc,
        album_data.monitored,
        album_data.media_profile_id,
        album_data.root_folder_path,
        artist_name,
    )

    return Album(**dict(row))


@router.put("/albums/{album_id}", response_model=Album)
async def update_album(
    album_id: int,
    album_data: AlbumUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update an album in library
    """
    existing = await conn.fetchrow("SELECT id FROM albums WHERE id = $1", album_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    update_fields = []
    values = []
    param_count = 1

    for field, value in album_data.model_dump(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    values.append(album_id)
    query = f"""
        UPDATE albums
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Album(**dict(row))


@router.delete("/albums/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete an album from library
    """
    result = await conn.execute("DELETE FROM albums WHERE id = $1", album_id)

    if result == "DELETE 0":
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
    """
    Search for artists using Deezer API
    """
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
    """
    Search for albums using Deezer API
    """
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
    """
    Search for tracks using Deezer API
    """
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
    """
    Get detailed artist information from Deezer
    """
    artist_data = await deezer_service.get_artist(deezer_id)
    albums_data = await deezer_service.get_artist_albums(deezer_id)

    return {
        "artist": deezer_service.parse_artist_data(artist_data),
        "albums": albums_data,
    }


@router.get("/album/{deezer_id}/details")
async def get_album_details(
    deezer_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed album information from Deezer including tracks
    """
    album_data = await deezer_service.get_album(deezer_id)
    return deezer_service.parse_album_data(album_data)


# Track Endpoints
@router.get("/tracks", response_model=List[Track])
async def get_tracks(
    skip: int = 0,
    limit: int = 100,
    album_id: int = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all tracks from library
    """
    query = "SELECT * FROM tracks"
    if album_id:
        query += f" WHERE album_id = {album_id}"
    query += f" ORDER BY disk_number, track_position LIMIT {limit} OFFSET {skip}"

    rows = await conn.fetch(query)
    return [Track(**dict(row)) for row in rows]


@router.get("/tracks/{track_id}", response_model=Track)
async def get_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific track by ID
    """
    row = await conn.fetchrow("SELECT * FROM tracks WHERE id = $1", track_id)

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
    """
    Add a track to library
    """
    # Check if track already exists by Deezer ID
    if track_data.deezer_id:
        existing = await conn.fetchrow(
            "SELECT id FROM tracks WHERE deezer_id = $1", track_data.deezer_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Track already exists in library",
            )

    row = await conn.fetchrow(
        """
        INSERT INTO tracks (
            title, duration, track_position, disk_number, deezer_id, album_id, isrc,
            explicit_lyrics, preview, artist_name, album_title
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING *
        """,
        track_data.title,
        track_data.duration,
        track_data.track_position,
        track_data.disk_number,
        track_data.deezer_id,
        track_data.album_id,
        track_data.isrc,
        track_data.explicit_lyrics,
        track_data.preview,
        track_data.artist_name,
        track_data.album_title,
    )

    return Track(**dict(row))


@router.put("/tracks/{track_id}", response_model=Track)
async def update_track(
    track_id: int,
    track_data: TrackUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update a track in library
    """
    existing = await conn.fetchrow("SELECT id FROM tracks WHERE id = $1", track_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    update_fields = []
    values = []
    param_count = 1

    for field, value in track_data.model_dump(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    values.append(track_id)
    query = f"""
        UPDATE tracks
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Track(**dict(row))


@router.delete("/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a track from library
    """
    result = await conn.execute("DELETE FROM tracks WHERE id = $1", track_id)

    if result == "DELETE 0":
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
    """
    Add all albums from an artist's discography to the library
    """
    # Get artist from library
    artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)
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
        albums_data = await deezer_service.get_artist_albums(artist["deezer_id"], limit=100)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch discography from Deezer: {str(e)}",
        )

    if not albums_data:
        return {
            "message": "No albums found in Deezer for this artist",
            "added": [],
            "skipped": [],
            "albums": [],
        }

    added_albums = []
    skipped_albums = []

    for album_info in albums_data:
        # Check if album already exists
        existing = await conn.fetchrow(
            "SELECT id FROM albums WHERE deezer_id = $1", album_info["id"]
        )
        if existing:
            skipped_albums.append(album_info["title"])
            continue

        # Add album to library
        row = await conn.fetchrow(
            """
            INSERT INTO albums (
                title, cover, cover_medium, cover_big, cover_xl, release_date,
                deezer_id, artist_id, monitored, media_profile_id, root_folder_path,
                nb_tracks, record_type, artist_name, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 'wanted')
            RETURNING *
            """,
            album_info.get("title"),
            album_info.get("cover"),
            album_info.get("cover_medium"),
            album_info.get("cover_big"),
            album_info.get("cover_xl"),
            parse_release_date(album_info.get("release_date")),
            album_info.get("id"),
            artist_id,
            monitored,
            media_profile_id,
            artist["root_folder_path"],
            album_info.get("nb_tracks"),
            album_info.get("record_type"),
            artist["name"],
        )
        added_albums.append(dict(row))

    return {
        "message": f"Added {len(added_albums)} albums, skipped {len(skipped_albums)} existing",
        "added": [a["title"] for a in added_albums],
        "skipped": skipped_albums,
        "albums": added_albums,
    }


# Batch Operations - Add Album with Tracks
@router.post("/albums/{album_id}/add-tracks", status_code=status.HTTP_201_CREATED)
async def add_album_tracks(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add all tracks from an album to the library (fetches from Deezer)
    """
    # Get album from library
    album = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)
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
        album_data = await deezer_service.get_album(album["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch album data from Deezer: {str(e)}",
        )

    tracks_data = album_data.get("tracks", {}).get("data", [])

    if not tracks_data:
        return {
            "message": "No tracks found in Deezer data for this album",
            "added": [],
            "skipped": [],
            "tracks": [],
        }

    added_tracks = []
    skipped_tracks = []

    for track_info in tracks_data:
        # Check if track already exists
        existing = await conn.fetchrow(
            "SELECT id FROM tracks WHERE deezer_id = $1", track_info["id"]
        )
        if existing:
            skipped_tracks.append(track_info["title"])
            continue

        # Add track to library
        row = await conn.fetchrow(
            """
            INSERT INTO tracks (
                title, duration, track_position, disk_number, deezer_id, album_id,
                isrc, explicit_lyrics, preview, artist_name, album_title
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            track_info.get("title"),
            track_info.get("duration"),
            track_info.get("track_position"),
            track_info.get("disk_number", 1),
            track_info.get("id"),
            album_id,
            track_info.get("isrc"),
            track_info.get("explicit_lyrics", False),
            track_info.get("preview"),
            track_info.get("artist", {}).get("name"),
            album["title"],
        )
        added_tracks.append(dict(row))

    # Update album track count
    await conn.execute(
        "UPDATE albums SET nb_tracks = $1 WHERE id = $2",
        len(added_tracks) + len(skipped_tracks),
        album_id,
    )

    return {
        "message": f"Added {len(added_tracks)} tracks, skipped {len(skipped_tracks)} existing",
        "added": [t["title"] for t in added_tracks],
        "skipped": skipped_tracks,
        "tracks": added_tracks,
    }


# Download Operations
@router.post("/albums/{album_id}/search-download")
async def search_and_download_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Search for an album torrent and add to download client
    """
    from app.services.automation.search_engine import search_engine
    from app.services.media_profile import media_profile_service

    # Get album from library
    album = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    # Get artist for search query
    artist = None
    if album["artist_id"]:
        artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", album["artist_id"])

    # Build search query
    artist_name = artist["name"] if artist else album.get("artist_name", "")
    album_title = album["title"]
    search_query = f"{artist_name} {album_title}"

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
    torrent_hash = await search_engine.search_music_and_download(
        query=search_query,
        profile=profile,
        save_path=album.get("root_folder_path"),
        tags=["music", artist_name],
    )

    if torrent_hash:
        # Update album status
        await conn.execute(
            "UPDATE albums SET status = 'downloading' WHERE id = $1",
            album_id,
        )
        return {
            "message": "Download started",
            "torrent_hash": torrent_hash,
            "query": search_query,
        }
    else:
        return {
            "message": "No suitable release found",
            "query": search_query,
        }


@router.post("/artists/{artist_id}/search-download-all")
async def search_and_download_discography(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Search and download all wanted albums for an artist
    """
    from app.services.automation.search_engine import search_engine
    from app.services.media_profile import media_profile_service, MediaProfile

    # Get artist from library
    artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)
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
        search_query = f"{artist['name']} {album['title']}"

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

        torrent_hash = await search_engine.search_music_and_download(
            query=search_query,
            profile=profile,
            save_path=album.get("root_folder_path") or artist.get("root_folder_path"),
            tags=["music", artist["name"]],
        )

        if torrent_hash:
            await conn.execute(
                "UPDATE albums SET status = 'downloading' WHERE id = $1",
                album["id"],
            )
            started.append({"album": album["title"], "hash": torrent_hash})
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
    """
    Monitor or unmonitor all albums for an artist
    """
    artist = await conn.fetchrow("SELECT id FROM artists WHERE id = $1", artist_id)
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
    """
    Update monitoring settings for an artist
    """
    artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    update_fields = []
    values = []
    param_count = 1

    if data.monitored is not None:
        update_fields.append(f"monitored = ${param_count}")
        values.append(data.monitored)
        param_count += 1

    if data.upgradeAllowed is not None:
        update_fields.append(f"upgrade_allowed = ${param_count}")
        values.append(data.upgradeAllowed)
        param_count += 1

    if not update_fields:
        return Artist(**dict(artist))

    values.append(artist_id)
    query = f"""
        UPDATE artists SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Artist(**dict(row))


@router.put("/albums/{album_id}/monitoring")
async def update_album_monitoring(
    album_id: int,
    data: MusicMonitoringUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update monitoring settings for an album
    """
    album = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    update_fields = []
    values = []
    param_count = 1

    if data.monitored is not None:
        update_fields.append(f"monitored = ${param_count}")
        values.append(data.monitored)
        param_count += 1

    if data.upgradeAllowed is not None:
        update_fields.append(f"upgrade_allowed = ${param_count}")
        values.append(data.upgradeAllowed)
        param_count += 1

    if not update_fields:
        return Album(**dict(album))

    values.append(album_id)
    query = f"""
        UPDATE albums SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Album(**dict(row))


# Delete with files
@router.delete("/artists/{artist_id}/delete")
async def delete_artist_with_files(
    artist_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete an artist and optionally their files from disk
    """
    artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    deleted_files = []
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
                    deleted_files.append(album["file_path"])
                except Exception as e:
                    errors.append(f"Failed to delete {album['file_path']}: {str(e)}")

        if artist["root_folder_path"] and os.path.exists(artist["root_folder_path"]):
            try:
                if os.path.isdir(artist["root_folder_path"]):
                    if not os.listdir(artist["root_folder_path"]):
                        os.rmdir(artist["root_folder_path"])
            except Exception as e:
                errors.append(f"Failed to remove artist folder: {str(e)}")

    await conn.execute("DELETE FROM artists WHERE id = $1", artist_id)

    return {
        "message": "Artist deleted successfully",
        "deleted_files": deleted_files,
        "errors": errors if errors else None,
    }


@router.delete("/albums/{album_id}/delete")
async def delete_album_with_files(
    album_id: int,
    delete_files: bool = Query(False, description="Also delete files from disk"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete an album and optionally its files from disk
    """
    album = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )

    deleted_files = []
    errors = []

    if delete_files and album["file_path"]:
        if os.path.exists(album["file_path"]):
            try:
                if os.path.isdir(album["file_path"]):
                    shutil.rmtree(album["file_path"])
                else:
                    os.remove(album["file_path"])
                deleted_files.append(album["file_path"])
            except Exception as e:
                errors.append(f"Failed to delete {album['file_path']}: {str(e)}")

    await conn.execute("DELETE FROM albums WHERE id = $1", album_id)

    return {
        "message": "Album deleted successfully",
        "deleted_files": deleted_files,
        "errors": errors if errors else None,
    }


# Refresh Metadata
@router.post("/artists/{artist_id}/refresh-metadata")
async def refresh_artist_metadata(
    artist_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Refresh artist metadata from Deezer
    """
    artist = await conn.fetchrow("SELECT * FROM artists WHERE id = $1", artist_id)
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
        deezer_data = await deezer_service.get_artist(artist["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch artist data from Deezer: {str(e)}",
        )

    if not deezer_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found on Deezer",
        )

    row = await conn.fetchrow(
        """
        UPDATE artists SET
            name = $1,
            picture = $2,
            picture_medium = $3,
            picture_big = $4,
            picture_xl = $5,
            nb_album = $6,
            nb_fan = $7,
            updated_at = NOW()
        WHERE id = $8
        RETURNING *
        """,
        deezer_data.get("name"),
        deezer_data.get("picture"),
        deezer_data.get("picture_medium"),
        deezer_data.get("picture_big"),
        deezer_data.get("picture_xl"),
        deezer_data.get("nb_album"),
        deezer_data.get("nb_fan"),
        artist_id,
    )

    return {
        "message": "Artist metadata refreshed successfully",
        "artist": Artist(**dict(row)),
    }


@router.post("/albums/{album_id}/refresh-metadata")
async def refresh_album_metadata(
    album_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Refresh album metadata from Deezer
    """
    album = await conn.fetchrow("SELECT * FROM albums WHERE id = $1", album_id)
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
        deezer_data = await deezer_service.get_album(album["deezer_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch album data from Deezer: {str(e)}",
        )

    if not deezer_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found on Deezer",
        )

    row = await conn.fetchrow(
        """
        UPDATE albums SET
            title = $1,
            cover = $2,
            cover_medium = $3,
            cover_big = $4,
            cover_xl = $5,
            release_date = $6,
            nb_tracks = $7,
            record_type = $8,
            upc = $9,
            updated_at = NOW()
        WHERE id = $10
        RETURNING *
        """,
        deezer_data.get("title"),
        deezer_data.get("cover"),
        deezer_data.get("cover_medium"),
        deezer_data.get("cover_big"),
        deezer_data.get("cover_xl"),
        parse_release_date(deezer_data.get("release_date")),
        deezer_data.get("nb_tracks"),
        deezer_data.get("record_type"),
        deezer_data.get("upc"),
        album_id,
    )

    return {
        "message": "Album metadata refreshed successfully",
        "album": Album(**dict(row)),
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
    """
    Get all albums for a specific artist with optional filtering
    """
    artist = await conn.fetchrow("SELECT id FROM artists WHERE id = $1", artist_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )

    query = "SELECT * FROM albums WHERE artist_id = $1"
    params = [artist_id]
    param_count = 2

    if record_type:
        query += f" AND record_type = ${param_count}"
        params.append(record_type)
        param_count += 1

    if monitored_only:
        query += " AND monitored = TRUE"

    query += " ORDER BY release_date DESC"

    rows = await conn.fetch(query, *params)
    return [Album(**dict(row)) for row in rows]
