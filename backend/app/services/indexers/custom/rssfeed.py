"""
RSS feed adapter.

Reads a tracker's personal RSS feed, whose URL carries the account's passkey, so the
whole feed URL is stored as a credential. The feed is used for RSS monitoring. When the
tracker's feed accepts a search term in a query parameter, naming that parameter enables
search through the same feed.
"""

from typing import Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.indexers.base import TorrentRelease
from app.services.indexers.custom.common import CustomIndexer, FieldSpec
from app.services.indexers.custom.torznab import parseFeedItems, parseXml, raiseForTorznabError


class RssFeedIndexer(CustomIndexer):
    kind = "rss"
    label = "RSS feed (passkey)"
    description = "A personal tracker feed for RSS monitoring, searchable when the feed takes a query parameter"
    supportsRss = True

    @classmethod
    def credentialFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "feedUrl",
                "Feed URL",
                secret=True,
                required=True,
                placeholder="https://tracker.example/rss?passkey=...",
                help="The full feed address including the passkey. It is stored encrypted",
            )
        ]

    @classmethod
    def settingFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "searchParam",
                "Search parameter",
                placeholder="search",
                help="Query parameter the feed filters by. Leave empty when the feed cannot be searched",
            )
        ]

    @classmethod
    def validateConfig(cls, baseUrl, settings, credentials, definition) -> List[str]:
        errors = super().validateConfig(baseUrl, settings, credentials, definition)
        feedUrl = str(credentials.get("feedUrl") or "")
        if feedUrl and not feedUrl.lower().startswith(("http://", "https://")):
            errors.append("Feed URL must start with http:// or https://")
        return errors

    def _feedUrl(self, extra: Dict[str, str]) -> str:
        parts = urlsplit(self.config.credentials.get("feedUrl", ""))
        query = parse_qsl(parts.query, keep_blank_values=True) + list(extra.items())
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    async def _read(self, extra: Dict[str, str], scope: str) -> List[TorrentRelease]:
        response = await self.request("GET", self._feedUrl(extra))
        root = parseXml(response.text)
        raiseForTorznabError(root)
        return [
            self.makeRelease(
                title=item["title"],
                scope=scope,
                downloadUrl=item.get("downloadUrl"),
                magnet=item.get("magnet"),
                infoHash=item.get("infoHash"),
                size=item.get("size"),
                seeders=item.get("seeders"),
                leechers=item.get("leechers"),
                publishDate=item.get("publishDate"),
                uploader=item.get("uploader"),
                detailUrl=item.get("detailUrl"),
            )
            for item in parseFeedItems(root)
        ]

    @property
    def searchParam(self) -> str:
        return str(self.config.settings.get("searchParam") or "").strip()

    async def checkCapabilities(self) -> str:
        if self.searchParam:
            return f"Feed with search through the '{self.searchParam}' parameter"
        return "Feed for RSS monitoring. Search is off because no search parameter is set"

    async def searchScope(self, query, scope, context, limit) -> List[TorrentRelease]:
        if not self.searchParam:
            return []
        return await self._read({self.searchParam: query} if query else {}, scope)

    async def fetchRecent(self) -> List[TorrentRelease]:
        scope = self.config.mediaTypes[0] if len(self.config.mediaTypes) == 1 else "movies"
        return await self._read({}, scope)
