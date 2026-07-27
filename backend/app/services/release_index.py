"""
Local release index.

Persists every torrent release the app ever sees (searches, RSS pulls, catalog
syncs) into the releases table and answers searches from it. The index is a side
effect of normal operation, so it grows toward covering everything anyone here
looks for without any dedicated crawling.

All write paths are best effort and never raise: losing an index write must never
break a search or a download.
"""

import hashlib
import re
from functools import lru_cache
from typing import List, Optional

from app.db import get_pool
from app.services.indexers.base import TorrentRelease

# Columns written on insert, in the order used by _releaseToRow.
_INSERT_COLUMNS = [
    "dedupe_key",
    "info_hash",
    "title",
    "normalized_title",
    "indexer",
    "category",
    "detail_url",
    "magnet_link",
    "torrent_url",
    "size",
    "size_string",
    "seeders",
    "leechers",
    "upload_date",
    "uploader",
    "quality",
    "codec",
    "source",
    "audio",
    "audio_channels",
    "hdr",
    "edition",
    "language",
    "release_group",
    "is_proper",
    "is_repack",
    "audio_format",
    "audio_bitrate",
    "bit_depth",
    "sample_rate",
    "quality_tier",
    "is_lossless",
    "is_discography",
    "artist",
    "album",
    "year",
]

_UPSERT_SQL = f"""
    INSERT INTO releases ({", ".join(_INSERT_COLUMNS)})
    VALUES ({", ".join(f"${i + 1}" for i in range(len(_INSERT_COLUMNS)))})
    ON CONFLICT (dedupe_key) DO UPDATE SET
        seeders = EXCLUDED.seeders,
        leechers = EXCLUDED.leechers,
        magnet_link = COALESCE(EXCLUDED.magnet_link, releases.magnet_link),
        torrent_url = COALESCE(EXCLUDED.torrent_url, releases.torrent_url),
        info_hash = COALESCE(EXCLUDED.info_hash, releases.info_hash),
        detail_url = COALESCE(EXCLUDED.detail_url, releases.detail_url),
        size = COALESCE(EXCLUDED.size, releases.size),
        size_string = COALESCE(EXCLUDED.size_string, releases.size_string),
        upload_date = COALESCE(EXCLUDED.upload_date, releases.upload_date),
        uploader = COALESCE(EXCLUDED.uploader, releases.uploader),
        category = COALESCE(EXCLUDED.category, releases.category),
        last_seen_at = NOW()
"""


@lru_cache(maxsize=4096)
def normalizeTitle(title: str) -> str:
    """
    Lowercase a title and collapse punctuation to single spaces for matching.
    Commas between digits are thousands separators ("10,000 BC"), never scene
    separators, so they are removed rather than spaced: "10,000" and "10000"
    normalize to the same form. Dots stay word separators because scene naming
    uses them as spaces ("11.11.11.2011" means "11 11 11 2011").

    Cached because the feed matcher compares every release against every
    monitored item, normalizing the same titles thousands of times per cycle.
    """
    lowered = re.sub(r"(\d),(\d)", r"\1\2", (title or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def dedupeKey(release: TorrentRelease) -> str:
    """
    Stable identity for a release. The info hash when known, otherwise a digest of
    indexer plus detail URL (or title plus size for indexers without detail pages).
    """
    if release.info_hash:
        return release.info_hash.lower()
    basis = f"{release.indexer}|{release.detail_url or ''}|{release.title}|{release.size or 0}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _releaseToRow(release: TorrentRelease) -> tuple:
    """Map a TorrentRelease onto the insert column order."""
    return (
        dedupeKey(release),
        release.info_hash.lower() if release.info_hash else None,
        (release.title or "")[:1000],
        normalizeTitle(release.title)[:1000],
        release.indexer or "unknown",
        release.category,
        release.detail_url,
        release.magnet,
        release.torrent_url,
        release.size,
        release.size_string,
        release.seeders or 0,
        release.leechers or 0,
        release.upload_date,
        release.uploader,
        release.quality,
        release.codec,
        release.source,
        release.audio,
        release.audio_channels,
        release.hdr,
        release.edition,
        release.language,
        release.release_group,
        release.is_proper,
        release.is_repack,
        release.audio_format,
        release.audio_bitrate,
        release.bit_depth,
        release.sample_rate,
        release.quality_tier,
        release.is_lossless,
        release.is_discography,
        release.artist[:500] if release.artist else None,
        release.album[:500] if release.album else None,
        release.year,
    )


def _rowToRelease(row) -> TorrentRelease:
    """Rebuild a TorrentRelease from a releases table row."""
    return TorrentRelease(
        title=row["title"],
        magnet=row["magnet_link"],
        torrent_url=row["torrent_url"],
        detail_url=row["detail_url"],
        info_hash=row["info_hash"],
        size=row["size"],
        size_string=row["size_string"],
        seeders=row["seeders"],
        leechers=row["leechers"],
        upload_date=row["upload_date"],
        uploader=row["uploader"],
        category=row["category"],
        indexer=row["indexer"],
        quality=row["quality"],
        codec=row["codec"],
        source=row["source"],
        audio=row["audio"],
        audio_channels=row["audio_channels"],
        hdr=row["hdr"],
        edition=row["edition"],
        language=row["language"],
        release_group=row["release_group"],
        is_proper=row["is_proper"],
        is_repack=row["is_repack"],
        audio_format=row["audio_format"],
        audio_bitrate=row["audio_bitrate"],
        bit_depth=row["bit_depth"],
        sample_rate=row["sample_rate"],
        quality_tier=row["quality_tier"],
        is_lossless=row["is_lossless"],
        is_discography=row["is_discography"],
        artist=row["artist"],
        album=row["album"],
        year=row["year"],
    )


async def upsertReleases(releases: List[TorrentRelease]) -> int:
    """
    Persist releases into the index, refreshing seed counts and last_seen_at for
    ones already known. Deduplicates within the batch. Best effort, returns the
    number of rows written, 0 on any failure.
    """
    if not releases:
        return 0

    rows = {}
    for release in releases:
        if not release or not release.title:
            continue
        # Last occurrence wins within a batch so a row with a resolved magnet
        # replaces an earlier bare one.
        rows[dedupeKey(release)] = _releaseToRow(release)

    if not rows:
        return 0

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(_UPSERT_SQL, list(rows.values()))
        return len(rows)
    except Exception as e:
        print(f"Release index write failed ({len(rows)} rows): {e}")
        return 0


def _mediaTypeFilter(media_type: Optional[str]):
    """
    SQL fragment and params restricting rows to the slice of the index the given
    media type would search, mirroring the indexer selection in the search engine.
    """
    if media_type == "anime":
        return "AND (indexer = 'Nyaa' OR category = 'anime')", []
    if media_type in ("music", "album", "track"):
        return "AND (category = 'music' OR audio_format IS NOT NULL)", []
    if media_type in ("movie", "show"):
        return "AND (category IS DISTINCT FROM 'music')", []
    return "", []


async def searchLocal(
    query: str,
    media_type: Optional[str] = None,
    limit: int = 100,
    max_age_days: Optional[int] = None,
    quality: Optional[str] = None,
) -> List[TorrentRelease]:
    """
    Search the local index. Every normalized query token must appear as a whole
    word in the normalized title, so the token "1" from a title like "+1" matches
    " 1 " but never the 1 inside "1080p". The trigram index accelerates the regex
    matches.

    quality filters on the parsed resolution column rather than title text, so a
    2160p filter also returns releases titled "4K" or "UHD", which ingest parsing
    already normalized. Results are ordered by seed count as last recorded.
    Returns [] on any failure.
    """
    tokens = normalizeTitle(query).split()
    if not tokens:
        return []

    conditions = []
    params: list = []
    for token in tokens:
        # Tokens are [a-z0-9]+ after normalization, so no regex escaping needed.
        # \m and \M are Postgres word boundaries.
        params.append(rf"\m{token}\M")
        conditions.append(f"normalized_title ~ ${len(params)}")

    typeClause, typeParams = _mediaTypeFilter(media_type)
    params.extend(typeParams)

    qualityClause = ""
    if quality:
        params.append(quality)
        qualityClause = f"AND quality = ${len(params)}"

    ageClause = ""
    if max_age_days is not None:
        params.append(max_age_days)
        ageClause = f"AND last_seen_at > NOW() - (${len(params)} * INTERVAL '1 day')"

    params.append(limit)

    sql = f"""
        SELECT * FROM releases
        WHERE {" AND ".join(conditions)}
        {typeClause}
        {qualityClause}
        {ageClause}
        ORDER BY seeders DESC, last_seen_at DESC
        LIMIT ${len(params)}
    """

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        releases = []
        for row in rows:
            release = _rowToRelease(row)
            # Index freshness rides along in raw_data so response formatting can
            # show when a cached row was last confirmed on its indexer.
            release.raw_data = {
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "from_index": True,
            }
            releases.append(release)
        return releases
    except Exception as e:
        print(f"Release index search failed for '{query}': {e}")
        return []


async def knownKeys(releases: List[TorrentRelease]) -> Optional[set]:
    """
    Subset of the given releases already present in the index, as dedupe keys.
    Used by feed readers to page until they reach already-seen releases. Returns
    None when the index cannot be consulted, so callers can distinguish "nothing
    known" from "could not check" and stop paging instead of running away.
    """
    keys = [dedupeKey(r) for r in releases if r and r.title]
    if not keys:
        return set()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT dedupe_key FROM releases WHERE dedupe_key = ANY($1)", keys)
        return {row["dedupe_key"] for row in rows}
    except Exception:
        return None


async def hasReleasesFromIndexer(indexer: str) -> Optional[bool]:
    """
    Whether the index holds any release from an indexer. Feed readers use this to
    tell a first run (seed a bounded window) from an up-to-date index (page until
    overlap). Returns None when the index cannot be consulted.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM releases WHERE indexer = $1)", indexer)
    except Exception:
        return None


async def getLastSeenMap(releases: List[TorrentRelease]) -> dict:
    """
    Map dedupe key to last_seen_at for the given releases, used to annotate
    responses with index freshness. Returns {} on failure.
    """
    keys = [dedupeKey(r) for r in releases if r and r.title]
    if not keys:
        return {}
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT dedupe_key, last_seen_at FROM releases WHERE dedupe_key = ANY($1)",
                keys,
            )
        return {row["dedupe_key"]: row["last_seen_at"] for row in rows}
    except Exception:
        return {}
