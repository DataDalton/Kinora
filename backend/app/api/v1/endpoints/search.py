import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncpg
from app.api.v1.endpoints.auth import get_current_user, check_media_permission
from app.schemas.user import User
from app.services import download_episodes
from app.db import get_db, get_pool
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service
from app.services.automation.search_engine import search_engine
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.media_profile import MediaProfile
from app.services.torrent_validator import validate_and_resume_torrent
from app.services import hash_blocklist
from app.services import release_trust
from app.services.indexers.extto import extto_indexer
from app.services.indexers import search_context
from app.services.indexers.custom import registry as custom_indexers
from app.services.folder_selector import folderSelector
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
    # Not used by the search itself (results are query-based); optional so a search can
    # run before the item exists in the library.
    media_id: Optional[int] = None
    episode_id: Optional[int] = None
    indexers: Optional[List[str]] = None  # Which indexers to search (None = all available)
    quality: Optional[str] = None  # Quality to append to search query (e.g., "1080p")
    # When True, answer purely from the local release index without touching any
    # indexer. The modal fires this first for instant results while the live sweep
    # runs as a second request.
    local_only: bool = False
    # Profile whose safety template marks which results it allows. Falls back to the
    # media item's profile, then to allowing everything.
    profile_id: Optional[int] = None


class DownloadReleaseRequest(BaseModel):
    torrent_url: Optional[str] = None
    magnet_link: Optional[str] = None
    media_type: str
    media_id: int
    episode_id: Optional[int] = None
    indexer: Optional[str] = None
    indexer_page_url: Optional[str] = None
    title: Optional[str] = None
    quality: Optional[str] = None
    size: Optional[int] = None
    seeders: Optional[int] = None
    root_folder_id: Optional[int] = None  # Override folder selection
    keep_monitoring: Optional[bool] = None  # explicit satisfied/monitoring override
    # Trust details from the search result, recorded in download history.
    uploader: Optional[str] = None
    trust_category: Optional[str] = None
    origin_sites: Optional[List[str]] = None
    # Set when the user confirmed downloading a release the profile's template does not
    # allow. The confirmation is logged with the user's name.
    confirmed_outside_template: bool = False


_MANUAL_GRAB_TABLE = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums", "music": "albums"}


async def _apply_manual_grab_state(conn, data, profile):
    """
    After a manual grab: mark the item downloading (prevents the background searcher from
    double-grabbing) and set the satisfied/keep-monitoring default from whether the release
    meets the profile. Returns (meets_profile, monitoring_mode).
    """
    table = _MANUAL_GRAB_TABLE.get(data.media_type)
    if not table:
        return None, None

    await conn.execute(
        f"UPDATE {table} SET status = 'downloading', updated_at = NOW() WHERE id = $1",
        data.media_id,
    )

    meets = None
    monitoring = data.keep_monitoring
    if profile is not None and data.media_type in ("movie", "show", "anime"):
        from app.services.indexers.base import TorrentRelease
        from app.services.media_profile import media_profile_service

        release = TorrentRelease(
            title=data.title or "",
            quality=data.quality,
            size=data.size,
            seeders=data.seeders or 0,
        )
        meets = media_profile_service.score_release(release, profile, media_type=data.media_type) >= 0
        if monitoring is None:
            monitoring = not meets

    if monitoring is not None:
        await conn.execute(
            f"UPDATE {table} SET upgrade_allowed = $1 WHERE id = $2",
            monitoring,
            data.media_id,
        )
    return meets, monitoring


async def _searchMovies(query: str) -> List[Dict[str, Any]]:
    """Search TMDB movies and format for the combined search response."""
    movie_results = await tmdb_service.search_movie(query)
    return [
        {
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
            "media_type": "movie",
        }
        for movie in movie_results
    ]


async def _searchShows(query: str) -> List[Dict[str, Any]]:
    """Search TMDB TV shows and format for the combined search response."""
    show_results = await tmdb_service.search_tv(query)
    return [
        {
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
            "media_type": "show",
        }
        for show in show_results
    ]


async def _searchAnime(query: str) -> List[Dict[str, Any]]:
    """Search Anilist and format for the combined search response."""
    anime_results = await anilist_service.search_anime(query)
    results = []
    for anime in anime_results:
        title = anime.get("title", {})
        anime_title = title.get("english") or title.get("romaji")

        start_date = anilist_service._parse_anilist_date(anime.get("startDate"))
        release_date_str = start_date.strftime("%Y-%m-%d") if start_date else None

        results.append(
            {
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
                "mal_id": anime.get("idMal"),
            }
        )
    return results


async def _searchDeezerAlbums(query: str) -> List[Dict[str, Any]]:
    """Search Deezer albums and format for the combined search response."""
    album_results = await deezer_service.search_album(query, limit=10)
    results = []
    for album in album_results:
        artist = album.get("artist", {})
        results.append(
            {
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
                "nb_tracks": album.get("nb_tracks"),
            }
        )
    return results


async def _searchDeezerTracks(query: str) -> List[Dict[str, Any]]:
    """Search Deezer tracks and format for the combined search response."""
    track_results = await deezer_service.search_track(query, limit=10)
    results = []
    for track in track_results:
        artist = track.get("artist", {})
        album = track.get("album", {})
        results.append(
            {
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
                "duration": track.get("duration"),
            }
        )
    return results


async def _searchDeezerArtists(query: str) -> List[Dict[str, Any]]:
    """Search Deezer artists and format for the combined search response."""
    artist_results = await deezer_service.search_artist(query, limit=5)
    return [
        {
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
            "nb_album": artist.get("nb_album"),
        }
        for artist in artist_results
    ]


async def _prefetch_top_details(results: List[Dict[str, Any]]) -> None:
    """
    Warm the detail caches for the top visible search results so opening one of
    them answers locally. Runs after the response is sent; every fetch goes
    through the normal cached service methods, so already-warm items cost nothing.
    """
    try:
        movie_ids = [r["id"] for r in results if r.get("media_type") == "movie" and r.get("id")][:5]
        show_ids = [r["id"] for r in results if r.get("media_type") == "show" and r.get("id")][:5]
        anime_ids = [r["id"] for r in results if r.get("media_type") == "anime" and r.get("id")][:3]

        fetchers = (
            [tmdb_service.get_movie(mid) for mid in movie_ids]
            + [tmdb_service.get_tv(sid) for sid in show_ids]
            + [anilist_service.get_anime(aid) for aid in anime_ids]
        )
        if fetchers:
            await asyncio.gather(*fetchers, return_exceptions=True)
    except Exception as e:
        print(f"Detail prefetch error: {e}")


@router.get("/")
async def search_media(
    background_tasks: BackgroundTasks,
    query: str = Query(..., min_length=1),
    media_type: str = Query("all", pattern="^(all|movie|show|anime|music)$"),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Search for media across TMDB, Anilist, and Deezer based on media type.
    All provider calls run concurrently, and a failing provider is skipped
    instead of blanking the whole response.
    """
    fetchers = []
    if media_type in ["all", "movie"]:
        fetchers.append(_searchMovies(query))
    if media_type in ["all", "show"]:
        fetchers.append(_searchShows(query))
    if media_type in ["all", "anime"]:
        fetchers.append(_searchAnime(query))
    if media_type in ["all", "music"]:
        fetchers.append(_searchDeezerAlbums(query))
        fetchers.append(_searchDeezerTracks(query))
        fetchers.append(_searchDeezerArtists(query))

    provider_results = await asyncio.gather(*fetchers, return_exceptions=True)

    results: List[Dict[str, Any]] = []
    for provider_result in provider_results:
        if isinstance(provider_result, Exception):
            print(f"Search provider error: {provider_result}")
            continue
        results.extend(provider_result)

    results.sort(key=lambda x: x.get("popularity", 0) or 0, reverse=True)

    # One hop ahead: warm detail caches for the results the user is looking at.
    background_tasks.add_task(_prefetch_top_details, results)

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
                "media_type": "movie",
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
                "media_type": "show",
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
                    recommendations.append(
                        {
                            "id": media_rec.get("id"),
                            "title": rec_title.get("english") or rec_title.get("romaji"),
                            "name": rec_title.get("english") or rec_title.get("romaji"),
                            "poster_path": media_rec.get("coverImage", {}).get("large"),
                            "backdrop_path": media_rec.get("bannerImage"),
                        }
                    )

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
                "media_type": "anime",
            }

        elif media_type == "artist":
            details, top_tracks, albums = await asyncio.gather(
                deezer_service.get_artist(media_id),
                deezer_service.get_artist_top_tracks(media_id, limit=10),
                deezer_service.get_artist_albums(media_id, limit=12),
            )

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
                "media_type": "artist",
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
                "media_type": "album",
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
                "media_type": "track",
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid media type. Must be 'movie', 'show', 'anime', 'artist', 'album', or 'track'",
            )

    except Exception as e:
        print(f"Error fetching media details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch details: {str(e)}"
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
                    "overview": movie.get("overview"),
                }
                for movie in collection_data.get("parts", [])
            ],
        }
    except Exception as e:
        print(f"Error fetching collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch collection: {str(e)}"
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
    profile_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get available search filter options and the relevant profile settings.
    Returns all quality definitions and indexers from the search engine. When profile_id
    is given, that profile is used directly (media_id may be 0), which lets a search that
    is not yet tied to a library item still honor a chosen profile's indexers/resolutions.
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
        available_indexers = [idx.name for idx in search_engine.anime_indexers] + [extto_indexer.name]
    elif media_type == "album":
        available_indexers = [idx.name for idx in search_engine.music_indexers] + [extto_indexer.name]
    elif media_type in ("show", "episode"):
        available_indexers = [idx.name for idx in search_engine.show_indexers] + [extto_indexer.name]
    else:
        available_indexers = [idx.name for idx in search_engine.general_indexers] + [extto_indexer.name]
    # User-defined indexers enabled for search that cover this media type.
    await custom_indexers.ensureLoaded()
    available_indexers += [idx.name for idx in custom_indexers.searchIndexers(search_context.scopeFor(media_type))]

    # Get the media item and its profile
    media_profile = None
    profile_resolutions = []
    profile_indexers = []

    try:
        # A caller-supplied profile_id wins (used before an item exists). Otherwise the
        # profile comes from the media item's assignment.
        resolved_profile_id = profile_id
        if resolved_profile_id is None:
            if media_type == "movie":
                media = await conn.fetchrow("SELECT media_profile_id FROM movies WHERE id = $1", media_id)
            elif media_type == "show":
                media = await conn.fetchrow("SELECT media_profile_id FROM shows WHERE id = $1", media_id)
            elif media_type == "anime":
                media = await conn.fetchrow("SELECT media_profile_id FROM anime WHERE id = $1", media_id)
            elif media_type == "album":
                media = await conn.fetchrow("SELECT media_profile_id FROM albums WHERE id = $1", media_id)
            else:
                media = None
            if media and media.get("media_profile_id"):
                resolved_profile_id = media["media_profile_id"]

        if resolved_profile_id:
            profile = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", resolved_profile_id)
            if profile:
                media_profile = dict(profile)
                # Get media-type-specific resolutions
                res_field = f"{media_type}_resolutions"
                profile_resolutions = profile.get(res_field) or []

                # Get media-type-specific indexers
                idx_field = f"{media_type}_indexers"
                profile_indexers = profile.get(idx_field) or []

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
        "profile": (
            {
                "id": media_profile.get("id") if media_profile else None,
                "name": media_profile.get("name") if media_profile else None,
                "resolutions": profile_resolutions,
                "indexers": profile_indexers,
            }
            if media_profile
            else None
        ),
    }


def _format_interactive_release(release, from_cache: bool = False, template: Optional[str] = None) -> Dict[str, Any]:
    """Convert a TorrentRelease into the interactive search response shape, with its trust details."""
    upload_date_str = ""
    if release.upload_date:
        upload_date_str = release.upload_date.isoformat()

    last_seen_at = ""
    if isinstance(release.raw_data, dict):
        last_seen_at = release.raw_data.get("last_seen_at") or ""
    allowed, reason = release_trust.isAllowed(release, template)

    return {
        "title": release.title,
        "size": release.size or 0,
        "seeders": release.seeders,
        "leechers": release.leechers,
        "quality": release.quality or "Unknown",
        "source": release.source or "",
        "indexer": release.indexer,
        "indexer_page_url": release.detail_url or "",
        "torrent_url": release.torrent_url or "",
        "magnet_link": release.magnet or "",
        "info_hash": release.info_hash or "",
        "upload_date": upload_date_str,
        "uploader": release.uploader or "",
        "from_cache": from_cache,
        "last_seen_at": last_seen_at,
        "uploader_badge": release.uploader_badge,
        "origin_sites": list(release.origin_sites or []),
        "trust_category": release.trust_category,
        "trust_label": release_trust.CATEGORY_LABELS.get(release.trust_category, "Unverified"),
        "allowed_by_template": allowed,
        "template_reason": reason,
    }


@router.post("/interactive")
async def interactive_search(
    data: InteractiveSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Search for releases matching the query. With local_only, answers instantly from
    the local release index. Otherwise runs a live sweep of the selected indexers in
    parallel, persists everything seen into the index, and merges in any additional
    index-only rows so the response is a superset of both.
    """
    from app.services import release_index

    indexer_status = []
    all_releases = []
    template = await _template_for_search(data.profile_id, data.media_type, data.media_id)

    # The quality filter is a text token for the live keyword sweep, but a
    # structured column filter for the local index, where ingest parsing already
    # normalized "4K"/"UHD" titles to 2160p. The local pass therefore returns
    # releases the literal keyword search cannot.
    quality_filter = data.quality if data.quality and data.quality.lower() != "all" else None
    search_query = f"{data.query} {quality_filter}" if quality_filter else data.query

    # Instant local pass. No indexer round trips, no FlareSolverr. Honors an
    # explicit indexer selection so a filtered search never shows rows from
    # deselected indexers.
    if data.local_only:
        local_releases = await release_index.searchLocal(
            data.query, media_type=data.media_type, limit=100, quality=quality_filter
        )
        if data.indexers:
            allowed_indexers = set(data.indexers)
            local_releases = [r for r in local_releases if r.indexer in allowed_indexers]
        local_releases = await release_trust.annotate(local_releases)
        local_results = [_format_interactive_release(r, from_cache=True, template=template) for r in local_releases]
        local_results.sort(key=lambda x: x["seeders"], reverse=True)
        return {
            "results": local_results,
            "indexers": [{"name": "Local index", "status": "success", "count": len(local_results)}],
            "source": "local",
        }

    # Build indexer map from search engine's actual indexers
    indexer_map = {}
    for idx in search_engine.general_indexers:
        indexer_map[idx.name] = (idx, None)
    for idx in search_engine.anime_indexers:
        indexer_map[idx.name] = (idx, None)
    for idx in search_engine.music_indexers:
        if idx.name not in indexer_map:
            indexer_map[idx.name] = (idx, "music")
    # ext.to is searched only when chosen, for every media type.
    indexer_map[extto_indexer.name] = (extto_indexer, "music" if data.media_type in ("music", "album") else None)

    # Determine default indexers based on media type
    if data.media_type == "anime":
        default_indexers = [idx.name for idx in search_engine.anime_indexers]
    elif data.media_type == "music" or data.media_type == "album":
        default_indexers = [idx.name for idx in search_engine.music_indexers]
        # Set music category for music indexers
        for idx in search_engine.music_indexers:
            indexer_map[idx.name] = (idx, "music")
    elif data.media_type in ("show", "episode"):
        default_indexers = [idx.name for idx in search_engine.show_indexers]
    else:
        default_indexers = [idx.name for idx in search_engine.general_indexers]

    # User-defined indexers enabled for search that cover this media type are searched
    # by default, like the built-in indexers of that type.
    await custom_indexers.ensureLoaded()
    for idx in custom_indexers.searchIndexers(search_context.scopeFor(data.media_type)):
        indexer_map[idx.name] = (idx, "music" if data.media_type in ("music", "album") else None)
        default_indexers.append(idx.name)

    # Use selected indexers if provided, otherwise use defaults for media type
    selected_indexers = data.indexers if data.indexers else default_indexers

    # Filter to only valid indexers
    valid_indexers = [i for i in selected_indexers if i in indexer_map]

    # Search all selected indexers concurrently. Results stay live (no cache), the
    # total wait is the slowest indexer instead of the sum of all of them. The item's
    # ids go to indexers that search by id.
    search_tasks = [
        indexer_map[indexer_name][0].search(search_query, indexer_map[indexer_name][1], limit=50)
        for indexer_name in valid_indexers
    ]
    from app.services import release_matching

    itemContext = await search_context.forItem(None, data.media_type, data.media_id)
    season, episode = release_matching.seasonEpisodeFromQuery(data.query)
    if season is not None:
        itemContext.season = season
        itemContext.episode = episode
        itemContext.singleEpisode = episode is not None
    with search_context.using(itemContext):
        search_outcomes = await asyncio.gather(*search_tasks, return_exceptions=True)

    for indexer_name, outcome in zip(valid_indexers, search_outcomes):
        if isinstance(outcome, Exception):
            error_msg = str(outcome)
            # Provide user-friendly error messages
            if "FlareSolverr" in error_msg or "flaresolverr" in error_msg.lower():
                error_msg = "FlareSolverr not configured or unavailable"
            elif "timeout" in error_msg.lower():
                error_msg = "Request timed out"
            elif "connection" in error_msg.lower():
                error_msg = "Connection failed"

            indexer_status.append(
                {
                    "name": indexer_name,
                    "status": "error",
                    "error": error_msg,
                    "count": 0,
                }
            )
            print(f"Indexer {indexer_name} error: {outcome}")
            continue

        all_releases.extend(outcome)
        indexer_status.append(
            {
                "name": indexer_name,
                "status": "success",
                "count": len(outcome),
            }
        )

    # Merge copies of one torrent found through several indexers and set trust.
    unique_releases = await release_trust.annotate(all_releases)

    # Persist the live sweep into the local index.
    await release_index.upsertReleases(unique_releases)

    # Merge in index rows the live sweep did not return (from a failed indexer, an
    # earlier RSS pull, or a prior search), so the response never loses a known
    # release. Live rows win on identity collisions.
    live_keys = {release_index.dedupeKey(r) for r in unique_releases}
    local_releases = await release_index.searchLocal(
        data.query, media_type=data.media_type, limit=100, quality=quality_filter
    )
    if data.indexers:
        allowed_indexers = set(data.indexers)
        local_releases = [r for r in local_releases if r.indexer in allowed_indexers]
    index_extras = await release_trust.annotate(
        [r for r in local_releases if release_index.dedupeKey(r) not in live_keys]
    )

    results = [_format_interactive_release(r, from_cache=False, template=template) for r in unique_releases]
    results.extend(_format_interactive_release(r, from_cache=True, template=template) for r in index_extras)

    # Sort by seeders descending
    results.sort(key=lambda x: x["seeders"], reverse=True)

    return {
        "results": results,
        "indexers": indexer_status,
        "source": "live",
        "safety_template": template,
    }


async def _template_for_search(profile_id: Optional[int], media_type: Optional[str], media_id: Optional[int]):
    """The safety template of the chosen profile, or of the media item's profile, or None."""
    from app.db import get_pool

    table = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums", "music": "albums"}.get(
        media_type or ""
    )
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if profile_id:
                return await conn.fetchval("SELECT safety_template FROM media_profiles WHERE id = $1", profile_id)
            if table and media_id:
                return await conn.fetchval(
                    f"SELECT mp.safety_template FROM {table} m JOIN media_profiles mp ON mp.id = m.media_profile_id "
                    f"WHERE m.id = $1",
                    media_id,
                )
    except Exception as e:
        print(f"Could not read the safety template for search: {e}")
    return None


class SiteCheckRequest(BaseModel):
    """An ext.to search result to read every listed site for."""

    indexer: str
    indexer_page_url: str
    title: Optional[str] = None
    uploader: Optional[str] = None
    uploader_badge: Optional[str] = None
    origin_sites: List[str] = []
    profile_id: Optional[int] = None
    media_type: Optional[str] = None
    media_id: Optional[int] = None


@router.post("/check-sites")
async def check_release_sites(
    data: SiteCheckRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Read every site an ext.to release is listed on from its detail page, and whether the
    profile's safety template allows the release with that list. A search result names
    only the first site, so a release outside Balanced can turn out to be allowed. Only
    ext.to detail pages are read. Requires the same download permission as downloading
    the release, such as movies.download.
    """
    from app.services import release_index
    from app.services.indexers.base import TorrentRelease

    check_media_permission(current_user, data.media_type, "download")
    if data.indexer != extto_indexer.name or not data.indexer_page_url.startswith(extto_indexer.base_url + "/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only ext.to releases list more sites")
    release = TorrentRelease(
        title=data.title or "",
        indexer=extto_indexer.name,
        detail_url=data.indexer_page_url,
        uploader=data.uploader,
        uploader_badge=data.uploader_badge,
        origin_sites=list(data.origin_sites),
    )
    await release_trust.annotate([release])
    try:
        await extto_indexer.refresh_sites(release)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not read the ext.to page: {e}")
    await release_index.addOriginSites(release.indexer, release.detail_url, release.origin_sites)
    template = await _template_for_search(data.profile_id, data.media_type, data.media_id)
    allowed, reason = release_trust.isAllowed(release, template)
    return {
        "origin_sites": list(release.origin_sites),
        "trust_category": release.trust_category,
        "trust_label": release_trust.CATEGORY_LABELS.get(release.trust_category, "Unverified"),
        "allowed_by_template": allowed,
        "template_reason": reason,
    }


@router.post("/download-release")
async def download_release(
    data: DownloadReleaseRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Download a selected release from search results.
    Selects appropriate root folder and sends to qBittorrent. Requires the download
    permission for the release's media type, such as movies.download.
    """
    check_media_permission(current_user, data.media_type, "download")
    try:
        # Get torrent source (prefer .torrent URL, fallback to magnet)
        torrent_source = data.torrent_url or data.magnet_link

        # The magnet is deferred at search time for indexers that need a detail-page
        # fetch (1337x). Resolve it now from the release's detail page, and persist it
        # on the request so the download_history row can re-add the torrent later.
        if not torrent_source and data.indexer_page_url:
            from app.services.automation.search_engine import search_engine
            from app.services.indexers.base import TorrentRelease

            release = TorrentRelease(
                title=data.title or "",
                indexer=data.indexer or "",
                detail_url=data.indexer_page_url,
            )
            await search_engine.resolve_download_source(release)
            if release.magnet and not data.magnet_link:
                data.magnet_link = release.magnet
            if release.torrent_url and not data.torrent_url:
                data.torrent_url = release.torrent_url
            torrent_source = data.torrent_url or data.magnet_link

        if not torrent_source:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No torrent URL or magnet link provided"
            )

        # Get qBittorrent client
        client = await get_qbittorrent_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Download client not configured or unavailable"
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
                    f"SELECT root_folder_id, media_profile_id FROM {tableName} WHERE id = $1", data.media_id
                )
                if mediaRow:
                    mediaRootFolderId = mediaRow.get("root_folder_id")
                    if mediaRow.get("media_profile_id"):
                        profileRow = await conn.fetchrow(
                            "SELECT * FROM media_profiles WHERE id = $1", mediaRow["media_profile_id"]
                        )
                        if profileRow:
                            profile = MediaProfile.from_row(dict(profileRow))

            # Determine which folder to use:
            # 1. User override from request
            # 2. Media item's assigned folder
            # 3. Auto-select based on rules
            overrideFolderId = data.root_folder_id or mediaRootFolderId

            # Select folder using folder selector service
            folder = await folderSelector.selectFolder(
                conn, mediaType=folderMediaType or data.media_type, overrideFolderId=overrideFolderId
            )

            if not folder:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No active root folder configured for {data.media_type}",
                )

            # Check folder health before using
            if folder.get("health_status") == "error":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Root folder '{folder['name']}' is unhealthy: {folder.get('health_message', 'Unknown error')}",
                )

            # Free-space preflight: refuse the grab if the release would push the
            # download folder below the configured minimum free space.
            try:
                import shutil as _shutil
                from app.services.seeding import get_global_seed_defaults

                seedDefaults = await get_global_seed_defaults()
                automation = seedDefaults.get("automation", {})
                if automation.get("disk_pause_enabled") and data.size:
                    usage = _shutil.disk_usage(folder["download_path"])
                    minFree = automation.get("disk_min_free_gb", 10) * (1024**3)
                    if usage.free < data.size + minFree:
                        raise HTTPException(
                            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                            detail=(
                                f"Not enough free space in '{folder['name']}' for this release "
                                f"(needs {data.size // (1024**3)} GB, keeping {automation.get('disk_min_free_gb', 10)} GB free)"
                            ),
                        )
            except HTTPException:
                raise
            except Exception as preflightError:
                print(f"Free-space preflight skipped: {preflightError}")

            if await hash_blocklist.isHashBlocked(
                conn, hash_blocklist.infoHashFromSource(data.magnet_link), data.media_type, data.media_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This torrent is blocklisted because it failed validation before",
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

            # torrent_title and indexer are NOT NULL, so resolve a name from the client
            # and fall back for a request that omits the indexer.
            torrentInfo = await client.get_torrent(torrentHash)
            torrentTitle = (
                data.title
                or (torrentInfo.name if torrentInfo and torrentInfo.name else None)
                or f"{data.media_type} #{data.media_id}"
            )

            # Record in download_history with folder assignment and manual grab mode. The
            # magnet/.torrent source and info hash are stored so it can be re-added later.
            await conn.execute(
                """
                INSERT INTO download_history (
                    torrent_hash, media_type, media_id, episode_id, root_folder_id,
                    torrent_title, indexer, quality, size, magnet_link, torrent_url,
                    info_hash, indexer_page_url, grab_mode, status, created_at,
                    uploader, trust_category, safety_template, origin_sites
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 'manual', 'downloading', NOW(),
                    $14, $15, $16, $17
                )
                ON CONFLICT (torrent_hash) DO UPDATE SET
                    root_folder_id = $5,
                    torrent_title = EXCLUDED.torrent_title,
                    magnet_link = COALESCE(EXCLUDED.magnet_link, download_history.magnet_link),
                    torrent_url = COALESCE(EXCLUDED.torrent_url, download_history.torrent_url),
                    info_hash = COALESCE(EXCLUDED.info_hash, download_history.info_hash),
                    indexer_page_url = COALESCE(EXCLUDED.indexer_page_url, download_history.indexer_page_url),
                    grab_mode = 'manual',
                    uploader = EXCLUDED.uploader,
                    trust_category = EXCLUDED.trust_category,
                    safety_template = EXCLUDED.safety_template,
                    origin_sites = EXCLUDED.origin_sites,
                    updated_at = NOW()
                """,
                torrentHash,
                data.media_type,
                data.media_id,
                data.episode_id,
                folder["id"],
                torrentTitle,
                data.indexer or "unknown",
                data.quality,
                data.size,
                data.magnet_link,
                data.torrent_url,
                torrentHash,
                data.indexer_page_url,
                data.uploader,
                data.trust_category,
                getattr(profile, "safety_template", None) if profile else None,
                data.origin_sites or [],
            )
            await download_episodes.recordCoveredEpisodes(
                conn, torrentHash, data.media_type, data.media_id, torrentTitle, data.episode_id
            )
            if data.confirmed_outside_template:
                print(
                    f"Manual download outside the safety template confirmed by "
                    f"{getattr(current_user, 'username', 'unknown user')}: {torrentTitle}"
                )

            # Fix double-grab: mark the item as downloading so the background searcher
            # does not grab it again. Also set the satisfied/keep-monitoring default from
            # whether the grabbed release meets the profile.
            meetsProfile, monitoringMode = await _apply_manual_grab_state(conn, data, profile)

        # Validate immediately after adding. An item with no profile is checked with the
        # built-in default rules, so no manual download skips validation.
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
            "meets_profile": meetsProfile,
            "monitoring_mode": (
                "satisfied" if monitoringMode is False else ("monitoring" if monitoringMode else None)
            ),
            "message": f"Download queued to '{folder['name']}': {validationResult.message}",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Download release error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start download: {str(e)}"
        )
