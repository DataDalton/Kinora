"""
ext.to indexer.

ext.to aggregates many sites (1337x, ThePirateBay, EZTV, YTS, Nyaa, RARBG and regional
trackers) and adds uploads made directly to it. Each search result names the first site
the torrent is listed on, the uploader shown there, and ext.to's Trusted Uploader badge
for accounts ext.to has verified. Which of these a profile accepts is decided by its
safety template (see release_trust), not here.

Pages sit behind Cloudflare, so they are fetched through FlareSolverr, reusing its
clearance cookies with an impersonating HTTP client when they are still valid. Searches
read up to three result pages, because single episodes are often pushed past the first
page by season packs and movies. Magnets come from the detail page through ext.to's
signed magnet request, and only for the release being downloaded.
"""

import asyncio
import hashlib
import re
import time
from datetime import datetime
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.core.http_client import get_http_client, indexer_request_kwargs
from app.services import release_trust
from app.services.cloudflare.flaresolverr import flaresolverr
from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.services.indexers.leetx import _impersonate_for_ua

# Result pages read per search. Each holds up to RESULTS_PER_PAGE rows.
SEARCH_PAGES = 3
RESULTS_PER_PAGE = 50
# Minimum seconds between two requests to ext.to from one process, so a backlog of
# searches never floods the site.
REQUEST_INTERVAL_SECONDS = 1.5
# How long the site list read from a detail page is reused, and how many pages are kept.
DETAIL_CACHE_SECONDS = 3600
DETAIL_CACHE_ENTRIES = 500

_challengeMarkers = ("just a moment", "cf-chl", "challenge-platform", "checking your browser")
_torrentIdPattern = re.compile(r"-(\d+)/?$")


class ExtToIndexer(BaseIndexer):
    """Searches ext.to and resolves magnets through its signed magnet request."""

    name = "ext.to"
    base_url = "https://ext.to"
    requires_cloudflare_bypass = True
    categories = {"movies": "Movies", "tv": "TV", "anime": "Anime", "music": "Music"}

    def __init__(self):
        self.current_url = self.base_url
        self.bypass = flaresolverr
        self._fast_failed_clearance: Optional[str] = None
        self._lastRequestAt = 0.0
        self._paceLock: Optional[asyncio.Lock] = None
        self._paceLockLoop = None
        # Detail page URL to (read time, sites listed on the page).
        self._detailSites: Dict[str, Tuple[float, List[str]]] = {}

    def _lock(self) -> asyncio.Lock:
        """A pacing lock bound to the running loop, since Celery and FastAPI use separate loops."""
        loop = asyncio.get_running_loop()
        if self._paceLock is None or self._paceLockLoop is not loop:
            self._paceLock = asyncio.Lock()
            self._paceLockLoop = loop
        return self._paceLock

    async def _pace(self) -> None:
        async with self._lock():
            wait = self._lastRequestAt + REQUEST_INTERVAL_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._lastRequestAt = time.monotonic()

    async def _fetch_html(self, url: str) -> str:
        """Fetch a page, reusing the Cloudflare clearance when possible and solving again when not."""
        await self._pace()
        fast = await self._fetch_fast(url)
        if fast is not None:
            return fast
        await self._pace()
        try:
            result = await self.bypass.get(url, max_timeout=30000)
            return result.get("solution", {}).get("response", "")
        except Exception as e:
            raise Exception(f"Failed to bypass Cloudflare for {url}: {e}")

    def _clearance(self, url: str):
        cookies = self.bypass.clearance_for(url) if hasattr(self.bypass, "clearance_for") else {}
        return cookies, getattr(self.bypass, "user_agent", None)

    async def _fetch_fast(self, url: str) -> Optional[str]:
        """Fetch with the cached clearance cookies, or None when there are none or they were rejected."""
        cookies, user_agent = self._clearance(url)
        if not cookies or not user_agent:
            return None
        clearance = cookies.get("cf_clearance")
        if clearance and clearance == self._fast_failed_clearance:
            return None
        try:
            client = await get_http_client()
            response = await client.get(
                url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": self.current_url + "/",
                },
                cookies=cookies,
                **indexer_request_kwargs(
                    impersonate=_impersonate_for_ua(user_agent), timeout=20, allow_redirects=True
                ),
            )
            if response.status_code != 200 or any(
                m in (response.text or "")[:2000].lower() for m in _challengeMarkers
            ):
                self._fast_failed_clearance = clearance
                return None
            return response.text
        except Exception:
            self._fast_failed_clearance = clearance
            return None

    async def search(self, query: str, category: Optional[str] = None, limit: int = 100) -> List[TorrentRelease]:
        """Read up to SEARCH_PAGES result pages for the query, stopping at the first short page."""
        releases: List[TorrentRelease] = []
        for page in range(1, SEARCH_PAGES + 1):
            url = f"{self.current_url}/browse/?q={quote_plus(query)}" + (f"&page={page}" if page > 1 else "")
            html = await self._fetch_html(url)
            pageReleases = self._parse_rows(html, category)
            releases.extend(pageReleases)
            if len(pageReleases) < RESULTS_PER_PAGE:
                break
        return releases

    @staticmethod
    def _cell_value(cell):
        spans = cell.select("span")
        return spans[-1] if spans else cell

    @staticmethod
    def _count(cell) -> int:
        text = ExtToIndexer._cell_value(cell).get_text(strip=True).replace(",", "")
        return int(text) if text.isdigit() else 0

    @staticmethod
    def _parse_age(cell) -> Optional[datetime]:
        stamp = (ExtToIndexer._cell_value(cell).get("title") or "").strip()
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
            try:
                return datetime.strptime(stamp, pattern)
            except ValueError:
                continue
        return None

    def _parse_rows(self, html: str, category: Optional[str]) -> List[TorrentRelease]:
        soup = BeautifulSoup(html or "", "html.parser")
        releases = []
        for row in soup.select("table tr"):
            link = row.select_one("a.torrent-title-link")
            cells = row.find_all("td", recursive=False)
            if not link or len(cells) < 6:
                continue
            try:
                releases.append(self._parse_row(row, link, cells, category))
            except Exception as e:
                print(f"ext.to: could not parse a result row: {e}")
        return [r for r in releases if r]

    def _parse_row(self, row, link, cells, category: Optional[str]) -> Optional[TorrentRelease]:
        tooltip = link.get("data-tooltip")
        title = re.sub(r"<[^>]+>", "", tooltip).strip() if tooltip else link.get_text(" ", strip=True)
        href = link.get("href") or ""
        if not title or not href:
            return None
        posted = row.select_one(".related-posted")
        verified = posted.select_one(".is-verified-uploader") if posted else None
        external = posted.select_one(".external-user") if posted else None
        uploaderTag = verified or external
        sourceIcon = row.select_one(".source-link-tor img")
        site = release_trust.canonicalSite(PurePosixPath(sourceIcon.get("src") or "").stem) if sourceIcon else None
        sizeString = self._cell_value(cells[1]).get_text(strip=True)
        common = dict(
            title=title,
            detail_url=self.current_url + href,
            size=self.parse_size(sizeString),
            size_string=sizeString,
            seeders=self._count(cells[4]),
            leechers=self._count(cells[5]),
            upload_date=self._parse_age(cells[3]),
            uploader=uploaderTag.get_text(strip=True) if uploaderTag else None,
            uploader_badge="ext_verified" if verified else None,
            origin_sites=[site] if site else [],
            indexer=self.name,
            category=category,
            is_proper="PROPER" in title.upper(),
            is_repack="REPACK" in title.upper(),
        )
        if category == "music":
            music = self.parse_music_quality(title)
            return TorrentRelease(
                **common,
                audio_format=music.get("audio_format"),
                audio_bitrate=music.get("audio_bitrate"),
                bit_depth=music.get("bit_depth"),
                sample_rate=music.get("sample_rate"),
                quality_tier=music.get("quality_tier"),
                is_lossless=music.get("is_lossless", False),
                is_discography=music.get("is_discography", False),
                artist=music.get("artist"),
                album=music.get("album"),
                year=music.get("year"),
                release_group=music.get("release_group"),
            )
        quality = self.parse_quality(title)
        return TorrentRelease(
            **common,
            quality=quality.get("quality"),
            codec=quality.get("codec"),
            source=quality.get("source"),
            audio=quality.get("audio"),
            audio_channels=quality.get("audio_channels"),
            hdr=quality.get("hdr"),
            edition=quality.get("edition"),
            language=quality.get("language"),
            release_group=quality.get("release_group"),
        )

    @staticmethod
    def _sites_on_detail_page(html: str) -> List[str]:
        """Every site a detail page lists the torrent on, from the source icons in its header."""
        sites = []
        for icon in BeautifulSoup(html or "", "html.parser").select(".detail-torrent-source img"):
            site = release_trust.canonicalSite(icon.get("alt") or icon.get("src"))
            if site and site not in sites:
                sites.append(site)
        return sites

    def _remember_sites(self, url: str, sites: List[str]) -> None:
        if len(self._detailSites) >= DETAIL_CACHE_ENTRIES:
            oldest = min(self._detailSites, key=lambda key: self._detailSites[key][0])
            self._detailSites.pop(oldest, None)
        self._detailSites[url] = (time.monotonic(), sites)

    @staticmethod
    def _add_sites(release: TorrentRelease, sites: List[str]) -> None:
        for site in sites:
            if site not in release.origin_sites:
                release.origin_sites.append(site)

    async def refresh_sites(self, release: TorrentRelease) -> None:
        """
        Add every site the release's detail page lists to origin_sites. A search result
        names only the first site, so a release can be on a Balanced site the result does
        not show. A page read within DETAIL_CACHE_SECONDS is reused.
        """
        if not release.detail_url:
            return
        cached = self._detailSites.get(release.detail_url)
        if cached and time.monotonic() - cached[0] < DETAIL_CACHE_SECONDS:
            self._add_sites(release, cached[1])
            return
        html = await self._fetch_html(release.detail_url)
        sites = self._sites_on_detail_page(html)
        self._remember_sites(release.detail_url, sites)
        self._add_sites(release, sites)

    async def ensure_download_source(self, release: TorrentRelease) -> TorrentRelease:
        """
        Resolve the magnet for a chosen release from its detail page. The page also lists
        every site the torrent is on, which is added to origin_sites for the template check.
        """
        if release.magnet or release.torrent_url or not release.detail_url:
            return release
        match = _torrentIdPattern.search(release.detail_url)
        if not match:
            return release
        try:
            html = await self._fetch_html(release.detail_url)
            sites = self._sites_on_detail_page(html)
            self._remember_sites(release.detail_url, sites)
            self._add_sites(release, sites)
            pageToken = re.search(r"window\.pageToken\s*=\s*'([0-9a-f]+)'", html)
            csrfToken = re.search(r"window\.csrfToken\s*=\s*'([0-9a-f]+)'", html)
            if not pageToken or not csrfToken:
                print(f"ext.to: no magnet tokens on {release.detail_url}")
                return release
            magnet, infoHash = await self._request_magnet(
                match.group(1), pageToken.group(1), csrfToken.group(1), release.detail_url, release.title
            )
            release.magnet = magnet or release.magnet
            release.info_hash = infoHash or release.info_hash
        except Exception as e:
            print(f"ext.to: could not resolve the magnet for {release.title}: {e}")
        return release

    async def _request_magnet(self, torrentId: str, pageToken: str, csrfToken: str, referer: str, title: str):
        """ext.to's signed magnet request, signed as its page script does with the page token."""
        await self._pace()
        timestamp = int(time.time())
        signature = hashlib.sha256(f"{torrentId}|{timestamp}|{pageToken}".encode()).hexdigest()
        cookies, user_agent = self._clearance(referer)
        client = await get_http_client()
        response = await client.post(
            f"{self.current_url}/ajax/getTorrentMagnet.php",
            data={
                "torrent_id": torrentId,
                "download_type": "magnet",
                "timestamp": timestamp,
                "hmac": signature,
                "sessid": csrfToken,
            },
            headers={
                "User-Agent": user_agent or "",
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
            cookies=cookies,
            **indexer_request_kwargs(impersonate=_impersonate_for_ua(user_agent), timeout=30),
        )
        payload: Dict = response.json()
        url = payload.get("url") or ""
        hashMatch = re.search(r"\b([0-9a-fA-F]{40})\b", f"{url} {payload.get('hash') or ''}")
        infoHash = hashMatch.group(1).upper() if hashMatch else None
        if url.startswith("magnet:"):
            return url, infoHash
        if infoHash:
            return f"magnet:?xt=urn:btih:{infoHash}&dn={quote_plus(title)}", infoHash
        print(f"ext.to: magnet request returned no magnet ({payload.get('error') or response.status_code})")
        return None, None

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """ext.to is used for searches only. RSS stays on the indexers that have a feed."""
        return []

    async def test_connection(self) -> bool:
        try:
            html = await self._fetch_html(self.current_url + "/")
            return "torrent-title-link" in html or "ext.to" in html.lower()
        except Exception:
            return False


extto_indexer = ExtToIndexer()
