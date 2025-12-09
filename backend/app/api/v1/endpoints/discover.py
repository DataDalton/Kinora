from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service

router = APIRouter()


@router.get("/trending")
async def get_trending(
    media_type: str = "all",
    time_window: str = "week",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get trending media from TMDB
    """
    try:
        results = await tmdb_service.get_trending(media_type, time_window)

        formatted_results = []
        for item in results:
            item_type = item.get("media_type", media_type)
            formatted_results.append({
                "id": item.get("id"),
                "title": item.get("title") or item.get("name"),
                "name": item.get("name") or item.get("title"),
                "poster_path": item.get("poster_path"),
                "backdrop_path": item.get("backdrop_path"),
                "vote_average": item.get("vote_average", 0),
                "release_date": item.get("release_date"),
                "first_air_date": item.get("first_air_date"),
                "media_type": item_type
            })

        return {"results": formatted_results}
    except Exception as e:
        print(f"Error fetching trending: {e}")
        return {"results": []}


@router.get("/popular")
async def get_popular(
    media_type: str = "all",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get popular media from TMDB and Anilist
    """
    try:
        all_results = []

        if media_type in ["all", "movie"]:
            movie_results = await tmdb_service.get_popular("movie")
            for movie in movie_results:
                all_results.append({
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "name": movie.get("title"),
                    "poster_path": movie.get("poster_path"),
                    "backdrop_path": movie.get("backdrop_path"),
                    "vote_average": movie.get("vote_average", 0),
                    "release_date": movie.get("release_date"),
                    "media_type": "movie"
                })

        if media_type in ["all", "show", "tv"]:
            show_results = await tmdb_service.get_popular("tv")
            for show in show_results:
                all_results.append({
                    "id": show.get("id"),
                    "title": show.get("name"),
                    "name": show.get("name"),
                    "poster_path": show.get("poster_path"),
                    "backdrop_path": show.get("backdrop_path"),
                    "vote_average": show.get("vote_average", 0),
                    "first_air_date": show.get("first_air_date"),
                    "media_type": "show"
                })

        if media_type in ["all", "anime"]:
            anime_results = await anilist_service.get_trending(per_page=20)
            for anime in anime_results:
                title = anime.get("title", {})
                anime_title = title.get("english") or title.get("romaji")

                start_date = anilist_service._parse_anilist_date(anime.get("startDate"))
                release_date_str = start_date.strftime("%Y-%m-%d") if start_date else None

                all_results.append({
                    "id": anime.get("id"),
                    "title": anime_title,
                    "name": anime_title,
                    "poster_path": anime.get("coverImage", {}).get("large"),
                    "backdrop_path": anime.get("bannerImage"),
                    "vote_average": anime.get("averageScore") / 10 if anime.get("averageScore") else 0,
                    "release_date": release_date_str,
                    "media_type": "anime",
                    "anilist_id": anime.get("id")
                })

        all_results.sort(key=lambda x: x.get("vote_average", 0), reverse=True)

        return {"results": all_results}
    except Exception as e:
        print(f"Error fetching popular: {e}")
        return {"results": []}


@router.get("/upcoming")
async def get_upcoming(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get upcoming movie releases from TMDB
    """
    try:
        results = await tmdb_service.get_upcoming()

        formatted_results = []
        for movie in results:
            formatted_results.append({
                "id": movie.get("id"),
                "title": movie.get("title"),
                "name": movie.get("title"),
                "poster_path": movie.get("poster_path"),
                "backdrop_path": movie.get("backdrop_path"),
                "vote_average": movie.get("vote_average", 0),
                "release_date": movie.get("release_date"),
                "media_type": "movie"
            })

        return {"results": formatted_results}
    except Exception as e:
        print(f"Error fetching upcoming: {e}")
        return {"results": []}


@router.get("/top-rated")
async def get_top_rated(
    media_type: str = "all",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get top rated media from TMDB
    """
    try:
        all_results = []

        if media_type in ["all", "movie"]:
            movie_results = await tmdb_service.get_top_rated("movie")
            for movie in movie_results:
                all_results.append({
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "name": movie.get("title"),
                    "poster_path": movie.get("poster_path"),
                    "backdrop_path": movie.get("backdrop_path"),
                    "vote_average": movie.get("vote_average", 0),
                    "release_date": movie.get("release_date"),
                    "media_type": "movie"
                })

        if media_type in ["all", "show", "tv"]:
            show_results = await tmdb_service.get_top_rated("tv")
            for show in show_results:
                all_results.append({
                    "id": show.get("id"),
                    "title": show.get("name"),
                    "name": show.get("name"),
                    "poster_path": show.get("poster_path"),
                    "backdrop_path": show.get("backdrop_path"),
                    "vote_average": show.get("vote_average", 0),
                    "first_air_date": show.get("first_air_date"),
                    "media_type": "show"
                })

        return {"results": all_results}
    except Exception as e:
        print(f"Error fetching top rated: {e}")
        return {"results": []}


@router.get("/genre")
async def get_by_genre(
    genre: str,
    page: int = 1,
    sort_by: str = "popularity",
    media_type: str = "all",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get content by genre from TMDB and Anilist with pagination and sorting
    """
    genre_mapping = {
        "action": {"tmdb_movie": [28], "tmdb_tv": [10759], "anilist": "Action"},
        "comedy": {"tmdb_movie": [35], "tmdb_tv": [35], "anilist": "Comedy"},
        "drama": {"tmdb_movie": [18], "tmdb_tv": [18], "anilist": "Drama"},
        "scifi": {"tmdb_movie": [878], "tmdb_tv": [10765], "anilist": "Sci-Fi"},
        "horror": {"tmdb_movie": [27], "tmdb_tv": [9648, 80], "anilist": "Horror"},
        "romance": {"tmdb_movie": [10749], "tmdb_tv": [10749], "anilist": "Romance"}
    }

    sort_mapping = {
        "popularity": "popularity.desc",
        "rating": "vote_average.desc",
        "release_date": "release_date.desc",
        "title": "title.asc"
    }

    try:
        all_results = []
        genre_info = genre_mapping.get(genre.lower())

        if not genre_info:
            return {"results": []}

        movie_genre_ids = genre_info["tmdb_movie"]
        tv_genre_ids = genre_info["tmdb_tv"]
        anilist_genre = genre_info["anilist"]
        tmdb_sort = sort_mapping.get(sort_by, "popularity.desc")

        if media_type in ["all", "movie"]:
            movie_data = await tmdb_service.discover_movies(
                genres=movie_genre_ids,
                page=page,
                sort_by=tmdb_sort
            )
            for movie in movie_data.get("results", []):
                all_results.append({
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "name": movie.get("title"),
                    "poster_path": movie.get("poster_path"),
                    "backdrop_path": movie.get("backdrop_path"),
                    "vote_average": movie.get("vote_average", 0),
                    "release_date": movie.get("release_date"),
                    "media_type": "movie"
                })

        if media_type in ["all", "show", "tv"]:
            tv_data = await tmdb_service.discover_tv(
                genres=tv_genre_ids,
                page=page,
                sort_by=tmdb_sort
            )
            for show in tv_data.get("results", []):
                all_results.append({
                    "id": show.get("id"),
                    "title": show.get("name"),
                    "name": show.get("name"),
                    "poster_path": show.get("poster_path"),
                    "backdrop_path": show.get("backdrop_path"),
                    "vote_average": show.get("vote_average", 0),
                    "first_air_date": show.get("first_air_date"),
                    "media_type": "show"
                })

        if media_type in ["all", "anime"]:
            anime_results = await anilist_service.get_by_genre(
                anilist_genre,
                page=page,
                per_page=20
            )
            for anime in anime_results:
                title = anime.get("title", {})
                anime_title = title.get("english") or title.get("romaji")

                start_date = anilist_service._parse_anilist_date(anime.get("startDate"))
                release_date_str = start_date.strftime("%Y-%m-%d") if start_date else None

                all_results.append({
                    "id": anime.get("id"),
                    "title": anime_title,
                    "name": anime_title,
                    "poster_path": anime.get("coverImage", {}).get("large"),
                    "backdrop_path": anime.get("bannerImage"),
                    "vote_average": anime.get("averageScore") / 10 if anime.get("averageScore") else 0,
                    "release_date": release_date_str,
                    "media_type": "anime",
                    "anilist_id": anime.get("id")
                })

        if sort_by == "popularity":
            all_results.sort(key=lambda x: x.get("vote_average", 0) * (x.get("vote_count", 1) or 1), reverse=True)
        elif sort_by == "rating":
            all_results.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
        elif sort_by == "release_date":
            all_results.sort(key=lambda x: x.get("release_date") or x.get("first_air_date") or "", reverse=True)
        elif sort_by == "title":
            all_results.sort(key=lambda x: x.get("title", "").lower())

        return {"results": all_results[:20]}
    except Exception as e:
        print(f"Error fetching genre content: {e}")
        return {"results": []}


@router.get("/music/charts")
async def get_music_charts(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get global music charts from Deezer (top tracks, albums, artists)
    """
    try:
        charts = await deezer_service.get_chart(limit)

        return {
            "tracks": charts.get("tracks", {}).get("data", []),
            "albums": charts.get("albums", {}).get("data", []),
            "artists": charts.get("artists", {}).get("data", []),
        }
    except Exception as e:
        print(f"Error fetching music charts: {e}")
        return {"tracks": [], "albums": [], "artists": []}


@router.get("/music/new-releases")
async def get_music_new_releases(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get new music releases from Deezer editorial
    """
    try:
        releases = await deezer_service.get_editorial_releases(limit)

        formatted_results = []
        for album in releases:
            artist = album.get("artist", {})
            formatted_results.append({
                "id": album.get("id"),
                "title": album.get("title"),
                "cover": album.get("cover_medium"),
                "cover_xl": album.get("cover_xl"),
                "artist_name": artist.get("name") if artist else None,
                "artist_id": artist.get("id") if artist else None,
                "release_date": album.get("release_date"),
                "nb_tracks": album.get("nb_tracks"),
                "record_type": album.get("record_type"),
                "media_type": "music"
            })

        return {"results": formatted_results}
    except Exception as e:
        print(f"Error fetching new releases: {e}")
        return {"results": []}


@router.get("/music/genres")
async def get_music_genres(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get all available music genres from Deezer
    """
    try:
        genres = await deezer_service.get_genres()
        return {"results": genres}
    except Exception as e:
        print(f"Error fetching music genres: {e}")
        return {"results": []}


@router.get("/music/genre/{genre_id}")
async def get_music_by_genre(
    genre_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get top artists for a specific music genre
    """
    try:
        artists = await deezer_service.get_genre_artists(genre_id, limit)

        formatted_results = []
        for artist in artists:
            formatted_results.append({
                "id": artist.get("id"),
                "name": artist.get("name"),
                "picture": artist.get("picture_medium"),
                "picture_xl": artist.get("picture_xl"),
                "nb_album": artist.get("nb_album"),
                "nb_fan": artist.get("nb_fan"),
                "media_type": "music"
            })

        return {"results": formatted_results}
    except Exception as e:
        print(f"Error fetching genre artists: {e}")
        return {"results": []}
