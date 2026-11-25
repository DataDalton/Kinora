"""
User-defined indexer registry.

Loads the custom_indexers table into adapter instances, which the search engine, the
interactive search, the RSS monitor and download link resolution look up by name or id.
Each process keeps its own instances. A version number in the shared cache changes on
every save, so the API and every Celery worker reload within RELOAD_CHECK_SECONDS of an
edit, and a reload also happens every MAX_AGE_SECONDS when the cache is unreachable.

Every load also tells release_trust which tier each indexer's site key belongs to.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from app.core.cache import cacheGet, cacheIncr
from app.services.indexers.custom.common import CustomIndexer, IndexerConfig, TRUST_TIERS, DEFAULT_TRUST_TIER
from app.services.indexers.custom.definition import DefinitionIndexer
from app.services.indexers.custom.gazelle import GazelleIndexer
from app.services.indexers.custom.privatelink import decryptText, encryptText
from app.services.indexers.custom.rssfeed import RssFeedIndexer
from app.services.indexers.custom.torznab import TorznabIndexer
from app.services.indexers.custom.unit3d import Unit3dIndexer

ADAPTERS = {
    adapter.kind: adapter
    for adapter in (Unit3dIndexer, GazelleIndexer, TorznabIndexer, RssFeedIndexer, DefinitionIndexer)
}
# Names a custom indexer may not take, because built-in indexers and the local index use them.
RESERVED_NAMES = {"1337x", "yts", "nyaa", "ext.to", "local index", "unknown"}
RELOAD_CHECK_SECONDS = 10
MAX_AGE_SECONDS = 300
_VERSION_KEY = "indexer:custom:version"

_state: Dict[str, Any] = {"checkedAt": 0.0, "loadedAt": 0.0, "version": None, "loaded": False, "byId": {}}


def encryptCredentials(credentials: Dict[str, str]) -> Optional[str]:
    cleaned = {key: str(value) for key, value in (credentials or {}).items() if value not in (None, "")}
    return encryptText(json.dumps(cleaned)) if cleaned else None


def decryptCredentials(stored: Optional[str]) -> Dict[str, str]:
    if not stored:
        return {}
    text = decryptText(stored)
    if text is None:
        print("Custom indexer credentials could not be decrypted. SECRET_KEY may have changed since they were saved")
        return {}
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _jsonValue(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return fallback
    return value


def configFromRow(row) -> IndexerConfig:
    tier = row["trust_tier"] if row["trust_tier"] in TRUST_TIERS else DEFAULT_TRUST_TIER
    return IndexerConfig(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        baseUrl=row["base_url"] or "",
        settings=_jsonValue(row["settings"], {}) or {},
        credentials=decryptCredentials(row["credentials"]),
        definition=_jsonValue(row["definition"], None),
        mediaTypes=list(row["media_types"] or []),
        enableSearch=bool(row["enable_search"]),
        enableRss=bool(row["enable_rss"]),
        trustTier=tier,
        isPrivate=bool(row["is_private"]),
        minIntervalSeconds=float(row["min_interval_seconds"] or 0),
        requestsPerMinute=row["requests_per_minute"],
        updatedAt=row["updated_at"],
    )


def buildIndexer(config: IndexerConfig) -> CustomIndexer:
    adapter = ADAPTERS.get(config.kind)
    if adapter is None:
        raise ValueError(f"Unknown indexer type '{config.kind}'")
    return adapter(config)


async def _closeLater(instances: List[CustomIndexer]) -> None:
    for instance in instances:
        close = getattr(instance, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                pass


async def ensureLoaded(force: bool = False) -> None:
    """Load or refresh the indexers when the shared version changed or the copy is old."""
    now = time.monotonic()
    if not force and _state["loaded"] and now - _state["checkedAt"] < RELOAD_CHECK_SECONDS:
        return
    version = await cacheGet(_VERSION_KEY)
    _state["checkedAt"] = now
    if not force and _state["loaded"] and version == _state["version"] and now - _state["loadedAt"] < MAX_AGE_SECONDS:
        return
    try:
        from app.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM custom_indexers ORDER BY lower(name)")
    except Exception as e:
        # The table is missing before the migration runs. Keep what is loaded.
        if not _state["loaded"]:
            print(f"Custom indexers could not be loaded: {e}")
            _state["loaded"] = True
            _state["loadedAt"] = now
        return

    previous: Dict[int, CustomIndexer] = _state["byId"]
    current: Dict[int, CustomIndexer] = {}
    for row in rows:
        existing = previous.get(row["id"])
        if existing is not None and existing.config.updatedAt == row["updated_at"]:
            current[row["id"]] = existing
            continue
        try:
            current[row["id"]] = buildIndexer(configFromRow(row))
        except Exception as e:
            print(f"Custom indexer {row['name']} could not be loaded: {e}")
    replaced = [instance for key, instance in previous.items() if current.get(key) is not instance]
    if replaced:
        try:
            asyncio.get_running_loop().create_task(_closeLater(replaced))
        except RuntimeError:
            pass

    _state.update({"byId": current, "version": version, "loaded": True, "loadedAt": now})

    from app.services import release_trust

    release_trust.setCustomSites(
        {
            instance.siteKey: (
                instance.name,
                instance.config.trustTier,
                instance.config.enableSearch or instance.config.enableRss,
            )
            for instance in current.values()
        }
    )


async def notifyChanged() -> None:
    """Tell every process the indexers changed, and reload this one now."""
    await cacheIncr(_VERSION_KEY)
    await ensureLoaded(force=True)


def allIndexers() -> List[CustomIndexer]:
    return list(_state["byId"].values())


def byId(indexerId: int) -> Optional[CustomIndexer]:
    return _state["byId"].get(indexerId)


async def byIdLoaded(indexerId: int) -> Optional[CustomIndexer]:
    await ensureLoaded()
    return byId(indexerId)


def byName(name: Optional[str]) -> Optional[CustomIndexer]:
    wanted = (name or "").strip().lower()
    if not wanted:
        return None
    for instance in _state["byId"].values():
        if instance.name.lower() == wanted:
            return instance
    return None


def searchIndexers(scope: str) -> List[CustomIndexer]:
    """Indexers enabled for search that cover a scope (movies, shows, anime or music)."""
    return [
        instance
        for instance in _state["byId"].values()
        if instance.config.enableSearch and (not instance.config.mediaTypes or scope in instance.config.mediaTypes)
    ]


def rssIndexers() -> List[CustomIndexer]:
    return [instance for instance in _state["byId"].values() if instance.config.enableRss and instance.supportsRss]


def versionTag() -> str:
    """Changes whenever the set of indexers changes, for search cache keys."""
    return str(_state["version"] or 0) + ":" + ",".join(sorted(str(key) for key in _state["byId"]))
