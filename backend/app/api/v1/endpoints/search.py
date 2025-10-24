from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any
from app.schemas.movie import MovieSearch
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service

router = APIRouter()


@router.get("/")
async def search_media(
    query: str = Query(..., min_length=1),
    media_type: str = Query("all", regex="^(all|movie|show|anime)$"),
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
                "videos": details.get("videos", {}).get("results", []),
                "similar": details.get("similar", {}).get("results", [])[:6],
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
                "videos": details.get("videos", {}).get("results", []),
                "similar": details.get("similar", {}).get("results", [])[:6],
                "created_by": details.get("created_by", []),
                "media_type": "show"
            }

        elif media_type == "anime":
            details = await anilist_service.get_anime(media_id)
            parsed = anilist_service.parse_anime_data(details)

            title = details.get("title", {})
            anime_title = title.get("english") or title.get("romaji")

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
                "media_type": "anime"
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid media type. Must be 'movie', 'show', or 'anime'"
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
