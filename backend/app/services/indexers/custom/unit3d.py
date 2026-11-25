"""
UNIT3D adapter.

UNIT3D trackers expose /api/torrents/filter, authenticated with the account's API token.
A search for a library item with known ids filters by tmdbId, imdbId or tvdbId and by
season and episode, which matches releases whatever their titles say. Searches without
ids filter by name. Category ids differ between trackers, so they are configurable per
media type.

An id search returns every release of the item, and the search engine's cascade sends
several queries for one item, so an id search answer is reused for a short time instead
of being requested again.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.indexers.base import TorrentRelease
from app.services.indexers.custom.common import CustomIndexer, FieldSpec, IndexerError, parseDate, toInt

FILTER_PATH = "/api/torrents/filter"
# Seconds an id search answer is reused for repeated queries of the same item.
ID_SEARCH_REUSE_SECONDS = 120
ID_SEARCH_CACHE_ENTRIES = 64


class Unit3dIndexer(CustomIndexer):
    kind = "unit3d"
    label = "UNIT3D"
    description = "Trackers running UNIT3D, searched through /api/torrents/filter with an API token"
    supportsRss = True
    # UNIT3D's stock categories. Many trackers renumber them.
    defaultCategories = {"movies": ["1"], "shows": ["2"], "anime": [], "music": ["3"]}

    @classmethod
    def credentialFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "apiToken",
                "API token",
                secret=True,
                required=True,
                help="Found under the account's security settings on the tracker",
            )
        ]

    @classmethod
    def settingFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "categories",
                "Categories",
                kind="categories",
                help="UNIT3D category ids per media type. Empty uses Movies 1, TV 2 and Music 3",
            )
        ]

    def __init__(self, config):
        super().__init__(config)
        self._idAnswers: Dict[Tuple, Tuple[float, List[Dict[str, Any]]]] = {}

    def authParams(self) -> Dict[str, str]:
        return {"api_token": self.config.credentials.get("apiToken", "")}

    def authHeaders(self) -> Dict[str, str]:
        return {"Accept": "application/json"}

    async def _get(self, params: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """One filter request. Array parameters such as categories[] repeat, so the query is built from pairs."""
        from urllib.parse import urlencode

        query = urlencode([(k, v) for k, v in params if v not in (None, "")])
        url = f"{self.base_url}{FILTER_PATH}?{query}" if query else self.base_url + FILTER_PATH
        response = await self.request("GET", url)
        try:
            payload = response.json()
        except ValueError:
            snippet = " ".join((response.text or "")[:120].split())
            raise IndexerError(
                f"{self.name} did not answer with JSON. It starts with: {snippet or 'nothing'}",
                stage="parse",
            )
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            message = payload.get("message") if isinstance(payload, dict) else None
            raise IndexerError(
                f"{self.name} answered without a data list" + (f" ({message})" if message else ""),
                stage="auth" if message and "unauth" in str(message).lower() else "parse",
                field="data",
            )
        return payload

    async def checkCapabilities(self) -> str:
        payload = await self._get([("perPage", 1)])
        total = (payload.get("meta") or {}).get("total")
        return "API token accepted" + (f". The tracker lists {total} torrents" if total is not None else "")

    def _params(self, query: str, scope: str, context, limit: int) -> Tuple[List[Tuple[str, Any]], bool]:
        params: List[Tuple[str, Any]] = [("perPage", min(max(limit, 1), 100)), ("sortField", "created_at")]
        byId = False
        if context is not None:
            if scope in ("movies", "shows", "anime"):
                if context.tmdbId:
                    params.append(("tmdbId", context.tmdbId))
                    byId = True
                elif context.imdbNumeric:
                    params.append(("imdbId", context.imdbNumeric))
                    byId = True
                elif scope != "movies" and context.tvdbId:
                    params.append(("tvdbId", context.tvdbId))
                    byId = True
            if byId and scope in ("shows", "anime") and context.season is not None:
                params.append(("seasonNumber", context.season))
                if context.singleEpisode and context.episode is not None:
                    params.append(("episodeNumber", context.episode))
        if not byId and query:
            params.append(("name", query))
        for categoryId in self.categoryIds(scope):
            params.append(("categories[]", categoryId))
        return params, byId

    async def searchScope(self, query, scope, context, limit) -> List[TorrentRelease]:
        params, byId = self._params(query, scope, context, limit)
        key = tuple(params)
        if byId:
            cached = self._idAnswers.get(key)
            if cached and time.monotonic() - cached[0] < ID_SEARCH_REUSE_SECONDS:
                return [self._release(row, scope, position) for position, row in enumerate(cached[1], start=1)]
        rows = (await self._get(params))["data"]
        if byId:
            if len(self._idAnswers) >= ID_SEARCH_CACHE_ENTRIES:
                self._idAnswers.pop(min(self._idAnswers, key=lambda k: self._idAnswers[k][0]), None)
            self._idAnswers[key] = (time.monotonic(), rows)
        return [self._release(row, scope, position) for position, row in enumerate(rows, start=1)]

    async def fetchRecent(self) -> List[TorrentRelease]:
        releases = []
        for scope in self.config.mediaTypes or ["movies"]:
            params: List[Tuple[str, Any]] = [("perPage", 100), ("sortField", "created_at"), ("sortDirection", "desc")]
            for categoryId in self.categoryIds(scope):
                params.append(("categories[]", categoryId))
            rows = (await self._get(params))["data"]
            releases.extend(self._release(row, scope, position) for position, row in enumerate(rows, start=1))
        return releases

    def _release(self, row: Dict[str, Any], scope: str, position: int) -> TorrentRelease:
        attributes = row.get("attributes") if isinstance(row, dict) else None
        if not isinstance(attributes, dict):
            raise IndexerError(f"Result {position} has no attributes object", stage="parse", field="attributes")
        title = attributes.get("name")
        if not title:
            raise IndexerError(f"Result {position} has no name", stage="parse", field="title")
        size = toInt(attributes.get("size"))
        if attributes.get("size") not in (None, "") and size is None:
            raise IndexerError(
                f"Result {position} has a size that is not a number ({attributes.get('size')!r})",
                stage="parse",
                field="size",
            )
        download = attributes.get("download_link")
        magnet = attributes.get("magnet_link")
        infoHash = attributes.get("info_hash")
        if not (download or magnet or infoHash):
            raise IndexerError(
                f"Result {position} ('{title}') has no download_link, magnet_link or info_hash",
                stage="parse",
                field="download",
            )
        raw = {
            key: attributes.get(key)
            for key in ("tmdb_id", "imdb_id", "tvdb_id", "mal_id", "freeleech", "double_upload", "internal", "type")
            if attributes.get(key) not in (None, "")
        }
        return self.makeRelease(
            title=title,
            scope=scope,
            downloadUrl=download,
            magnet=magnet,
            infoHash=infoHash,
            size=size,
            seeders=toInt(attributes.get("seeders")),
            leechers=toInt(attributes.get("leechers")),
            publishDate=parseDate(attributes.get("created_at")),
            uploader=attributes.get("uploader"),
            detailUrl=attributes.get("details_link"),
            rawData=raw or None,
        )

    async def downloadTorrentFile(self, link: str) -> bytes:
        # UNIT3D download links already carry the account's RSS key.
        response = await self.request("GET", self.absoluteUrl(link) or link, withAuth=False)
        return response.content
