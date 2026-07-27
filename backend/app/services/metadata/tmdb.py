import json
import base64
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.cache import cacheGet, cacheSet, CACHE_TTL_SHORT, CACHE_TTL_LONG
from app.db import get_pool
from app.core.http_client import http_get
from app.services import metadata_cache


def getEncryptionKey() -> bytes:
    """Generate encryption key from SECRET_KEY for decrypting settings"""
    return base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())


def decryptValue(encryptedValue: str) -> str:
    """Decrypt a sensitive value from the database"""
    try:
        f = Fernet(getEncryptionKey())
        return f.decrypt(encryptedValue.encode()).decode()
    except Exception:
        return ""


class TMDBService:
    """
    TMDB API service for fetching movie and TV show metadata
    Priority: Database setting > Environment variable > Embedded default
    """

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

    def __init__(self):
        self.api_key = None

    async def _get_api_key(self) -> str:
        """
        Get TMDB API key with priority: Database > Environment > Embedded
        """
        if self.api_key:
            return self.api_key

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT value, is_encrypted FROM app_settings WHERE key = 'tmdb_api_key'
                """)
                if row and row["value"]:
                    value = row["value"]
                    if row["is_encrypted"]:
                        value = decryptValue(value)
                    if value:
                        self.api_key = value
                        return self.api_key
        except Exception as e:
            print(f"Error fetching TMDB API key from database: {e}")

        if settings.TMDB_API_KEY:
            self.api_key = settings.TMDB_API_KEY
            return self.api_key

        raise ValueError(
            "TMDB_API_KEY is required. Configure it in Settings page or set TMDB_API_KEY environment variable. "
            "Official Docker images have this embedded."
        )

    def _adaptive_ttl(self, endpoint: str, data: Dict[str, Any], default_ttl: int) -> int:
        """
        TTL tiered by content age for detail payloads. A movie released years ago
        never changes, so its details stay valid for days instead of an hour. An
        in-production show keeps the short TTL so new episodes appear promptly.
        """
        if endpoint.startswith("movie/") and isinstance(data.get("release_date"), str):
            return metadata_cache.tieredTtl(data.get("release_date"), default_ttl)
        if endpoint.startswith("tv/"):
            if data.get("in_production"):
                return default_ttl
            return metadata_cache.tieredTtl(data.get("last_air_date") or data.get("first_air_date"), default_ttl)
        return default_ttl

    async def _request(
        self, endpoint: str, params: Dict[str, Any] = None, ttl: int = CACHE_TTL_LONG
    ) -> Dict[str, Any]:
        """
        Make a request to TMDB API with two-tier caching: Dragonfly first, then the
        persistent metadata_cache table (survives restarts), then the network.
        A stale persistent row is served if TMDB itself is unreachable.
        ttl: Cache duration in seconds. Use CACHE_TTL_SHORT for detail pages, CACHE_TTL_LONG for lists/searches
        """
        if params is None:
            params = {}

        # Cache key excludes the API key so persisted entries survive key rotation.
        cache_key = f"tmdb:{endpoint}:{str(dict(sorted(params.items())))}"

        cached = await cacheGet(cache_key)
        if cached:
            return cached

        persisted = await metadata_cache.getFresh(cache_key)
        if persisted is not None:
            await cacheSet(cache_key, persisted, expire=ttl)
            return persisted

        api_key = await self._get_api_key()
        request_params = {**params, "api_key": api_key}

        try:
            response = await http_get(f"{self.BASE_URL}/{endpoint}", params=request_params)
            response.raise_for_status()
            data = response.json()
        except Exception:
            # Provider unreachable: an expired persistent row is better than an error.
            stale = await metadata_cache.getStale(cache_key)
            if stale is not None:
                return stale
            raise

        effective_ttl = self._adaptive_ttl(endpoint, data, ttl)
        await cacheSet(cache_key, data, expire=effective_ttl)
        await metadata_cache.setCached(cache_key, "tmdb", data, effective_ttl)
        return data

    async def search_movie(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for movies by title
        """
        params = {"query": query, "include_adult": False}
        if year:
            params["year"] = year

        data = await self._request("search/movie", params)
        return data.get("results", [])

    async def get_movie(self, tmdb_id: int) -> Dict[str, Any]:
        """
        Get detailed movie information
        """
        return await self._request(
            f"movie/{tmdb_id}", {"append_to_response": "credits,recommendations"}, ttl=CACHE_TTL_SHORT
        )

    async def search_tv(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for TV shows by title
        """
        params = {"query": query, "include_adult": False}
        if year:
            params["first_air_date_year"] = year

        data = await self._request("search/tv", params)
        return data.get("results", [])

    async def get_tv(self, tmdb_id: int) -> Dict[str, Any]:
        """
        Get detailed TV show information
        """
        return await self._request(
            f"tv/{tmdb_id}", {"append_to_response": "credits,recommendations"}, ttl=CACHE_TTL_SHORT
        )

    async def get_tv_season(self, tmdb_id: int, season_number: int) -> Dict[str, Any]:
        """
        Get TV show season details including episodes
        """
        return await self._request(f"tv/{tmdb_id}/season/{season_number}", ttl=CACHE_TTL_SHORT)

    async def get_trending(self, media_type: str = "all", time_window: str = "week") -> List[Dict[str, Any]]:
        """
        Get trending media (all, movie, tv)
        """
        data = await self._request(f"trending/{media_type}/{time_window}")
        return data.get("results", [])

    async def get_popular(self, media_type: str = "movie") -> List[Dict[str, Any]]:
        """
        Get popular movies or TV shows
        """
        data = await self._request(f"{media_type}/popular")
        return data.get("results", [])

    async def get_upcoming(self) -> List[Dict[str, Any]]:
        """
        Get upcoming movies
        """
        data = await self._request("movie/upcoming")
        return data.get("results", [])

    async def get_top_rated(self, media_type: str = "movie") -> List[Dict[str, Any]]:
        """
        Get top rated movies or TV shows
        """
        data = await self._request(f"{media_type}/top_rated")
        return data.get("results", [])

    async def discover_movies(
        self,
        sort_by: str = "popularity.desc",
        genres: Optional[List[int]] = None,
        year: Optional[int] = None,
        min_rating: Optional[float] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Discover movies with filters
        """
        params = {
            "sort_by": sort_by,
            "page": page,
            "include_adult": False,
        }

        if genres:
            params["with_genres"] = ",".join(map(str, genres))
        if year:
            params["primary_release_year"] = year
        if min_rating:
            params["vote_average.gte"] = min_rating

        return await self._request("discover/movie", params)

    async def discover_tv(
        self,
        sort_by: str = "popularity.desc",
        genres: Optional[List[int]] = None,
        year: Optional[int] = None,
        min_rating: Optional[float] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Discover TV shows with filters
        """
        params = {
            "sort_by": sort_by,
            "page": page,
            "include_adult": False,
        }

        if genres:
            params["with_genres"] = ",".join(map(str, genres))
        if year:
            params["first_air_date_year"] = year
        if min_rating:
            params["vote_average.gte"] = min_rating

        return await self._request("discover/tv", params)

    async def get_movie_collection(self, collection_id: int) -> Dict[str, Any]:
        """
        Get collection details (e.g., MCU, Star Wars)
        """
        return await self._request(f"collection/{collection_id}")

    def get_image_url(self, path: str, size: str = "original") -> str:
        """
        Generate full TMDB image URL
        Sizes: w92, w154, w185, w342, w500, w780, original
        """
        if not path:
            return ""
        return f"{self.IMAGE_BASE_URL}/{size}{path}"

    def _parse_genres(self, genres: list) -> list:
        """
        Extract genre names from TMDB genres list.
        Returns a list for JSONB storage (asyncpg handles serialization).
        """
        if not genres:
            return []
        return [g.get("name") for g in genres if g.get("name")]

    def parse_movie_data(self, tmdb_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse TMDB movie data into our database format.
        Returns native Python types for JSONB fields (asyncpg handles serialization).
        """
        return {
            "title": tmdb_data.get("title"),
            "original_title": tmdb_data.get("original_title"),
            "overview": tmdb_data.get("overview"),
            "poster_path": tmdb_data.get("poster_path"),
            "backdrop_path": tmdb_data.get("backdrop_path"),
            "release_date": self._parse_date(tmdb_data.get("release_date")),
            "genres": self._parse_genres(tmdb_data.get("genres", [])),
            "rating": tmdb_data.get("vote_average"),
            "vote_count": tmdb_data.get("vote_count"),
            "popularity": tmdb_data.get("popularity"),
            "tmdb_id": tmdb_data.get("id"),
            "imdb_id": tmdb_data.get("imdb_id") or tmdb_data.get("external_ids", {}).get("imdb_id"),
            "runtime": tmdb_data.get("runtime"),
            "tagline": tmdb_data.get("tagline"),
            "production_companies": tmdb_data.get("production_companies", []),
            "production_countries": tmdb_data.get("production_countries", []),
            "spoken_languages": tmdb_data.get("spoken_languages", []),
            "collection_id": (
                tmdb_data.get("belongs_to_collection", {}).get("id")
                if tmdb_data.get("belongs_to_collection")
                else None
            ),
            "collection_name": (
                tmdb_data.get("belongs_to_collection", {}).get("name")
                if tmdb_data.get("belongs_to_collection")
                else None
            ),
        }

    def parse_tv_data(self, tmdb_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse TMDB TV show data into our database format.
        Returns native Python types for JSONB fields (asyncpg handles serialization).
        """
        return {
            "title": tmdb_data.get("name"),
            "original_title": tmdb_data.get("original_name"),
            "overview": tmdb_data.get("overview"),
            "poster_path": tmdb_data.get("poster_path"),
            "backdrop_path": tmdb_data.get("backdrop_path"),
            "release_date": self._parse_date(tmdb_data.get("first_air_date")),
            "genres": self._parse_genres(tmdb_data.get("genres", [])),
            "rating": tmdb_data.get("vote_average"),
            "vote_count": tmdb_data.get("vote_count"),
            "popularity": tmdb_data.get("popularity"),
            "tmdb_id": tmdb_data.get("id"),
            "imdb_id": tmdb_data.get("external_ids", {}).get("imdb_id"),
            "tvdb_id": tmdb_data.get("external_ids", {}).get("tvdb_id"),
            "number_of_seasons": tmdb_data.get("number_of_seasons"),
            "number_of_episodes": tmdb_data.get("number_of_episodes"),
            "episode_run_time": tmdb_data.get("episode_run_time", []),
            "networks": tmdb_data.get("networks", []),
            "production_companies": tmdb_data.get("production_companies", []),
            "first_air_date": self._parse_date(tmdb_data.get("first_air_date")),
            "last_air_date": self._parse_date(tmdb_data.get("last_air_date")),
            "in_production": tmdb_data.get("in_production", False),
        }

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse TMDB date string to datetime
        """
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


tmdb_service = TMDBService()
