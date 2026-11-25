from typing import List, Optional
from datetime import datetime

from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.core.config import settings
from app.core.http_client import indexer_get


class YTSIndexer(BaseIndexer):
    """
    YTS torrent indexer implementation
    Focuses on high-quality movie releases
    """

    name = "YTS"
    # Only the official site and the API host its own API names are used. Mirror domains
    # are often run by third parties, so an outage is reported rather than routed around.
    base_url = "https://yts.gg"
    api_url = "https://movies-api.accel.li/api/v2"
    requires_cloudflare_bypass = False
    categories = {
        "movies": "Movies",
    }

    def __init__(self):
        self.current_url = self.base_url
        self.current_api_url = self.api_url

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TorrentRelease]:
        """
        Search YTS for movie torrents using their API.
        Errors are raised so the search engine records them against the indexer's health.
        """
        response = await indexer_get(
            f"{self.current_api_url}/list_movies.json",
            params={
                "query_term": query,
                "limit": min(limit, 50),
                "sort_by": "seeds",
                "order_by": "desc",
            },
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            raise Exception(f"YTS API returned status {data.get('status')}: {data.get('status_message')}")

        releases = []
        for movie in data.get("data", {}).get("movies") or []:
            releases.extend(self._parse_movie(movie))
        return releases

    def _parse_movie(self, movie: dict) -> List[TorrentRelease]:
        """
        Parse YTS movie data into TorrentRelease objects
        YTS provides multiple quality options per movie
        """
        releases = []

        title_long = movie.get("title_long", "")
        year = movie.get("year", "")
        imdb_code = movie.get("imdb_code", "")
        rating = movie.get("rating", 0)
        upload_date = self._parse_date(movie.get("date_uploaded"))

        torrents = movie.get("torrents", [])

        for torrent in torrents:
            quality = torrent.get("quality", "")
            quality_type = torrent.get("type", "")
            size_bytes = torrent.get("size_bytes")
            size_string = torrent.get("size", "")
            seeders = torrent.get("seeds", 0)
            leechers = torrent.get("peers", 0)
            hash_value = torrent.get("hash", "")

            # Build magnet link
            magnet = self._build_magnet(hash_value, title_long) if hash_value else None

            # YTS uses x264 for 720p/1080p and x265 for 2160p
            codec = "x265" if quality == "2160p" else "x264"

            # Parse quality to standardized format
            quality_parsed = quality.lower() if quality else None

            # Build full title
            full_title = f"{title_long} [{quality}] [{quality_type}] [YTS]"

            release = TorrentRelease(
                origin_sites=["yts"],
                title=full_title,
                magnet=magnet,
                detail_url=movie.get("url"),
                info_hash=hash_value,
                size=size_bytes,
                size_string=size_string,
                seeders=seeders,
                leechers=leechers,
                upload_date=upload_date,
                uploader="YTS",
                category="Movies",
                indexer=self.name,
                quality=quality_parsed,
                codec=codec,
                source="BLURAY" if quality_type == "bluray" else "WEB-DL",
                audio="AAC",
                audio_channels="2.0",
                hdr=None,
                edition=None,
                language="en",
                release_group="YTS",
                raw_data={
                    "imdb_code": imdb_code,
                    "rating": rating,
                    "year": year,
                },
            )

            releases.append(release)

        return releases

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """
        Get recent uploads from YTS
        """
        releases = []

        try:
            response = await indexer_get(
                f"{self.current_api_url}/list_movies.json",
                params={
                    "limit": 50,
                    "sort_by": "date_added",
                    "order_by": "desc",
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                return releases

            movies = data.get("data", {}).get("movies", [])

            for movie in movies:
                releases.extend(self._parse_movie(movie))

        except Exception as e:
            print(f"Error fetching RSS from YTS: {e}")

        return releases

    async def test_connection(self) -> bool:
        """
        Test if YTS API is reachable
        """
        try:
            response = await indexer_get(f"{self.current_api_url}/list_movies.json?limit=1")
            data = response.json()
            return data.get("status") == "ok"
        except Exception:
            return False

    def _build_magnet(self, info_hash: str, title: str) -> str:
        """
        Build magnet link from info hash
        """
        trackers = [
            "udp://open.demonii.com:1337/announce",
            "udp://tracker.openbittorrent.com:80",
            "udp://tracker.coppersurfer.tk:6969",
            "udp://glotorrents.pw:6969/announce",
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://torrent.gresille.org:80/announce",
            "udp://p4p.arenabg.com:1337",
            "udp://tracker.leechers-paradise.org:6969",
        ]

        tracker_params = "&".join([f"tr={tracker}" for tracker in trackers])
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={title}&{tracker_params}"

        return magnet

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse YTS date format (e.g., "2023-12-19 10:30:45")
        """
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


yts_indexer = YTSIndexer()
