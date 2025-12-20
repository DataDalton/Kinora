from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import httpx

from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.services.cloudflare.flaresolverr import flaresolverr
from app.core.config import settings


class LeetxIndexer(BaseIndexer):
    """
    1337x torrent indexer implementation
    Supports Cloudflare bypass via FlareSolverr
    """

    name = "1337x"
    base_url = "https://1337x.to"
    alternative_urls = [
        "https://1337x.st",
        "https://1337x.is",
        "https://x1337x.ws",
        "https://x1337x.eu",
        "https://x1337x.se",
    ]
    requires_cloudflare_bypass = True
    categories = {
        "movies": "Movies",
        "tv": "TV",
        "anime": "Anime",
        "documentaries": "Documentaries",
        "music": "Music",
    }

    def __init__(self):
        self.current_url = self.base_url
        self.bypass = flaresolverr if self.requires_cloudflare_bypass else None

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML from URL with Cloudflare bypass if needed
        """
        if self.requires_cloudflare_bypass and self.bypass:
            try:
                result = await self.bypass.get(url, max_timeout=30000)
                return result.get("solution", {}).get("response", "")
            except Exception as e:
                raise Exception(f"Failed to bypass Cloudflare for {url}: {str(e)}")
        else:
            async with httpx.AsyncClient(timeout=settings.INDEXER_REQUEST_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TorrentRelease]:
        """
        Search 1337x for torrents
        """
        releases = []

        category_path = self.categories.get(category, "") if category else ""
        search_url = f"{self.current_url}/search/{query.replace(' ', '+')}/{category_path}/1/"

        html = await self._fetch_html(search_url)
        soup = BeautifulSoup(html, "lxml")

        table = soup.find("table", class_="table-list")
        if not table:
            return releases

        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows[:limit]:
            try:
                release = await self._parse_search_result(row, category)
                if release:
                    releases.append(release)
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        return releases

    async def _parse_search_result(self, row, category: Optional[str] = None) -> Optional[TorrentRelease]:
        """
        Parse a search result row from 1337x
        """
        cols = row.find_all("td")
        if len(cols) < 5:
            return None

        # Title and link
        name_col = cols[0]
        link = name_col.find("a", href=True)
        if not link:
            return None

        title = link.text.strip()
        detail_url = f"{self.current_url}{link['href']}"

        # Seeders and leechers
        seeders = int(cols[1].text.strip()) if cols[1].text.strip().isdigit() else 0
        leechers = int(cols[2].text.strip()) if cols[2].text.strip().isdigit() else 0

        # Upload date
        date_str = cols[3].text.strip()
        upload_date = self._parse_date(date_str)

        # Size
        size_str = cols[4].text.strip()
        size_bytes = self.parse_size(size_str)

        # Uploader
        uploader = cols[5].text.strip() if len(cols) > 5 else None

        # Fetch magnet link (requires visiting detail page)
        magnet = await self._fetch_magnet(detail_url)

        # Parse quality info based on category
        if category == "music":
            music_info = self.parse_music_quality(title)
            return TorrentRelease(
                title=title,
                magnet=magnet,
                size=size_bytes,
                size_string=size_str,
                seeders=seeders,
                leechers=leechers,
                upload_date=upload_date,
                uploader=uploader,
                indexer=self.name,
                category=category,
                audio_format=music_info.get("audio_format"),
                audio_bitrate=music_info.get("audio_bitrate"),
                is_lossless=music_info.get("is_lossless", False),
                is_discography=music_info.get("is_discography", False),
                artist=music_info.get("artist"),
                album=music_info.get("album"),
                year=music_info.get("year"),
                release_group=music_info.get("release_group"),
                is_proper="PROPER" in title.upper(),
                is_repack="REPACK" in title.upper(),
            )
        else:
            quality_info = self.parse_quality(title)
            return TorrentRelease(
                title=title,
                magnet=magnet,
                size=size_bytes,
                size_string=size_str,
                seeders=seeders,
                leechers=leechers,
                upload_date=upload_date,
                uploader=uploader,
                indexer=self.name,
                category=category,
                quality=quality_info.get("quality"),
                codec=quality_info.get("codec"),
                source=quality_info.get("source"),
                audio=quality_info.get("audio"),
                audio_channels=quality_info.get("audio_channels"),
                hdr=quality_info.get("hdr"),
                edition=quality_info.get("edition"),
                language=quality_info.get("language"),
                release_group=quality_info.get("release_group"),
                is_proper="PROPER" in title.upper(),
                is_repack="REPACK" in title.upper(),
            )

    async def _fetch_magnet(self, detail_url: str) -> Optional[str]:
        """
        Fetch magnet link from torrent detail page
        """
        try:
            html = await self._fetch_html(detail_url)
            soup = BeautifulSoup(html, "lxml")

            magnet_link = soup.find("a", href=lambda x: x and x.startswith("magnet:"))
            if magnet_link:
                return magnet_link["href"]

        except Exception as e:
            print(f"Error fetching magnet from {detail_url}: {e}")

        return None

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """
        Get recent uploads from 1337x (RSS not directly supported, use trending instead)
        """
        releases = []

        try:
            category_path = self.categories.get(category, "movies") if category else "movies"
            trending_url = f"{self.current_url}/trending/d/{category_path}/"

            html = await self._fetch_html(trending_url)
            soup = BeautifulSoup(html, "lxml")

            table = soup.find("table", class_="table-list")
            if not table:
                return releases

            rows = table.find_all("tr")[1:]

            for row in rows[:50]:  # Limit to 50 recent items
                try:
                    release = await self._parse_search_result(row)
                    if release:
                        releases.append(release)
                except Exception:
                    continue

        except Exception as e:
            print(f"Error fetching RSS from 1337x: {e}")

        return releases

    async def test_connection(self) -> bool:
        """
        Test if 1337x is reachable
        """
        try:
            html = await self._fetch_html(self.current_url)
            return "1337x" in html.lower()
        except Exception:
            return await self._try_alternative_url()

    async def _try_alternative_url(self) -> bool:
        """
        Try alternative URLs if main URL is down
        """
        for alt_url in self.alternative_urls:
            try:
                html = await self._fetch_html(alt_url)
                if "1337x" in html.lower():
                    self.current_url = alt_url
                    return True
            except Exception:
                continue
        return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse 1337x date format (e.g., "Dec. 19th '23")
        """
        import re
        from datetime import datetime

        try:
            if "'" in date_str:
                match = re.search(r"(\w+)\.\s+(\d+)\w+\s+'(\d+)", date_str)
                if match:
                    month, day, year = match.groups()
                    year = "20" + year if len(year) == 2 else year
                    date_obj = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
                    return date_obj
        except Exception:
            pass

        return None


leetx_indexer = LeetxIndexer()
