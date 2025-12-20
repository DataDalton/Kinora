from typing import List, Optional
from datetime import datetime
import re
from bs4 import BeautifulSoup

from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.core.http_client import get_http_client


class NyaaIndexer(BaseIndexer):
    """
    Nyaa.si indexer for anime torrents
    Primary source for high-quality anime releases with fansubs
    """

    name = "Nyaa"
    base_url = "https://nyaa.si"
    alternative_urls = [
        "https://nyaa.land",
        "https://nyaa.iss.one",
        "https://nyaa.iss.ink",
    ]
    requires_cloudflare_bypass = False

    categories = {
        "anime": "1_0",  # Anime - All
        "anime_amv": "1_1",  # Anime - AMV
        "anime_english": "1_2",  # Anime - English-translated
        "anime_non_english": "1_3",  # Anime - Non-English-translated
        "anime_raw": "1_4",  # Anime - Raw
    }

    def __init__(self):
        pass

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TorrentRelease]:
        """
        Search Nyaa for anime torrents
        """
        cat = self.categories.get(category, self.categories["anime_english"])

        params = {
            "f": "0",  # No filter
            "c": cat,
            "q": query,
        }

        torrents = []
        current_url = self.base_url
        client = await get_http_client()

        for url in [self.base_url] + self.alternative_urls:
            try:
                response = await client.get(f"{url}/", params=params)
                if response.status_code == 200:
                    current_url = url
                    break
            except Exception:
                continue
        else:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("tr.default, tr.success, tr.danger")

        for row in rows[:limit]:
            try:
                torrent = self._parse_row(row, current_url)
                if torrent:
                    torrents.append(torrent)
            except Exception:
                continue

        return torrents

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """
        Get recent uploads from Nyaa RSS feed
        """
        cat = self.categories.get(category, self.categories["anime_english"])

        params = {
            "page": "rss",
            "c": cat,
        }

        torrents = []
        current_url = self.base_url
        client = await get_http_client()

        for url in [self.base_url] + self.alternative_urls:
            try:
                response = await client.get(f"{url}/", params=params)
                if response.status_code == 200:
                    current_url = url
                    break
            except Exception:
                continue
        else:
            return []

        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")

        for item in items:
            try:
                torrent = self._parse_rss_item(item, current_url)
                if torrent:
                    torrents.append(torrent)
            except Exception:
                continue

        return torrents

    async def test_connection(self) -> bool:
        """
        Test if Nyaa is reachable
        """
        client = await get_http_client()
        for url in [self.base_url] + self.alternative_urls:
            try:
                response = await client.get(f"{url}/", timeout=10.0)
                if response.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def _parse_row(self, row, base_url: str) -> Optional[TorrentRelease]:
        """
        Parse a table row from Nyaa search results
        """
        try:
            # Category column
            category_td = row.select_one("td:nth-of-type(1)")
            category = category_td.get("title", "").strip() if category_td else None

            # Title and links
            title_td = row.select_one("td:nth-of-type(2)")
            if not title_td:
                return None

            title_link = title_td.select_one("a:not(.comments)")
            if not title_link:
                return None

            title = title_link.get("title", title_link.text).strip()
            detail_url = base_url + title_link.get("href", "")

            # Torrent and magnet links
            links_td = row.select_one("td:nth-of-type(3)")
            torrent_link = links_td.select_one("a[href*='.torrent']") if links_td else None
            magnet_link = links_td.select_one("a[href^='magnet:']") if links_td else None

            torrent_url = base_url + torrent_link.get("href") if torrent_link else None
            magnet = magnet_link.get("href") if magnet_link else None

            # Extract info hash from magnet link
            info_hash = None
            if magnet:
                hash_match = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
                if hash_match:
                    info_hash = hash_match.group(1).upper()

            # Size
            size_td = row.select_one("td:nth-of-type(4)")
            size_string = size_td.text.strip() if size_td else None
            size = self.parse_size(size_string) if size_string else None

            # Upload date
            date_td = row.select_one("td:nth-of-type(5)")
            upload_date = self._parse_date(date_td.text.strip()) if date_td else None

            # Seeders
            seeders_td = row.select_one("td:nth-of-type(6)")
            seeders = int(seeders_td.text.strip()) if seeders_td and seeders_td.text.strip().isdigit() else 0

            # Leechers
            leechers_td = row.select_one("td:nth-of-type(7)")
            leechers = int(leechers_td.text.strip()) if leechers_td and leechers_td.text.strip().isdigit() else 0

            # Parse anime-specific quality info
            parsed = self._parse_anime_quality(title)

            return TorrentRelease(
                title=title,
                magnet=magnet,
                torrent_url=torrent_url,
                info_hash=info_hash,
                size=size,
                size_string=size_string,
                seeders=seeders,
                leechers=leechers,
                upload_date=upload_date,
                category=category,
                indexer=self.name,
                quality=parsed.get("quality"),
                codec=parsed.get("codec"),
                source=parsed.get("source"),
                audio=parsed.get("audio"),
                language=parsed.get("language"),
                release_group=parsed.get("release_group"),
                raw_data={
                    "detail_url": detail_url,
                    "subtitle_type": parsed.get("subtitle_type"),
                    "is_batch": parsed.get("is_batch"),
                    "audio_language": parsed.get("audio_language"),
                    "subtitle_language": parsed.get("subtitle_language"),
                },
            )

        except Exception:
            return None

    def _parse_rss_item(self, item, base_url: str) -> Optional[TorrentRelease]:
        """
        Parse an RSS item from Nyaa feed
        """
        try:
            title = item.find("title").text.strip()
            link = item.find("link").text.strip()

            # Get GUID which contains info hash
            guid = item.find("guid").text.strip()
            info_hash_match = re.search(r"/view/(\d+)", guid)

            # Size from description
            description = item.find("description").text if item.find("description") else ""
            size_match = re.search(r"(\d+\.?\d*\s*[KMGT]iB)", description)
            size_string = size_match.group(1) if size_match else None
            size = self.parse_size(size_string) if size_string else None

            # Seeders/Leechers from nyaa:seeders and nyaa:leechers tags
            seeders_tag = item.find("nyaa:seeders")
            leechers_tag = item.find("nyaa:leechers")
            seeders = int(seeders_tag.text) if seeders_tag and seeders_tag.text.isdigit() else 0
            leechers = int(leechers_tag.text) if leechers_tag and leechers_tag.text.isdigit() else 0

            # Publication date
            pub_date = item.find("pubDate")
            upload_date = self._parse_rss_date(pub_date.text) if pub_date else None

            # Parse anime-specific quality info
            parsed = self._parse_anime_quality(title)

            return TorrentRelease(
                title=title,
                magnet=None,  # RSS doesn't include magnet, need to fetch detail page
                torrent_url=link,
                info_hash=None,
                size=size,
                size_string=size_string,
                seeders=seeders,
                leechers=leechers,
                upload_date=upload_date,
                indexer=self.name,
                quality=parsed.get("quality"),
                codec=parsed.get("codec"),
                source=parsed.get("source"),
                audio=parsed.get("audio"),
                language=parsed.get("language"),
                release_group=parsed.get("release_group"),
                raw_data={
                    "detail_url": guid,
                    "subtitle_type": parsed.get("subtitle_type"),
                    "is_batch": parsed.get("is_batch"),
                    "audio_language": parsed.get("audio_language"),
                    "subtitle_language": parsed.get("subtitle_language"),
                },
            )

        except Exception:
            return None

    def _parse_anime_quality(self, title: str) -> dict:
        """
        Parse anime-specific quality information from title
        Detects: hardsub vs softsub, dual audio, dub vs sub, batch releases, fansub groups
        """
        title_upper = title.upper()

        # Use base quality parser
        parsed = self.parse_quality(title)

        # Detect audio and subtitle languages
        audio_language = None
        subtitle_language = None

        # Detect if it's a dub (English audio)
        is_dub = bool(re.search(r"\bDUB\b|\bDUBBED\b|\[DUB\]", title_upper))

        # Try to detect audio language from common patterns
        if "CHINESE" in title_upper or "MANDARIN" in title_upper or re.search(r"\[CH\]|\(CH\)", title_upper):
            audio_language = "zh"
        elif "KOREAN" in title_upper or re.search(r"\[KR\]|\(KR\)|K-", title_upper):
            audio_language = "ko"
        elif is_dub or "ENGLISH" in title_upper:
            audio_language = "en"
        else:
            # Default to Japanese for anime
            audio_language = "ja"

        # Try to detect subtitle language
        if re.search(r"\[ENG\]|\(ENG\)|ENGLISH.*SUB", title_upper):
            subtitle_language = "en"
        elif re.search(r"\[ESP\]|\(ESP\)|SPANISH.*SUB", title_upper):
            subtitle_language = "es"
        elif re.search(r"\[FRE\]|\(FRE\)|FRENCH.*SUB", title_upper):
            subtitle_language = "fr"
        elif re.search(r"\[GER\]|\(GER\)|GERMAN.*SUB", title_upper):
            subtitle_language = "de"
        elif re.search(r"\[CHI\]|\(CHI\)|CHINESE.*SUB", title_upper):
            subtitle_language = "zh"
        else:
            # Default to English subtitles if not raw
            if "RAW" not in title_upper:
                subtitle_language = "en"

        # Anime-specific subtitle detection
        subtitle_type = None
        if any(x in title_upper for x in ["SOFTSUB", "SOFT SUB", "[SOFTSUBS]", "SOFT SUBS"]):
            subtitle_type = "softsub"
        elif any(x in title_upper for x in ["HARDSUB", "HARD SUB", "[HARDSUBS]", "HARD SUBS"]):
            subtitle_type = "hardsub"
        elif any(x in title_upper for x in ["DUAL AUDIO", "DUAL-AUDIO", "DUALAUD", "DUAL.AUDIO"]):
            subtitle_type = "dual_audio"
            is_dub = True  # Dual audio includes dub
            is_sub = True  # And sub
        elif "RAW" in title_upper or "[RAW]" in title_upper:
            subtitle_type = "raw"
            is_sub = False
        else:
            # Default assumption: English fansubs are usually softsub
            if is_sub:
                subtitle_type = "softsub"
            else:
                subtitle_type = "hardsub"

        # Batch release detection
        is_batch = bool(re.search(r"BATCH|COMPLETE|\d+-\d+|\d+~\d+|SEASON", title_upper))

        # Parse release group from title (will be filtered by profile settings)
        release_group = parsed.get("release_group")

        parsed["subtitle_type"] = subtitle_type
        parsed["is_batch"] = is_batch
        parsed["is_dub"] = is_dub
        parsed["is_sub"] = is_sub
        parsed["release_group"] = release_group
        parsed["audio_language"] = audio_language
        parsed["subtitle_language"] = subtitle_language

        return parsed

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse Nyaa date format (e.g., "2024-01-15 12:30")
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except Exception:
            return None

    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse RSS pubDate format
        """
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            return None

