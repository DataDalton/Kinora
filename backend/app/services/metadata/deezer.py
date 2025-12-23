from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.cache import cache_get, cache_set, CACHE_TTL_LONG
from app.core.http_client import http_get


class DeezerService:
    """
    Deezer API service for fetching music metadata and discovery
    Public API with no authentication required for most endpoints
    """

    BASE_URL = "https://api.deezer.com"

    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a request to Deezer API with caching using shared HTTP client
        Music metadata is static so all requests use 6-hour cache TTL
        """
        if params is None:
            params = {}

        cache_key = f"deezer:{endpoint}:{str(params)}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        response = await http_get(f"{self.BASE_URL}/{endpoint}", params=params)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ValueError(f"Deezer API error: {data['error'].get('message', 'Unknown error')}")

        await cache_set(cache_key, data, expire=CACHE_TTL_LONG)
        return data

    async def search_artist(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search for artists by name
        """
        params = {"q": query, "limit": limit}
        data = await self._request("search/artist", params)
        return data.get("data", [])

    async def get_artist(self, artist_id: int) -> Dict[str, Any]:
        """
        Get detailed artist information
        """
        return await self._request(f"artist/{artist_id}")

    async def get_artist_top_tracks(self, artist_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get artist's top tracks
        """
        params = {"limit": limit}
        data = await self._request(f"artist/{artist_id}/top", params)
        return data.get("data", [])

    async def get_artist_albums(self, artist_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all albums from an artist
        """
        params = {"limit": limit}
        data = await self._request(f"artist/{artist_id}/albums", params)
        return data.get("data", [])

    async def search_album(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search for albums by title
        """
        params = {"q": query, "limit": limit}
        data = await self._request("search/album", params)
        return data.get("data", [])

    async def get_album(self, album_id: int) -> Dict[str, Any]:
        """
        Get detailed album information including tracks
        """
        return await self._request(f"album/{album_id}")

    async def search_track(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search for tracks by title
        """
        params = {"q": query, "limit": limit}
        data = await self._request("search/track", params)
        return data.get("data", [])

    async def get_track(self, track_id: int) -> Dict[str, Any]:
        """
        Get detailed track information
        """
        return await self._request(f"track/{track_id}")

    async def get_chart(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get global charts (top tracks, albums, artists)
        """
        params = {"limit": limit}
        return await self._request("chart", params)

    async def get_editorial_releases(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get editorial new releases
        """
        params = {"limit": limit}
        data = await self._request("editorial/0/releases", params)
        return data.get("data", [])

    async def get_genres(self) -> List[Dict[str, Any]]:
        """
        Get all music genres
        """
        data = await self._request("genre")
        return data.get("data", [])

    async def get_genre_artists(self, genre_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get top artists for a specific genre
        """
        params = {"limit": limit}
        data = await self._request(f"genre/{genre_id}/artists", params)
        return data.get("data", [])

    async def get_radio_tracks(self, artist_id: int, limit: int = 40) -> List[Dict[str, Any]]:
        """
        Get radio/similar tracks based on an artist
        """
        params = {"limit": limit}
        data = await self._request(f"artist/{artist_id}/radio", params)
        return data.get("data", [])

    def parse_artist_data(self, deezer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Deezer artist data into our database format
        """
        return {
            "name": deezer_data.get("name"),
            "picture": deezer_data.get("picture"),
            "picture_medium": deezer_data.get("picture_medium"),
            "picture_big": deezer_data.get("picture_big"),
            "picture_xl": deezer_data.get("picture_xl"),
            "deezer_id": deezer_data.get("id"),
            "nb_album": deezer_data.get("nb_album"),
            "nb_fan": deezer_data.get("nb_fan"),
        }

    def parse_album_data(self, deezer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Deezer album data into our database format
        """
        artist = deezer_data.get("artist", {})
        genres_data = deezer_data.get("genres", {}).get("data", [])

        return {
            "title": deezer_data.get("title"),
            "cover": deezer_data.get("cover"),
            "cover_medium": deezer_data.get("cover_medium"),
            "cover_big": deezer_data.get("cover_big"),
            "cover_xl": deezer_data.get("cover_xl"),
            "release_date": self._parse_date(deezer_data.get("release_date")),
            "deezer_id": deezer_data.get("id"),
            "upc": deezer_data.get("upc"),
            "nb_tracks": deezer_data.get("nb_tracks"),
            "duration": deezer_data.get("duration"),
            "label": deezer_data.get("label"),
            "explicit_lyrics": deezer_data.get("explicit_lyrics", False),
            "record_type": deezer_data.get("record_type"),
            "artist_name": artist.get("name") if artist else None,
            "genres": genres_data if genres_data else None,
        }

    def parse_track_data(self, deezer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Deezer track data into our database format
        """
        artist = deezer_data.get("artist", {})
        album = deezer_data.get("album", {})

        return {
            "title": deezer_data.get("title"),
            "duration": deezer_data.get("duration"),
            "track_position": deezer_data.get("track_position"),
            "disk_number": deezer_data.get("disk_number"),
            "deezer_id": deezer_data.get("id"),
            "isrc": deezer_data.get("isrc"),
            "explicit_lyrics": deezer_data.get("explicit_lyrics", False),
            "preview": deezer_data.get("preview"),
            "artist_name": artist.get("name") if artist else None,
            "album_title": album.get("title") if album else None,
        }

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse Deezer date string to datetime
        Deezer uses YYYY-MM-DD format
        """
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


deezer_service = DeezerService()
