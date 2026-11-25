"""
Gazelle adapter.

Gazelle music trackers expose ajax.php, authenticated with an API key sent in the
Authorization header. Searches call action=browse. For an album search, the artist
and album from the search context fill artistname and groupname, and the quality term
the music cascade appends (FLAC, FLAC 24bit, MP3 320 and the like) becomes the format
and encoding filters. Each torrent of each group becomes one release, with its format,
encoding and media read from the structured fields rather than from a title.

Torrents download through ajax.php?action=download with the same header, so the
passkey never appears in a link.
"""

import html
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.indexers.base import TorrentRelease
from app.services.indexers.custom.common import CustomIndexer, FieldSpec, IndexerError, parseDate, toInt

# Quality words the music cascade appends to a query, removed before a text search.
_QUALITY_WORDS = {
    "flac",
    "mp3",
    "aac",
    "ogg",
    "dsd",
    "24bit",
    "16bit",
    "96khz",
    "192khz",
    "44khz",
    "48khz",
    "lossless",
}
_BITRATE_WORDS = {"128", "192", "256", "320", "v0", "v2"}


def qualityFilters(query: str) -> Tuple[str, Dict[str, str]]:
    """The query without its quality words, and the Gazelle format and encoding filters those words mean."""
    words = query.split()
    lowered = [w.lower() for w in words]
    filters: Dict[str, str] = {}
    if "flac" in lowered:
        filters["format"] = "FLAC"
        filters["encoding"] = "24bit Lossless" if "24bit" in lowered else "Lossless"
    elif "mp3" in lowered:
        filters["format"] = "MP3"
        for bitrate in ("320", "256", "192", "128"):
            if bitrate in lowered:
                filters["encoding"] = bitrate
                break
        if "v0" in lowered:
            filters["encoding"] = "V0 (VBR)"
        elif "v2" in lowered:
            filters["encoding"] = "V2 (VBR)"
    elif "aac" in lowered:
        filters["format"] = "AAC"
    elif "dsd" in lowered:
        filters["format"] = "DSD"
    text = " ".join(w for w, l in zip(words, lowered) if l not in _QUALITY_WORDS and l not in _BITRATE_WORDS)
    return text, filters


def musicFieldsFor(torrent: Dict[str, Any]) -> Dict[str, Any]:
    """Kinora's music fields from a Gazelle torrent's format, encoding and media."""
    fmt = (torrent.get("format") or "").strip()
    encoding = (torrent.get("encoding") or "").strip()
    lowerEncoding = encoding.lower()
    fields: Dict[str, Any] = {"audio_format": fmt.upper() or None}
    if "lossless" in lowerEncoding or fmt.upper() in ("FLAC", "ALAC", "WAV", "DSD"):
        fields["is_lossless"] = True
        fields["bit_depth"] = 24 if "24bit" in lowerEncoding else 16
    else:
        match = re.match(r"(v0|v1|v2|\d{3})", lowerEncoding)
        if match:
            fields["audio_bitrate"] = match.group(1).upper()
    return fields


class GazelleIndexer(CustomIndexer):
    kind = "gazelle"
    label = "Gazelle"
    description = "Gazelle music trackers, searched through ajax.php with an API key"
    supportsRss = True
    defaultCategories = {"music": []}

    @classmethod
    def credentialFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "apiKey",
                "API key",
                secret=True,
                required=True,
                help="Created in the tracker's user settings with torrent permissions",
            )
        ]

    @classmethod
    def settingFields(cls) -> List[FieldSpec]:
        return [
            FieldSpec(
                "authPrefix",
                "Authorization prefix",
                placeholder="token",
                help="Word sent before the key in the Authorization header. Leave empty to send the key alone",
            )
        ]

    def authHeaders(self) -> Dict[str, str]:
        key = self.config.credentials.get("apiKey", "")
        prefix = str(self.config.settings.get("authPrefix") or "").strip()
        return {"Authorization": f"{prefix} {key}" if prefix else key, "Accept": "application/json"}

    async def _ajax(self, params: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.request("GET", f"{self.base_url}/ajax.php", params=params)
        try:
            payload = response.json()
        except ValueError:
            snippet = " ".join((response.text or "")[:120].split())
            raise IndexerError(
                f"{self.name} did not answer with JSON. It starts with: {snippet or 'nothing'}", stage="parse"
            )
        if not isinstance(payload, dict):
            raise IndexerError(f"{self.name} answered with something other than an object", stage="parse")
        if payload.get("status") != "success":
            error = str(payload.get("error") or payload.get("status") or "unknown error")
            stage = "auth" if any(w in error.lower() for w in ("auth", "token", "key", "login")) else "http"
            raise IndexerError(f"{self.name} answered: {error}", stage=stage)
        return payload.get("response") or {}

    async def checkCapabilities(self) -> str:
        info = await self._ajax({"action": "index"})
        user = info.get("username")
        return f"Signed in as {user}" if user else "API key accepted"

    async def searchScope(self, query, scope, context, limit) -> List[TorrentRelease]:
        text, filters = qualityFilters(query or "")
        params: Dict[str, Any] = {"action": "browse", "order_by": "time", "order_way": "desc"}
        if context is not None and (context.artist or context.album):
            if context.artist:
                params["artistname"] = context.artist
            if context.album:
                params["groupname"] = context.album
        elif text:
            params["searchstr"] = text
        params.update(filters)
        response = await self._ajax(params)
        return self._releases(response.get("results") or [], scope)

    async def fetchRecent(self) -> List[TorrentRelease]:
        response = await self._ajax({"action": "browse", "order_by": "time", "order_way": "desc"})
        return self._releases(response.get("results") or [], "music")

    def _releases(self, groups: List[Dict[str, Any]], scope: str) -> List[TorrentRelease]:
        releases = []
        for groupPosition, group in enumerate(groups, start=1):
            if not isinstance(group, dict):
                raise IndexerError(f"Result {groupPosition} is not an object", stage="parse", field="results")
            groupName = html.unescape(str(group.get("groupName") or ""))
            if not groupName:
                raise IndexerError(f"Result {groupPosition} has no groupName", stage="parse", field="title")
            artist = html.unescape(str(group.get("artist") or "")) or None
            year = toInt(group.get("groupYear"))
            torrents = group.get("torrents")
            if torrents is None:
                # A group without a torrents list is a single torrent result.
                torrents = [group] if group.get("torrentId") else []
            for torrent in torrents:
                releases.append(self._release(torrent, artist, groupName, year, scope, groupPosition))
        return releases

    def _release(
        self,
        torrent: Dict[str, Any],
        artist: Optional[str],
        album: str,
        year: Optional[int],
        scope: str,
        position: int,
    ) -> TorrentRelease:
        torrentId = torrent.get("torrentId")
        if not torrentId:
            raise IndexerError(f"A torrent in result {position} has no torrentId", stage="parse", field="download")
        edition = []
        if torrent.get("remastered") and torrent.get("remasterYear"):
            edition.append(str(torrent.get("remasterYear")))
        if torrent.get("remasterTitle"):
            edition.append(html.unescape(str(torrent.get("remasterTitle"))))
        quality = " ".join(str(torrent.get(k) or "") for k in ("media", "format", "encoding")).strip()
        title = f"{artist} - {album}" if artist else album
        if year:
            title += f" ({year})"
        if edition:
            title += f" [{' '.join(edition)}]"
        if quality:
            title += f" [{quality}]"
        music = musicFieldsFor(torrent)
        music.update({"artist": artist, "album": album, "year": year})
        return self.makeRelease(
            title=title,
            scope=scope,
            downloadUrl=f"{self.base_url}/ajax.php?action=download&id={torrentId}",
            size=toInt(torrent.get("size")),
            seeders=toInt(torrent.get("seeders")),
            leechers=toInt(torrent.get("leechers")),
            publishDate=parseDate(torrent.get("time")),
            detailUrl=f"{self.base_url}/torrents.php?torrentid={torrentId}",
            rawData={
                "freeleech": torrent.get("isFreeleech"),
                "has_log": torrent.get("hasLog"),
                "log_score": torrent.get("logScore"),
                "has_cue": torrent.get("hasCue"),
                "scene": torrent.get("scene"),
            },
            musicFields=music,
        )
