from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncpg
from app.schemas.movie import MovieSearch
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.db import get_db, get_pool
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service
from app.services.automation.search_engine import search_engine
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.media_profile import MediaProfile
from app.services.torrent_validator import validate_and_resume_torrent
from app.services.folder_selector import folderSelector
from app.services.folder_health import folderHealthMonitor
from app.services.quality_definitions import (
    Resolution,
    Source,
    Codec,
    AudioCodec,
    AudioChannels,
    HDR,
)

router = APIRouter()


class InteractiveSearchRequest(BaseModel):
    query: str
    media_type: str
    media_id: int
    episode_id: Optional[int] = None
    indexers: Optional[List[str]] = None  # Which indexers to search (None = all available)
    quality: Optional[str] = None  # Quality to append to search query (e.g., "1080p")


class DownloadReleaseRequest(BaseModel):
    torrent_url: Optional[str] = None
    magnet_link: Optional[str] = None
    media_type: str
    media_id: int
    episode_id: Optional[int] = None
    indexer: Optional[str] = None
    indexer_page_url: Optional[str] = None
    quality: Optional[str] = None
    size: Optional[int] = None
    seeders: Optional[int] = None
    root_folder_id: Optional[int] = None  # Override folder selection


@router.get("/")
async def search_media(
    query: str = Query(..., min_length=1),
    media_type: str = Query("all", pattern="^(all|movie|show|anime|music)$"),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Search for media across TMDB and Anilist based on media type
    """
    results = []

    try:
        if media_type in ["all", "movie"]:
            movie_results = await tmdb_service.search_movie(query)
            for movie in movie_results:
                results.append({
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "name": movie.get("title"),
                    "original_title": movie.get("original_title"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path"),
                    "backdrop_path": movie.get("backdrop_path"),
                    "release_date": movie.get("release_date"),
                    "vote_average": movie.get("vote_average", 0),
                    "popularity": movie.get("popularity"),
                    "media_type": "movie"
                })

        if media_type in ["all", "show"]:
            show_results = await tmdb_service.search_tv(query)
            for show in show_results:
                results.append({
                    "id": show.get("id"),
                    "title": show.get("name"),
                    "name": show.get("name"),
                    "original_title": show.get("original_name"),
                    "overview": show.get("overview"),
                    "poster_path": show.get("poster_path"),
                    "backdrop_path": show.get("backdrop_path"),
                    "first_air_date": show.get("first_air_date"),
                    "vote_average": show.get("vote_average", 0),
                    "popularity": show.get("popularity"),
                    "media_type": "show"
                })

        if media_type in ["all", "anime"]:
            anime_results = await anilist_service.search_anime(query)
            for anime in anime_results:
                title = anime.get("title", {})
                anime_title = title.get("english") or title.get("romaji")

                start_date = anilist_service._parse_anilist_date(anime.get("startDate"))
                release_date_str = start_date.strftime("%Y-%m-%d") if start_date else None

                results.append({
                    "id": anime.get("id"),
                    "title": anime_title,
                    "name": anime_title,
                    "original_title": title.get("native"),
                    "overview": anime.get("description"),
                    "poster_path": anime.get("coverImage", {}).get("large"),
                    "backdrop_path": anime.get("bannerImage"),
                    "release_date": release_date_str,
                    "vote_average": anime.get("averageScore") / 10 if anime.get("averageScore") else 0,
                    "popularity": anime.get("popularity"),
                    "media_type": "anime",
                    "anilist_id": anime.get("id"),
                    "mal_id": anime.get("idMal")
                })

        if media_type in ["all", "music"]:
            album_results = await deezer_service.search_album(query, limit=10)
            for album in album_results:
                artist = album.get("artist", {})
                results.append({
                    "id": album.get("id"),
                    "title": album.get("title"),
                    "name": album.get("title"),
                    "overview": f"by {artist.get('name', 'Unknown Artist')}",
                    "poster_path": album.get("cover_xl") or album.get("cover_big") or album.get("cover_medium"),
                    "backdrop_path": album.get("cover_xl"),
                    "release_date": album.get("release_date"),
                    "vote_average": 0,
                    "popularity": 0,
                    "media_type": "album",
                    "deezer_id": album.get("id"),
                    "artist_name": artist.get("name"),
                    "artist_id": artist.get("id"),
                    "nb_tracks": album.get("nb_tracks")
                })

            track_results = await deezer_service.search_track(query, limit=10)
            for track in track_results:
                artist = track.get("artist", {})
                album = track.get("album", {})
                results.append({
                    "id": track.get("id"),
                    "title": track.get("title"),
                    "name": track.get("title"),
                    "overview": f"by {artist.get('name', 'Unknown Artist')}",
                    "poster_path": album.get("cover_xl") or album.get("cover_big") or album.get("cover_medium"),
                    "backdrop_path": album.get("cover_xl"),
                    "vote_average": 0,
                    "popularity": 0,
                    "media_type": "track",
                    "deezer_id": track.get("id"),
                    "artist_name": artist.get("name"),
                    "artist_id": artist.get("id"),
                    "album_name": album.get("title"),
                    "album_id": album.get("id"),
                    "duration": track.get("duration")
                })

            artist_results = await deezer_service.search_artist(query, limit=5)
            for artist in artist_results:
                results.append({
                    "id": artist.get("id"),
                    "title": artist.get("name"),
                    "name": artist.get("name"),
                    "overview": f"{artist.get('nb_album', 0)} albums",
                    "poster_path": artist.get("picture_xl") or artist.get("picture_big") or artist.get("picture_medium"),
                    "backdrop_path": artist.get("picture_xl"),
                    "vote_average": 0,
                    "popularity": 0,
                    "media_type": "artist",
                    "deezer_id": artist.get("id"),
                    "nb_album": artist.get("nb_album")
                })

        results.sort(key=lambda x: x.get("popularity", 0), reverse=True)

    except Exception as e:
        print(f"Search error: {e}")
        return []

    return results


@router.get("/details/{media_type}/{media_id}")
async def get_media_details(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get full details for a specific movie, show, or anime
    """
    try:
        if media_type == "movie":
            details = await tmdb_service.get_movie(media_id)
            parsed = tmdb_service.parse_movie_data(details)

            return {
                **parsed,
                "id": media_id,
                "name": details.get("title"),
                "tagline": details.get("tagline"),
                "runtime": details.get("runtime"),
                "budget": details.get("budget"),
                "revenue": details.get("revenue"),
                "vote_average": details.get("vote_average", 0),
                "vote_count": details.get("vote_count", 0),
                "cast": details.get("credits", {}).get("cast", [])[:10],
                "crew": details.get("credits", {}).get("crew", [])[:5],
                "recommendations": details.get("recommendations", {}).get("results", [])[:6],
                "media_type": "movie"
            }

        elif media_type == "show":
            details = await tmdb_service.get_tv(media_id)
            parsed = tmdb_service.parse_tv_data(details)

            return {
                **parsed,
                "id": media_id,
                "name": details.get("name"),
                "tagline": details.get("tagline", ""),
                "episode_run_time": details.get("episode_run_time", []),
                "vote_average": details.get("vote_average", 0),
                "vote_count": details.get("vote_count", 0),
                "cast": details.get("credits", {}).get("cast", [])[:10],
                "crew": details.get("credits", {}).get("crew", [])[:5],
                "recommendations": details.get("recommendations", {}).get("results", [])[:6],
                "created_by": details.get("created_by", []),
                "media_type": "show"
            }

        elif media_type == "anime":
            details = await anilist_service.get_anime(media_id)
            parsed = anilist_service.parse_anime_data(details)

            title = details.get("title", {})
            anime_title = title.get("english") or title.get("romaji")

            # Extract recommendations from Anilist format
            recommendations = []
            for rec_node in details.get("recommendations", {}).get("nodes", [])[:6]:
                media_rec = rec_node.get("mediaRecommendation")
                if media_rec:
                    rec_title = media_rec.get("title", {})
                    recommendations.append({
                        "id": media_rec.get("id"),
                        "title": rec_title.get("english") or rec_title.get("romaji"),
                        "name": rec_title.get("english") or rec_title.get("romaji"),
                        "poster_path": media_rec.get("coverImage", {}).get("large"),
                        "backdrop_path": media_rec.get("bannerImage"),
                    })

            return {
                **parsed,
                "id": media_id,
                "name": anime_title,
                "title": anime_title,
                "tagline": "",
                "vote_average": details.get("averageScore") / 10 if details.get("averageScore") else 0,
                "characters": details.get("characters", {}).get("nodes", [])[:10],
                "staff": details.get("staff", {}).get("nodes", [])[:5],
                "relations": details.get("relations", {}).get("nodes", [])[:6],
                "recommendations": recommendations,
                "media_type": "anime"
            }

        elif media_type == "artist":
            details = await deezer_service.get_artist(media_id)
            top_tracks = await deezer_service.get_artist_top_tracks(media_id, limit=10)
            albums = await deezer_service.get_artist_albums(media_id, limit=12)

            return {
                "id": media_id,
                "title": details.get("name"),
                "name": details.get("name"),
                "overview": f"{details.get('nb_album', 0)} albums • {details.get('nb_fan', 0):,} fans",
                "poster_path": details.get("picture_xl") or details.get("picture_big"),
                "backdrop_path": details.get("picture_xl"),
                "nb_fan": details.get("nb_fan", 0),
                "nb_album": details.get("nb_album", 0),
                "deezer_link": details.get("link"),
                "top_tracks": [
                    {
                        "id": track.get("id"),
                        "title": track.get("title"),
                        "duration": track.get("duration"),
                        "preview": track.get("preview"),
                        "album": track.get("album", {}),
                    }
                    for track in top_tracks
                ],
                "albums": [
                    {
                        "id": album.get("id"),
                        "title": album.get("title"),
                        "cover": album.get("cover_medium"),
                        "cover_xl": album.get("cover_xl"),
                        "release_date": album.get("release_date"),
                        "record_type": album.get("record_type"),
                    }
                    for album in albums
                ],
                "media_type": "artist"
            }

        elif media_type == "album":
            details = await deezer_service.get_album(media_id)
            artist = details.get("artist", {})
            genres = details.get("genres", {}).get("data", [])
            tracks = details.get("tracks", {}).get("data", [])

            return {
                "id": media_id,
                "title": details.get("title"),
                "name": details.get("title"),
                "overview": f"by {artist.get('name', 'Unknown Artist')}",
                "poster_path": details.get("cover_xl") or details.get("cover_big"),
                "backdrop_path": details.get("cover_xl"),
                "release_date": details.get("release_date"),
                "nb_tracks": details.get("nb_tracks"),
                "duration": details.get("duration"),
                "label": details.get("label"),
                "fans": details.get("fans", 0),
                "record_type": details.get("record_type"),
                "explicit_lyrics": details.get("explicit_lyrics", False),
                "artist": {
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "picture": artist.get("picture_medium"),
                    "picture_xl": artist.get("picture_xl"),
                },
                "genres": [{"id": g.get("id"), "name": g.get("name")} for g in genres],
                "tracks": [
                    {
                        "id": track.get("id"),
                        "title": track.get("title"),
                        "duration": track.get("duration"),
                        "track_position": track.get("track_position"),
                        "disk_number": track.get("disk_number"),
                        "preview": track.get("preview"),
                        "explicit_lyrics": track.get("explicit_lyrics", False),
                    }
                    for track in tracks
                ],
                "deezer_link": details.get("link"),
                "media_type": "album"
            }

        elif media_type == "track":
            details = await deezer_service.get_track(media_id)
            artist = details.get("artist", {})
            album = details.get("album", {})

            # Fetch album details to get release_date
            album_release_date = None
            if album.get("id"):
                try:
                    album_details = await deezer_service.get_album(album.get("id"))
                    album_release_date = album_details.get("release_date")
                except Exception:
                    pass

            return {
                "id": media_id,
                "title": details.get("title"),
                "name": details.get("title"),
                "overview": f"by {artist.get('name', 'Unknown Artist')}",
                "poster_path": album.get("cover_xl") or album.get("cover_big"),
                "backdrop_path": album.get("cover_xl"),
                "duration": details.get("duration"),
                "track_position": details.get("track_position"),
                "disk_number": details.get("disk_number"),
                "explicit_lyrics": details.get("explicit_lyrics", False),
                "preview": details.get("preview"),
                "isrc": details.get("isrc"),
                "release_date": album_release_date,
                "artist": {
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "picture": artist.get("picture_medium"),
                    "picture_xl": artist.get("picture_xl"),
                },
                "album": {
                    "id": album.get("id"),
                    "title": album.get("title"),
                    "cover": album.get("cover_medium"),
                    "cover_xl": album.get("cover_xl"),
                    "release_date": album_release_date,
                },
                "deezer_id": media_id,
                "media_type": "track"
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid media type. Must be 'movie', 'show', 'anime', 'artist', 'album', or 'track'"
            )

    except Exception as e:
        print(f"Error fetching media details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch details: {str(e)}"
        )


@router.get("/collection/{collection_id}")
async def get_collection_details(
    collection_id: int,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get collection details with all movies in the collection
    """
    try:
        collection_data = await tmdb_service.get_movie_collection(collection_id)

        return {
            "id": collection_data.get("id"),
            "name": collection_data.get("name"),
            "overview": collection_data.get("overview"),
            "poster_path": collection_data.get("poster_path"),
            "backdrop_path": collection_data.get("backdrop_path"),
            "parts": [
                {
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "release_date": movie.get("release_date"),
                    "poster_path": movie.get("poster_path"),
                    "overview": movie.get("overview")
                }
                for movie in collection_data.get("parts", [])
            ]
        }
    except Exception as e:
        print(f"Error fetching collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch collection: {str(e)}"
        )


@router.get("/torrents")
async def search_torrents(
    query: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    """
    Search indexers for torrents (placeholder)
    """
    return {"results": [], "indexers_searched": ["1337x", "yts"]}


@router.get("/options/{media_type}/{media_id}")
async def get_search_options(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get available search filter options and media's current profile settings.
    Returns all quality definitions and indexers from the search engine.
    """
    # All available quality options from definitions
    all_resolutions = [r.value for r in Resolution]
    all_sources = [s.value for s in Source]
    all_codecs = [c.value for c in Codec]
    all_audio_codecs = [a.value for a in AudioCodec]
    all_audio_channels = [a.value for a in AudioChannels]
    all_hdr = [h.value for h in HDR]

    # Get available indexers from the search engine based on media type
    if media_type == "anime":
        available_indexers = [idx.name for idx in search_engine.anime_indexers]
    elif media_type == "album":
        available_indexers = [idx.name for idx in search_engine.music_indexers]
    else:
        available_indexers = [idx.name for idx in search_engine.general_indexers]

    # Get the media item and its profile
    media_profile = None
    profile_resolutions = []
    profile_indexers = []

    try:
        if media_type == "movie":
            media = await conn.fetchrow(
                "SELECT media_profile_id FROM movies WHERE id = $1", media_id
            )
        elif media_type == "show":
            media = await conn.fetchrow(
                "SELECT media_profile_id FROM shows WHERE id = $1", media_id
            )
        elif media_type == "anime":
            media = await conn.fetchrow(
                "SELECT media_profile_id FROM anime WHERE id = $1", media_id
            )
        elif media_type == "album":
            media = await conn.fetchrow(
                "SELECT media_profile_id FROM albums WHERE id = $1", media_id
            )
        else:
            media = None

        if media and media.get("media_profile_id"):
            profile = await conn.fetchrow(
                "SELECT * FROM media_profiles WHERE id = $1",
                media["media_profile_id"]
            )
            if profile:
                media_profile = dict(profile)
                # Get media-type-specific resolutions or fall back to global
                res_field = f"{media_type}_resolutions"
                if media_type == "show":
                    res_field = "show_resolutions"
                profile_resolutions = profile.get(res_field) or profile.get("resolutions") or []

                # Get media-type-specific indexers or fall back to global
                idx_field = f"{media_type}_indexers"
                profile_indexers = profile.get(idx_field) or profile.get("indexers") or []

    except Exception as e:
        print(f"Error fetching media profile: {e}")

    return {
        "all_options": {
            "resolutions": all_resolutions,
            "sources": all_sources,
            "codecs": all_codecs,
            "audio_codecs": all_audio_codecs,
            "audio_channels": all_audio_channels,
            "hdr": all_hdr,
        },
        "available_indexers": available_indexers,
        "profile": {
            "id": media_profile.get("id") if media_profile else None,
            "name": media_profile.get("name") if media_profile else None,
            "resolutions": profile_resolutions,
            "indexers": profile_indexers,
        } if media_profile else None,
    }


@router.post("/interactive")
async def interactive_search(
    data: InteractiveSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search indexers for releases matching the query.
    Respects indexer selection and quality filters.
    """
    indexer_status = []
    all_releases = []

    # Build search query with optional quality filter
    search_query = data.query
    if data.quality and data.quality.lower() != "all":
        search_query = f"{data.query} {data.quality}"

    # Build indexer map from search engine's actual indexers
    indexer_map = {}
    for idx in search_engine.general_indexers:
        indexer_map[idx.name] = (idx, None)
    for idx in search_engine.anime_indexers:
        indexer_map[idx.name] = (idx, None)
    for idx in search_engine.music_indexers:
        if idx.name not in indexer_map:
            indexer_map[idx.name] = (idx, "music")

    # Determine default indexers based on media type
    if data.media_type == "anime":
        default_indexers = [idx.name for idx in search_engine.anime_indexers]
    elif data.media_type == "music" or data.media_type == "album":
        default_indexers = [idx.name for idx in search_engine.music_indexers]
        # Set music category for music indexers
        for idx in search_engine.music_indexers:
            indexer_map[idx.name] = (idx, "music")
    else:
        default_indexers = [idx.name for idx in search_engine.general_indexers]

    # Use selected indexers if provided, otherwise use defaults for media type
    selected_indexers = data.indexers if data.indexers else default_indexers

    # Filter to only valid indexers
    valid_indexers = [i for i in selected_indexers if i in indexer_map]

    # Search each selected indexer
    for indexer_name in valid_indexers:
        indexer, category = indexer_map.get(indexer_name, (None, None))
        if not indexer:
            continue

        try:
            releases = await indexer.search(search_query, category, limit=50)
            all_releases.extend(releases)
            indexer_status.append({
                "name": indexer_name,
                "status": "success",
                "count": len(releases),
            })
        except Exception as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if "FlareSolverr" in error_msg or "flaresolverr" in error_msg.lower():
                error_msg = "FlareSolverr not configured or unavailable"
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out"
            elif "connection" in error_msg.lower():
                error_msg = "Connection failed"

            indexer_status.append({
                "name": indexer_name,
                "status": "error",
                "error": error_msg,
                "count": 0,
            })
            print(f"Indexer {indexer_name} error: {e}")

    # Deduplicate by info_hash
    seen_hashes = set()
    unique_releases = []
    for release in all_releases:
        if release.info_hash and release.info_hash in seen_hashes:
            continue
        if release.info_hash:
            seen_hashes.add(release.info_hash)
        unique_releases.append(release)

    # Convert TorrentRelease objects to frontend format
    results = []
    for release in unique_releases:
        upload_date_str = ""
        if release.upload_date:
            upload_date_str = release.upload_date.isoformat()

        results.append({
            "title": release.title,
            "size": release.size or 0,
            "seeders": release.seeders,
            "leechers": release.leechers,
            "quality": release.quality or "Unknown",
            "source": release.source or "",
            "indexer": release.indexer,
            "indexer_page_url": "",
            "torrent_url": release.torrent_url or "",
            "magnet_link": release.magnet or "",
            "info_hash": release.info_hash or "",
            "upload_date": upload_date_str,
            "uploader": release.uploader or "",
        })

    # Sort by seeders descending
    results.sort(key=lambda x: x["seeders"], reverse=True)

    return {
        "results": results,
        "indexers": indexer_status,
    }


@router.post("/download-release")
async def download_release(
    data: DownloadReleaseRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Download a selected release from search results.
    Selects appropriate root folder and sends to qBittorrent.
    """
    try:
        # Get torrent source (prefer .torrent URL, fallback to magnet)
        torrent_source = data.torrent_url or data.magnet_link

        if not torrent_source:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No torrent URL or magnet link provided"
            )

        # Get qBittorrent client
        client = await get_qbittorrent_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Download client not configured or unavailable"
            )

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Map media type to table name and folder media type
            tableMap = {
                "movie": ("movies", "movies"),
                "show": ("shows", "shows"),
                "anime": ("anime", "anime"),
                "album": ("albums", "music"),
                "music": ("albums", "music"),
            }
            tableName, folderMediaType = tableMap.get(data.media_type, (None, None))

            # Get media item's assigned folder and profile
            mediaRootFolderId = None
            profile = None

            if tableName and data.media_id:
                mediaRow = await conn.fetchrow(
                    f"SELECT root_folder_id, media_profile_id FROM {tableName} WHERE id = $1",
                    data.media_id
                )
                if mediaRow:
                    mediaRootFolderId = mediaRow.get("root_folder_id")
                    if mediaRow.get("media_profile_id"):
                        profileRow = await conn.fetchrow(
                            "SELECT * FROM media_profiles WHERE id = $1",
                            mediaRow["media_profile_id"]
                        )
                        if profileRow:
                            profile = MediaProfile(**dict(profileRow))

            # Determine which folder to use:
            # 1. User override from request
            # 2. Media item's assigned folder
            # 3. Auto-select based on rules
            overrideFolderId = data.root_folder_id or mediaRootFolderId

            # Select folder using folder selector service
            folder = await folderSelector.selectFolder(
                conn,
                mediaType=folderMediaType or data.media_type,
                overrideFolderId=overrideFolderId
            )

            if not folder:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No active root folder configured for {data.media_type}"
                )

            # Check folder health before using
            if folder.get("health_status") == "error":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Root folder '{folder['name']}' is unhealthy: {folder.get('health_message', 'Unknown error')}"
                )

            # Add torrent paused with validating tag
            baseTags = ["kinora", "validating"]
            if data.indexer:
                baseTags.append(data.indexer)
            # Add folder identifier tag for traceability in qBittorrent
            baseTags.append(f"folder:{folder['id']}")

            # Use folder's paired download path for hardlink compatibility
            torrentHash = await client.add_torrent(
                torrent=torrent_source,
                save_path=folder["download_path"],
                category=data.media_type,
                tags=baseTags,
                paused=True,
            )

            # Record in download_history with folder assignment
            await conn.execute(
                """
                INSERT INTO download_history (
                    torrent_hash, media_type, media_id, episode_id, root_folder_id,
                    indexer, quality, size_bytes, status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'downloading', NOW())
                ON CONFLICT (torrent_hash) DO UPDATE SET
                    root_folder_id = $5,
                    updated_at = NOW()
                """,
                torrentHash,
                data.media_type,
                data.media_id,
                data.episode_id,
                folder["id"],
                data.indexer,
                data.quality,
                data.size,
            )

        # Trigger validation immediately after adding
        if profile:
            validationResult = await validate_and_resume_torrent(
                torrent_hash=torrentHash,
                client=client,
                profile=profile,
                media_type=data.media_type,
            )
            return {
                "success": True,
                "hash": torrentHash,
                "root_folder_id": folder["id"],
                "root_folder_name": folder["name"],
                "download_path": folder["download_path"],
                "message": f"Download queued to '{folder['name']}': {validationResult.message}"
            }
        else:
            # No profile found, resume without validation
            await client.remove_tags(torrentHash, ["validating"])
            await client.set_tags(torrentHash, ["validated"])
            await client.resume_torrent(torrentHash)
            return {
                "success": True,
                "hash": torrentHash,
                "root_folder_id": folder["id"],
                "root_folder_name": folder["name"],
                "download_path": folder["download_path"],
                "message": f"Download started to '{folder['name']}' (no profile for validation)"
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Download release error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start download: {str(e)}"
        )
