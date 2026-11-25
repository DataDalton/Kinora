"""
Torznab adapter.

Talks to any server that speaks the Torznab API directly, such as a tracker that offers
its own Torznab endpoint. The base URL is the API URL itself (the address that answers
?t=caps). Searches use the most specific function the server's caps list: t=movie for
movies with an IMDb or TMDB id, t=tvsearch for shows and anime with season and episode,
t=music for albums with artist and album, and t=search otherwise.

Results are RSS 2.0 items with torznab:attr elements. The parser reads seeders, peers,
infohash, magneturl, size, imdbid, tmdbid, downloadvolumefactor and uploadvolumefactor.
parseFeed also reads plain RSS feeds with the ezrss torrent namespace, so the RSS
adapter shares it.
"""

import time
import xml.etree.ElementTree as ElementTree
from typing import Any, Dict, List, Optional, Tuple

from app.services.indexers.base import TorrentRelease
from app.services.indexers.custom.common import (
    CustomIndexer,
    FieldSpec,
    IndexerError,
    parseDate,
    toInt,
)

TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
NEWZNAB_NS = "http://www.newznab.com/DTD/2010/feeds/attributes/"
TORRENT_NS = "http://xmlns.ezrss.it/0.1/"
# Seconds the caps answer is reused before it is read again.
CAPS_TTL_SECONDS = 3600
# Torznab error codes that mean the API key is wrong or the account is disabled.
AUTH_ERROR_CODES = {"100", "101", "102"}

# Newznab standard categories per scope.
STANDARD_CATEGORIES = {
    "movies": ["2000"],
    "shows": ["5000"],
    "anime": ["5070"],
    "music": ["3000"],
}

_FUNCTION_FOR_SCOPE = {
    "movies": ("movie", "movie-search"),
    "shows": ("tvsearch", "tv-search"),
    "anime": ("tvsearch", "tv-search"),
    "music": ("music", "music-search"),
}


def _localName(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: Optional[ElementTree.Element]) -> Optional[str]:
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def parseXml(text: str) -> ElementTree.Element:
    """Parse an XML answer, raising IndexerError(stage parse) with the parser's position when it is not XML."""
    try:
        return ElementTree.fromstring((text or "").strip().encode("utf-8"))
    except ElementTree.ParseError as e:
        snippet = " ".join((text or "")[:120].split())
        raise IndexerError(f"The answer is not valid XML ({e}). It starts with: {snippet or 'nothing'}", stage="parse")


def raiseForTorznabError(root: ElementTree.Element) -> None:
    """Raise the IndexerError a Torznab <error> answer describes."""
    if _localName(root.tag) != "error":
        return
    code = root.get("code") or ""
    description = root.get("description") or "no description"
    stage = "auth" if code in AUTH_ERROR_CODES else "http"
    raise IndexerError(f"Torznab error {code}: {description}", stage=stage)


def _attributes(item: ElementTree.Element) -> Dict[str, str]:
    """torznab:attr and newznab:attr name-value pairs of one item, names lowercased."""
    values: Dict[str, str] = {}
    for child in item:
        if _localName(child.tag) == "attr" and child.get("name"):
            values.setdefault(child.get("name").lower(), child.get("value") or "")
    return values


def parseFeedItems(root: ElementTree.Element) -> List[Dict[str, Any]]:
    """
    Every item of an RSS or Torznab feed as plain fields: title, downloadUrl, magnet,
    infoHash, size, seeders, leechers, publishDate, uploader, detailUrl, and the
    torznab attributes under attrs. Raises IndexerError naming the field that could not
    be read.
    """
    channel = root.find("channel") if _localName(root.tag) == "rss" else root
    if channel is None:
        raise IndexerError("The feed has no <channel> element", stage="parse", field="channel")
    items = []
    for position, item in enumerate(channel.iter("item"), start=1):
        title = _text(item.find("title"))
        if not title:
            raise IndexerError(f"Item {position} has no <title>", stage="parse", field="title")
        attrs = _attributes(item)
        enclosure = item.find("enclosure")
        enclosureUrl = enclosure.get("url") if enclosure is not None else None
        enclosureLength = toInt(enclosure.get("length")) if enclosure is not None else None
        link = _text(item.find("link"))
        magnet = attrs.get("magneturl") or _text(item.find(f"{{{TORRENT_NS}}}magnetURI"))
        if not magnet and link and link.startswith("magnet:"):
            magnet, link = link, None
        downloadUrl = enclosureUrl or link
        if downloadUrl and downloadUrl.startswith("magnet:"):
            magnet = magnet or downloadUrl
            downloadUrl = None

        seeders = toInt(attrs.get("seeders") or _text(item.find(f"{{{TORRENT_NS}}}seeds")))
        peers = toInt(attrs.get("peers") or _text(item.find(f"{{{TORRENT_NS}}}peers")))
        if attrs.get("seeders") not in (None, "") and seeders is None:
            raise IndexerError(
                f"Item {position} has a seeders attribute that is not a number ({attrs.get('seeders')!r})",
                stage="parse",
                field="seeders",
            )
        leechers = toInt(attrs.get("leechers"))
        if leechers is None and peers is not None:
            leechers = max(0, peers - (seeders or 0))

        size = toInt(attrs.get("size")) or toInt(_text(item.find("size"))) or enclosureLength
        if size is None:
            size = toInt(_text(item.find(f"{{{TORRENT_NS}}}contentLength")))

        dateText = _text(item.find("pubDate"))
        publishDate = parseDate(dateText) if dateText else None
        if dateText and publishDate is None:
            raise IndexerError(
                f"Item {position} has a pubDate that is not a date ({dateText!r})", stage="parse", field="publishDate"
            )

        infoHash = attrs.get("infohash") or _text(item.find(f"{{{TORRENT_NS}}}infoHash"))
        comments = _text(item.find("comments"))
        guid = _text(item.find("guid"))
        detailUrl = comments or (guid if guid and guid.startswith("http") else None)
        if not (downloadUrl or magnet or infoHash):
            raise IndexerError(
                f"Item {position} ('{title}') has no enclosure, link, magnet or infohash",
                stage="parse",
                field="download",
            )
        items.append(
            {
                "title": title,
                "downloadUrl": downloadUrl,
                "magnet": magnet,
                "infoHash": infoHash,
                "size": size,
                "seeders": seeders,
                "leechers": leechers,
                "publishDate": publishDate,
                "uploader": attrs.get("poster") or _text(item.find("author")),
                "detailUrl": detailUrl,
                "attrs": attrs,
            }
        )
    return items


def parseCaps(root: ElementTree.Element) -> Dict[str, Any]:
    """Search functions the server offers, with their supported parameters, and its categories."""
    raiseForTorznabError(root)
    if _localName(root.tag) != "caps":
        raise IndexerError(f"Expected a <caps> answer, got <{_localName(root.tag)}>", stage="parse", field="caps")
    searching: Dict[str, List[str]] = {}
    searchingNode = root.find("searching")
    if searchingNode is not None:
        for node in searchingNode:
            if (node.get("available") or "").lower() == "yes":
                params = [p.strip() for p in (node.get("supportedParams") or "q").split(",") if p.strip()]
                searching[_localName(node.tag)] = params
    categories = []
    categoriesNode = root.find("categories")
    if categoriesNode is not None:
        for category in categoriesNode.iter("category"):
            categories.append({"id": category.get("id"), "name": category.get("name")})
    server = root.find("server")
    return {
        "searching": searching,
        "categories": categories,
        "title": server.get("title") if server is not None else None,
    }


class TorznabIndexer(CustomIndexer):
    kind = "torznab"
    label = "Torznab"
    description = "Any Torznab API, searched with t=search, tvsearch, movie and music"
    supportsRss = True
    defaultCategories = STANDARD_CATEGORIES

    @classmethod
    def credentialFields(cls) -> List[FieldSpec]:
        return [FieldSpec("apiKey", "API key", secret=True, required=True)]

    @classmethod
    def settingFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "categories",
                "Categories",
                kind="categories",
                help="Torznab category ids per media type. Empty uses the standard ids (2000, 5000, 5070, 3000)",
            )
        ]

    def __init__(self, config):
        super().__init__(config)
        self._caps: Optional[Tuple[float, Dict[str, Any]]] = None

    def authParams(self) -> Dict[str, str]:
        return {"apikey": self.config.credentials.get("apiKey", "")}

    @property
    def apiUrl(self) -> str:
        return self.base_url

    async def _get(self, params: Dict[str, Any]) -> ElementTree.Element:
        response = await self.request("GET", self.apiUrl, params=params, allowStatus=(400, 401, 403))
        root = parseXml(response.text)
        raiseForTorznabError(root)
        if response.status_code in (401, 403):
            raise IndexerError(f"{self.name} rejected the API key (HTTP {response.status_code})", stage="auth")
        if response.status_code == 400:
            raise IndexerError(f"{self.name} answered HTTP 400", stage="http", status=400)
        return root

    async def caps(self) -> Dict[str, Any]:
        if self._caps and time.monotonic() - self._caps[0] < CAPS_TTL_SECONDS:
            return self._caps[1]
        caps = parseCaps(await self._get({"t": "caps"}))
        self._caps = (time.monotonic(), caps)
        return caps

    async def checkCapabilities(self) -> str:
        caps = await self.caps()
        functions = ", ".join(f"{name} ({', '.join(params)})" for name, params in caps["searching"].items())
        return f"{caps.get('title') or 'Torznab server'}. Searches: {functions or 'none listed'}. {len(caps['categories'])} categories"

    def _searchParams(self, query, scope, context, caps) -> Dict[str, Any]:
        function, capsName = _FUNCTION_FOR_SCOPE.get(scope, ("search", "search"))
        supported = caps["searching"].get(capsName)
        params: Dict[str, Any] = {}
        if supported is not None and context is not None:
            if scope == "movies":
                if "imdbid" in supported and context.imdbNumeric:
                    params["imdbid"] = context.imdbNumeric
                if "tmdbid" in supported and context.tmdbId:
                    params["tmdbid"] = context.tmdbId
            elif scope in ("shows", "anime"):
                if "tvdbid" in supported and context.tvdbId:
                    params["tvdbid"] = context.tvdbId
                if "imdbid" in supported and context.imdbNumeric:
                    params["imdbid"] = context.imdbNumeric
                if "tmdbid" in supported and context.tmdbId:
                    params["tmdbid"] = context.tmdbId
                if "season" in supported and context.season is not None:
                    params["season"] = context.season
                    if "ep" in supported and context.episode is not None and context.singleEpisode:
                        params["ep"] = context.episode
            elif scope == "music":
                if "artist" in supported and context.artist:
                    params["artist"] = context.artist
                if "album" in supported and context.album:
                    params["album"] = context.album
        if params:
            params["t"] = function
            # An id search returns every release of the item, so the free text is left out.
            if not any(key in params for key in ("imdbid", "tmdbid", "tvdbid")) and query:
                params["q"] = query
        else:
            params = {"t": "search"}
            if query:
                params["q"] = query
        return params

    async def searchScope(self, query, scope, context, limit) -> List[TorrentRelease]:
        caps = await self.caps()
        params = self._searchParams(query, scope, context, caps)
        categories = self.categoryIds(scope)
        if categories:
            params["cat"] = ",".join(categories)
        params["limit"] = min(max(limit, 1), 100)
        root = await self._get(params)
        return [self._release(item, scope) for item in parseFeedItems(root)]

    async def fetchRecent(self) -> List[TorrentRelease]:
        releases = []
        for scope in self.config.mediaTypes or ["movies"]:
            params: Dict[str, Any] = {"t": "search", "limit": 100}
            categories = self.categoryIds(scope)
            if categories:
                params["cat"] = ",".join(categories)
            root = await self._get(params)
            releases.extend(self._release(item, scope) for item in parseFeedItems(root))
        return releases

    def _release(self, item: Dict[str, Any], scope: str) -> TorrentRelease:
        attrs = item.get("attrs") or {}
        raw = {
            key: attrs[key]
            for key in (
                "imdbid",
                "tmdbid",
                "tvdbid",
                "downloadvolumefactor",
                "uploadvolumefactor",
                "grabs",
                "category",
            )
            if key in attrs
        }
        return self.makeRelease(
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
            rawData=raw or None,
        )
