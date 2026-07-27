import re
from typing import List, Optional, Dict
from datetime import datetime
from bs4 import BeautifulSoup

from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.services.cloudflare.flaresolverr import flaresolverr
from app.core.config import settings
from app.core.http_client import http_get


def _load_chrome_targets() -> Dict[int, str]:
    """Map each curl_cffi desktop Chrome major version to its impersonate token."""
    tokens: List[str] = []
    try:
        import typing
        from curl_cffi.requests.impersonate import BrowserTypeLiteral

        tokens = [t for t in typing.get_args(BrowserTypeLiteral) if isinstance(t, str)]
    except Exception:
        tokens = []
    if not tokens:
        # Fallback for curl_cffi 0.15.x if the literal cannot be enumerated.
        tokens = [
            "chrome99",
            "chrome100",
            "chrome101",
            "chrome104",
            "chrome107",
            "chrome110",
            "chrome116",
            "chrome119",
            "chrome120",
            "chrome123",
            "chrome124",
            "chrome131",
            "chrome133a",
            "chrome136",
            "chrome142",
            "chrome145",
            "chrome146",
        ]
    mapping: Dict[int, str] = {}
    for token in tokens:
        if "android" in token:
            continue
        match = re.fullmatch(r"chrome(\d+)[a-z]?", token)
        if match:
            mapping[int(match.group(1))] = token
    return mapping


_CHROME_TARGET_BY_VERSION = _load_chrome_targets()


def _impersonate_for_ua(user_agent: Optional[str]) -> str:
    """
    Pick the curl_cffi Chrome impersonation target closest to the FlareSolverr
    browser, so the TLS fingerprint matches the user-agent we send with the reused
    clearance cookie. curl_cffi ships a fixed set of Chrome profiles, so we choose the
    highest one at or below the browser's major version (or the highest available when
    the browser is newer than every profile).
    """
    default = "chrome"
    if not user_agent or not _CHROME_TARGET_BY_VERSION:
        return default
    match = re.search(r"Chrome/(\d+)", user_agent)
    if not match:
        return default
    major = int(match.group(1))
    versions = _CHROME_TARGET_BY_VERSION
    at_or_below = [v for v in versions if v <= major]
    chosen = max(at_or_below) if at_or_below else max(versions)
    return versions[chosen]


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
        # The cf_clearance value that failed the fast path, if any. Reuse is verified to
        # work, but if a cookie is ever rejected (different egress IP, stricter
        # challenge) we skip the fast path for that value until a fresh solve issues a
        # new one, so a broken reuse never costs more than one probe per cookie.
        self._fast_failed_clearance: Optional[str] = None

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML from URL with Cloudflare bypass if needed
        """
        if self.requires_cloudflare_bypass and self.bypass:
            # Fast path: reuse the Cloudflare clearance from a prior solve and fetch
            # with the impersonating HTTP client, skipping the browser entirely.
            fast = await self._fetch_fast(url)
            if fast is not None:
                return fast
            # Fall back to a full FlareSolverr solve, which refreshes the clearance.
            try:
                result = await self.bypass.get(url, max_timeout=30000)
                return result.get("solution", {}).get("response", "")
            except Exception as e:
                raise Exception(f"Failed to bypass Cloudflare for {url}: {str(e)}")
        else:
            response = await http_get(url, timeout=settings.INDEXER_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text

    async def _fetch_fast(self, url: str) -> Optional[str]:
        """
        Fetch a page reusing the cached Cloudflare clearance cookie and user-agent.
        Returns HTML on success, or None when there is no clearance yet or the response
        looks like a Cloudflare challenge, in which case the caller does a full solve.
        """
        cookies = getattr(self.bypass, "clearance_cookies", None)
        user_agent = getattr(self.bypass, "user_agent", None)
        if not cookies or not user_agent:
            return None

        clearance = cookies.get("cf_clearance")
        # Skip the fast path for a clearance value that already failed so we never pay
        # a wasted round trip before every solve. A fresh solve changes the value and
        # we probe again once.
        if clearance and clearance == self._fast_failed_clearance:
            return None

        try:
            from app.core.http_client import get_http_client

            client = await get_http_client()
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": self.current_url + "/",
            }
            response = await client.get(
                url,
                headers=headers,
                cookies=cookies,
                impersonate=_impersonate_for_ua(user_agent),
                timeout=15,
                allow_redirects=True,
            )
            markers = ("just a moment", "cf-chl", "challenge-platform", "checking your browser")
            if response.status_code != 200 or any(
                marker in (response.text or "")[:2000].lower() for marker in markers
            ):
                self._fast_failed_clearance = clearance
                return None
            return response.text
        except Exception:
            self._fast_failed_clearance = clearance
            return None

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

        # Title and link - 1337x has two links in name column: category icon and torrent name
        name_col = cols[0]
        links = name_col.find_all("a", href=True)
        # Get the second link (torrent name) if available, otherwise use the first
        link = links[1] if len(links) > 1 else (links[0] if links else None)
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

        # The magnet lives on the detail page. It is resolved on demand at download
        # time via ensure_download_source, not fetched for every search result, so a
        # search is a single page load instead of one fetch per row.
        magnet = None

        # Parse quality info based on category
        if category == "music":
            music_info = self.parse_music_quality(title)
            return TorrentRelease(
                title=title,
                magnet=magnet,
                detail_url=detail_url,
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
                bit_depth=music_info.get("bit_depth"),
                sample_rate=music_info.get("sample_rate"),
                quality_tier=music_info.get("quality_tier"),
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
                detail_url=detail_url,
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

    async def ensure_download_source(self, release: TorrentRelease) -> TorrentRelease:
        """Resolve the magnet from the detail page when it was deferred during search."""
        if not (release.magnet or release.torrent_url) and release.detail_url:
            release.magnet = await self._fetch_magnet(release.detail_url)
        return release

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

    # Pages fetched when the index has never seen this indexer (first run): a
    # bounded seed window instead of crawling the whole site.
    SEED_FEED_PAGES = 5
    # Runaway valve, not a coverage limit. Paging normally stops at the first page
    # that overlaps the index; this bound (50 pages = 1000 uploads per category per
    # cycle) only prevents a full-site crawl if overlap can never occur, for
    # example after the releases table is emptied mid-cycle.
    RUNAWAY_PAGE_LIMIT = 50

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """
        Get the newest uploads for a category. 1337x has no RSS feed, so this reads
        the category listing sorted by upload time descending, which is the actual
        new-uploads stream rather than the trending page.

        The listing serves 20 rows per page, so a fixed page count would miss
        uploads during bursts. Instead this pages until a page overlaps releases
        already present in the local index, meaning the gap since the previous
        cycle is fully covered, however deep it is. A first run seeds a bounded
        window, and an unreachable index stops paging conservatively.
        """
        from app.services import release_index

        releases = []

        try:
            category_path = self.categories.get(category, "Movies") if category else "Movies"

            seeded = await release_index.hasReleasesFromIndexer(self.name)
            if seeded is False:
                # First run: nothing to overlap with, seed a bounded window.
                max_pages = self.SEED_FEED_PAGES
            elif seeded is None:
                # Index unreachable: overlap cannot be detected, stay conservative.
                max_pages = 2
            else:
                max_pages = self.RUNAWAY_PAGE_LIMIT

            for page in range(1, max_pages + 1):
                latest_url = f"{self.current_url}/cat/{category_path}/time/desc/{page}/"

                html = await self._fetch_html(latest_url)
                soup = BeautifulSoup(html, "lxml")

                table = soup.find("table", class_="table-list")
                if not table:
                    break

                rows = table.find_all("tr")[1:]
                if not rows:
                    break

                page_releases = []
                for row in rows:
                    try:
                        release = await self._parse_search_result(row, category)
                        if release:
                            page_releases.append(release)
                    except Exception:
                        continue

                releases.extend(page_releases)

                # Any overlap with the index means this page reaches back into
                # already-seen territory, so the gap since the last cycle is closed.
                # None means the check itself failed, stop rather than run away.
                known = await release_index.knownKeys(page_releases)
                if known or known is None:
                    break

        except Exception as e:
            print(f"Error fetching new uploads from 1337x: {e}")

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
