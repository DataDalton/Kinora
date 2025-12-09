from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Dict, Any
from app.schemas.movie import MovieSearch
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service

router = APIRouter()


@router.get("/")
async def search_media(
    query: str = Query(..., min_length=1),
    media_type: str = Query("all", regex="^(all|movie|show|anime|music)$"),
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
