"""
Shared behavior of user-defined indexers.

Every adapter (UNIT3D, Gazelle, Torznab, RSS and Kinora definitions) is a BaseIndexer,
so the search engine, RSS monitor, health tracking and trust checks treat it exactly as
a built-in indexer. This module adds what the built-in indexers do not need:

    configuration read from the custom_indexers table
    request pacing per indexer (see pacing)
    credentials kept out of every error message
    download links wrapped so their passkeys never leave the server (see privatelink)
    a test run that reports which step failed and why
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from app.core.http_client import get_http_client, indexer_request_kwargs
from app.services.indexers.base import BaseIndexer, TorrentRelease
from app.services.indexers import search_context
from app.services.indexers.custom import pacing
from app.services.indexers.custom.privatelink import wrapLink

TRUST_TIERS = ("open", "balanced", "trusted")
DEFAULT_TRUST_TIER = "open"
REQUEST_TIMEOUT_SECONDS = 25
# Results shown by a test run.
TEST_RESULT_LIMIT = 15


@dataclass
class IndexerConfig:
    """One row of custom_indexers with its credentials decrypted."""

    id: int
    name: str
    kind: str
    baseUrl: str
    settings: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)
    definition: Optional[Dict[str, Any]] = None
    mediaTypes: List[str] = field(default_factory=list)
    enableSearch: bool = True
    enableRss: bool = False
    trustTier: str = DEFAULT_TRUST_TIER
    isPrivate: bool = True
    minIntervalSeconds: float = 2.0
    requestsPerMinute: Optional[int] = None
    updatedAt: Optional[datetime] = None


@dataclass
class FieldSpec:
    """One input the indexer form shows for an adapter."""

    key: str
    label: str
    secret: bool = False
    required: bool = False
    placeholder: str = ""
    help: str = ""
    kind: str = "text"  # text, number, select, categories
    options: List[str] = field(default_factory=list)

    def toDict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "secret": self.secret,
            "required": self.required,
            "placeholder": self.placeholder,
            "help": self.help,
            "kind": self.kind,
            "options": list(self.options),
        }


class IndexerError(Exception):
    """
    A failed request or parse, with the stage it failed at. Stages are config, connect,
    auth, rate_limit, http and parse. field names the result field that could not be
    read, for parse errors.
    """

    def __init__(self, message: str, stage: str = "http", status: Optional[int] = None, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.status = status
        self.field = field

    def toDict(self) -> Dict[str, Any]:
        return {"stage": self.stage, "message": self.message, "status": self.status, "field": self.field}


def parseDate(value: Any) -> Optional[datetime]:
    """A naive UTC datetime from an ISO 8601 string, an RFC 822 date, or a Unix timestamp."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        number = float(value)
        if number > 1e11:
            number /= 1000.0
        moment = datetime.fromtimestamp(number, tz=timezone.utc)
    else:
        text = str(value).strip()
        moment = None
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                moment = parsedate_to_datetime(text)
            except TypeError, ValueError:
                moment = None
        if moment is None:
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M"):
                try:
                    moment = datetime.strptime(text, pattern)
                    break
                except ValueError:
                    continue
        if moment is None:
            return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def toInt(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


class CustomIndexer(BaseIndexer):
    """Base of every user-defined indexer adapter."""

    kind: str = ""
    label: str = ""
    description: str = ""
    supportsRss: bool = False
    # Category ids searched per scope when the user has not set any.
    defaultCategories: Dict[str, List[str]] = {}

    @classmethod
    def settingFields(cls) -> List[FieldSpec]:
        return []

    @classmethod
    def credentialFields(cls) -> List[FieldSpec]:
        return []

    @classmethod
    def validateConfig(
        cls, baseUrl: str, settings: Dict[str, Any], credentials: Dict[str, str], definition
    ) -> List[str]:
        """Errors in a configuration about to be saved. An empty list means it is valid."""
        errors = []
        if not (baseUrl or "").lower().startswith(("http://", "https://")):
            errors.append("Base URL must start with http:// or https://")
        for spec in cls.credentialFields() + cls.settingFields():
            if not spec.required:
                continue
            source = credentials if spec.secret else settings
            if not str(source.get(spec.key) or "").strip():
                errors.append(f"{spec.label} is required")
        return errors

    def __init__(self, config: IndexerConfig):
        self.config = config
        self.name = config.name
        self.base_url = config.baseUrl.rstrip("/")
        self.categories = {scope: scope for scope in config.mediaTypes}

    # ------------------------------------------------------------------
    # Identity and trust
    # ------------------------------------------------------------------
    @property
    def searchEnabled(self) -> bool:
        """Whether automatic and interactive searches may use this indexer."""
        return self.config.enableSearch

    @property
    def siteKey(self) -> str:
        """The origin site key release_trust uses for this indexer's releases."""
        return f"custom:{self.config.id}"

    def categoryIds(self, scope: str) -> List[str]:
        configured = (self.config.settings.get("categories") or {}).get(scope)
        if configured is None:
            configured = self.defaultCategories.get(scope, [])
        if isinstance(configured, str):
            configured = [part.strip() for part in configured.split(",")]
        return [str(c).strip() for c in configured if str(c).strip()]

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------
    def redact(self, text: str) -> str:
        """The text with every credential value replaced, so errors never carry a secret."""
        result = str(text)
        for value in self.config.credentials.values():
            if value and len(str(value)) >= 4:
                result = result.replace(str(value), "***")
        return result

    def authHeaders(self) -> Dict[str, str]:
        return {}

    def authParams(self) -> Dict[str, str]:
        return {}

    def authCookies(self) -> Dict[str, str]:
        return {}

    def absoluteUrl(self, link: Optional[str]) -> Optional[str]:
        if not link:
            return None
        link = str(link).strip()
        if link.startswith(("magnet:", "http://", "https://")):
            return link
        return urljoin(self.base_url + "/", link)

    async def httpSession(self):
        return await get_http_client()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        cookies: Optional[Dict[str, str]] = None,
        withAuth: bool = True,
        allowStatus: tuple = (),
    ):
        """
        One paced request to the indexer. Raises IndexerError with stage connect, auth,
        rate_limit or http. Statuses in allowStatus are returned instead of raised.
        """
        try:
            await pacing.waitForSlot(
                self.config.id,
                self.name,
                pacing.spacingSeconds(self.config.minIntervalSeconds, self.config.requestsPerMinute),
            )
        except pacing.RateLimitWait as e:
            raise IndexerError(str(e), stage="rate_limit")

        mergedHeaders = {"User-Agent": "Kinora/1.0", "Accept": "*/*"}
        mergedParams = dict(params or {})
        mergedCookies = dict(cookies or {})
        if withAuth:
            mergedHeaders.update(self.authHeaders())
            mergedParams.update(self.authParams())
            mergedCookies.update(self.authCookies())
        mergedHeaders.update(headers or {})

        session = await self.httpSession()
        try:
            response = await session.request(
                method,
                url,
                params=mergedParams or None,
                headers=mergedHeaders,
                data=data,
                cookies=mergedCookies or None,
                **indexer_request_kwargs(timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True),
            )
        except Exception as e:
            raise IndexerError(self.redact(f"Could not reach {self.name}: {e}"), stage="connect")

        status = response.status_code
        if status in allowStatus:
            return response
        if status == 429:
            retryAfter = toInt(response.headers.get("Retry-After")) or 60
            await pacing.pushBack(self.config.id, retryAfter)
            raise IndexerError(
                f"{self.name} answered 429 Too Many Requests. Requests pause for {retryAfter} seconds",
                stage="rate_limit",
                status=status,
            )
        if status in (401, 403):
            raise IndexerError(
                f"{self.name} rejected the credentials (HTTP {status})",
                stage="auth",
                status=status,
            )
        if status >= 400:
            snippet = " ".join((response.text or "")[:200].split())
            raise IndexerError(
                self.redact(f"{self.name} answered HTTP {status}" + (f". {snippet}" if snippet else "")),
                stage="http",
                status=status,
            )
        return response

    async def downloadTorrentFile(self, link: str) -> bytes:
        """The bytes of a .torrent file, fetched with this indexer's credentials."""
        response = await self.request("GET", self.absoluteUrl(link) or link)
        return response.content

    # ------------------------------------------------------------------
    # Releases
    # ------------------------------------------------------------------
    def makeRelease(
        self,
        *,
        title: str,
        scope: str,
        downloadUrl: Optional[str] = None,
        magnet: Optional[str] = None,
        infoHash: Optional[str] = None,
        size: Optional[int] = None,
        seeders: Optional[int] = None,
        leechers: Optional[int] = None,
        publishDate: Optional[datetime] = None,
        uploader: Optional[str] = None,
        detailUrl: Optional[str] = None,
        rawData: Optional[Dict[str, Any]] = None,
        musicFields: Optional[Dict[str, Any]] = None,
    ) -> TorrentRelease:
        """
        A TorrentRelease tagged with this indexer's name and site key. The quality fields
        come from the same title parsers the built-in indexers use. Download links are
        wrapped, and a magnet from a private indexer is wrapped too, because its tracker
        URLs carry the passkey.
        """
        title = " ".join(str(title).split())
        downloadUrl = self.absoluteUrl(downloadUrl)
        if downloadUrl and downloadUrl.startswith("magnet:") and not magnet:
            magnet, downloadUrl = downloadUrl, None
        if not infoHash and magnet:
            import re

            match = re.search(r"xt=urn:btih:([0-9a-fA-F]{40})", magnet)
            infoHash = match.group(1) if match else None
        torrentUrl = wrapLink(self.config.id, downloadUrl) if downloadUrl else None
        if magnet and self.config.isPrivate:
            if torrentUrl is None:
                torrentUrl = wrapLink(self.config.id, magnet)
            magnet = None

        common = dict(
            title=title,
            magnet=magnet,
            torrent_url=torrentUrl,
            detail_url=self.absoluteUrl(detailUrl),
            info_hash=(infoHash or "").lower() or None,
            size=size,
            size_string=None,
            seeders=int(seeders or 0),
            leechers=int(leechers or 0),
            upload_date=publishDate,
            uploader=uploader or None,
            category=scope,
            indexer=self.name,
            is_proper="PROPER" in title.upper(),
            is_repack="REPACK" in title.upper(),
            origin_sites=[self.siteKey],
            raw_data=rawData,
        )
        if scope == "music":
            music = self.parse_music_quality(title)
            music.update({k: v for k, v in (musicFields or {}).items() if v is not None})
            if musicFields:
                from app.services import music_quality

                music["quality_tier"] = music_quality.tier_from_fields(
                    music.get("audio_format"),
                    music.get("audio_bitrate"),
                    music.get("is_lossless", False),
                    music.get("bit_depth"),
                    music.get("sample_rate"),
                )
            return TorrentRelease(
                **common,
                audio_format=music.get("audio_format"),
                audio_bitrate=music.get("audio_bitrate"),
                bit_depth=music.get("bit_depth"),
                sample_rate=music.get("sample_rate"),
                quality_tier=music.get("quality_tier"),
                is_lossless=bool(music.get("is_lossless")),
                is_discography=bool(music.get("is_discography")),
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

    # ------------------------------------------------------------------
    # BaseIndexer interface
    # ------------------------------------------------------------------
    async def search(self, query: str, category: Optional[str] = None, limit: int = 100) -> List[TorrentRelease]:
        context = search_context.current()
        scope = context.scope if context and context.scope else search_context.scopeFor(None, category)
        if self.config.mediaTypes and scope not in self.config.mediaTypes:
            return []
        try:
            return await self.searchScope(query, scope, context, limit)
        except IndexerError:
            raise
        except Exception as e:
            raise IndexerError(self.redact(f"{self.name} search failed: {e}"), stage="parse")

    async def searchScope(
        self, query: str, scope: str, context: Optional[search_context.SearchContext], limit: int
    ) -> List[TorrentRelease]:
        raise NotImplementedError

    async def fetchRecent(self) -> List[TorrentRelease]:
        """Newest releases for RSS monitoring. Adapters with supportsRss override this."""
        return []

    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """The newest releases, with the outcome recorded in the indexer's health like a search."""
        if not self.config.enableRss or not self.supportsRss:
            return []
        from app.services import indexer_health

        try:
            releases = await self.fetchRecent()
        except Exception as e:
            await indexer_health.record_failure(self.name, self.redact(str(e)))
            raise
        await indexer_health.record_success(self.name)
        return releases

    async def checkCapabilities(self) -> str:
        """A short description of what the indexer offers. Raises IndexerError when it cannot be reached."""
        return "Reachable"

    async def test_connection(self) -> bool:
        result = await self.runTest()
        return bool(result.get("ok"))

    async def runTest(self, query: Optional[str] = None, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        A capability check followed by one sample search. Each step reports success or the
        exact failure. The results list shows what the parser read, without download links.
        """
        started = time.monotonic()
        steps: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []
        error: Optional[Dict[str, Any]] = None

        try:
            detail = await self.checkCapabilities()
            steps.append({"name": "Capabilities", "ok": True, "detail": detail})
        except IndexerError as e:
            steps.append({"name": "Capabilities", "ok": False, "detail": e.message})
            error = e.toDict()
        except Exception as e:
            message = self.redact(str(e))
            steps.append({"name": "Capabilities", "ok": False, "detail": message})
            error = {"stage": "connect", "message": message, "status": None, "field": None}

        if error is None:
            scope = scope or (self.config.mediaTypes[0] if self.config.mediaTypes else "movies")
            sampleQuery = (query or "").strip()
            try:
                with search_context.using(search_context.SearchContext(scope=scope)):
                    if sampleQuery or not self.supportsRss:
                        releases = await self.searchScope(sampleQuery, scope, search_context.current(), 50)
                        stepName = f"Search '{sampleQuery}'" if sampleQuery else "Search with no query"
                    else:
                        releases = await self.fetchRecent()
                        stepName = "Feed"
                steps.append({"name": stepName, "ok": True, "detail": f"Parsed {len(releases)} result(s)"})
                for release in releases[:TEST_RESULT_LIMIT]:
                    results.append(
                        {
                            "title": release.title,
                            "size": release.size,
                            "seeders": release.seeders,
                            "leechers": release.leechers,
                            "publish_date": release.upload_date.isoformat() if release.upload_date else None,
                            "uploader": release.uploader,
                            "info_hash": release.info_hash,
                            "has_download": bool(release.torrent_url or release.magnet),
                            "detail_url": release.detail_url,
                            "quality": release.quality or release.quality_tier,
                            "category": release.category,
                        }
                    )
            except IndexerError as e:
                steps.append({"name": "Search", "ok": False, "detail": e.message})
                error = e.toDict()
            except Exception as e:
                message = self.redact(str(e))
                steps.append({"name": "Search", "ok": False, "detail": message})
                error = {"stage": "parse", "message": message, "status": None, "field": None}

        return {
            "ok": error is None,
            "steps": steps,
            "results": results,
            "error": error,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
