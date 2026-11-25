"""
Cascading Search Engine

Search strategy:
1. Resolution-first: Search highest quality first, cascade down
2. Uploader-aware: Try all allowed uploaders at each quality level
3. Stop as soon as acceptable release is found
"""

from typing import List, Optional
import asyncio
import hashlib

from app.services.indexers.base import TorrentRelease
from app.services import download_episodes
from app.services.indexers.leetx import leetx_indexer
from app.services.indexers.yts import yts_indexer
from app.services.indexers.nyaa import NyaaIndexer
from app.services.indexers.extto import extto_indexer
from app.services.indexers import search_context
from app.services.indexers.custom import registry as custom_indexers
from app.services.media_profile import MediaProfile, media_profile_service
from app.services import music_quality
from app.services import release_index
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.core.cache import cacheGet, cacheSet
from app.services.torrent_validator import validate_and_resume_torrent
from app.services import release_matching
from app.services import indexer_health
from app.services import release_trust
from app.services.folder_selector import folderSelector

# Media type -> root_folders.media_type scope, and -> the item table that stores root_folder_id.
_FOLDER_MEDIA_TYPE = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "music",
    "music": "music",
    "track": "music",
}
_ITEM_TABLE = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "music": "albums",
    "track": "albums",
}

# Query-side synonyms per resolution. Indexer search is a plain keyword match, so a
# release titled "4K UHD" never matches a "2160p" query. Targeted sweeps expand each
# resolution into every naming variant. Result parsing already normalizes these back
# (parse_quality), so filtering and scoring are unaffected.
RESOLUTION_QUERY_SYNONYMS = {
    "4320p": ["4320p", "8K"],
    "2160p": ["2160p", "4K", "UHD"],
    "1080p": ["1080p"],
    "720p": ["720p"],
    "576p": ["576p"],
    "480p": ["480p"],
    "360p": ["360p"],
    "240p": ["240p"],
}

# Local index rows older than this are not trusted for automated downloads, since
# their recorded seed counts may no longer reflect the swarm.
LOCAL_INDEX_MAX_AGE_DAYS = 7


async def _resolve_grab_folder(conn, media_type, media_id):
    """
    Pick the paired root folder for an automated grab: the item's assigned folder when it has
    one, else the configured selection for its type. The folder's download_path is where the
    torrent is added (same filesystem as root_path so the completed files hardlink into the
    library), and its id is recorded so the organizer knows where to place the release.
    Returns the folder dict, or None when no folder is configured.
    """
    if conn is None or not media_type:
        return None
    folder_media_type = _FOLDER_MEDIA_TYPE.get(media_type, media_type)
    override = None
    table = _ITEM_TABLE.get(media_type)
    if media_id is not None and table:
        try:
            override = await conn.fetchval(f"SELECT root_folder_id FROM {table} WHERE id = $1", media_id)
        except Exception:
            override = None
    try:
        return await folderSelector.selectFolder(conn, mediaType=folder_media_type, overrideFolderId=override)
    except Exception as e:
        print(f"Could not resolve grab folder for {media_type} {media_id}: {e}")
        return None


async def _record_download_history(
    conn,
    torrent_hash,
    release,
    media_id,
    media_type,
    grab_mode="auto",
    was_upgrade=False,
    root_folder_id=None,
    safety_template=None,
) -> None:
    """
    Write a complete download_history row for an added release, including the magnet/
    .torrent source and info hash so it can be re-added later from the archive, plus the
    root_folder_id so the organizer can place the completed files, and the trust category
    and safety template the release was chosen under. Keyed on torrent_hash and idempotent.
    Best effort, never raises.
    """
    try:
        await conn.execute(
            """
            INSERT INTO download_history (
                media_id, media_type, torrent_hash, torrent_title, indexer,
                quality, size, magnet_link, torrent_url, info_hash, status,
                grab_mode, was_upgrade, root_folder_id, download_client, created_at,
                uploader, trust_category, safety_template, origin_sites
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'downloading', $11, $12, $13, 'qbittorrent', NOW(),
                $14, $15, $16, $17
            )
            ON CONFLICT (torrent_hash) DO UPDATE SET
                media_id = EXCLUDED.media_id,
                media_type = EXCLUDED.media_type,
                torrent_title = EXCLUDED.torrent_title,
                indexer = EXCLUDED.indexer,
                magnet_link = COALESCE(EXCLUDED.magnet_link, download_history.magnet_link),
                torrent_url = COALESCE(EXCLUDED.torrent_url, download_history.torrent_url),
                info_hash = COALESCE(EXCLUDED.info_hash, download_history.info_hash),
                grab_mode = EXCLUDED.grab_mode,
                was_upgrade = EXCLUDED.was_upgrade,
                root_folder_id = COALESCE(EXCLUDED.root_folder_id, download_history.root_folder_id),
                uploader = EXCLUDED.uploader,
                trust_category = EXCLUDED.trust_category,
                safety_template = EXCLUDED.safety_template,
                origin_sites = EXCLUDED.origin_sites,
                updated_at = NOW()
            """,
            media_id,
            media_type,
            torrent_hash,
            release.title or "Unknown",
            release.indexer or "unknown",
            release.quality,
            release.size,
            release.magnet,
            release.torrent_url,
            release.info_hash or torrent_hash,
            grab_mode,
            was_upgrade,
            root_folder_id,
            release.uploader,
            getattr(release, "trust_category", None),
            safety_template,
            list(getattr(release, "origin_sites", None) or []),
        )
        await download_episodes.recordCoveredEpisodes(conn, torrent_hash, media_type, media_id, release.title)
    except Exception as e:
        print(f"Failed to record download history for {torrent_hash}: {e}")


# How many times a search picks again after its choice turns out to be blocklisted by hash.
_BLOCKED_RESELECT_LIMIT = 3

# Detail pages read per selection to find whether a release a Balanced profile rejected
# for its site is also on a Balanced site the search result did not show.
SITE_CHECKS_PER_SELECTION = 3


async def _isReleaseHashBlocked(conn, release, media_type, media_id) -> bool:
    """True when the release's info hash, from the release or its magnet, is on the blocklist."""
    from app.db import get_pool
    from app.services import hash_blocklist

    infoHash = release.info_hash or hash_blocklist.infoHashFromSource(release.magnet)
    if not infoHash:
        return False
    try:
        if conn is not None:
            return await hash_blocklist.isHashBlocked(conn, infoHash, media_type, media_id)
        pool = await get_pool()
        async with pool.acquire() as poolConn:
            return await hash_blocklist.isHashBlocked(poolConn, infoHash, media_type, media_id)
    except Exception as e:
        print(f"Could not check the hash blocklist for {release.title}: {e}")
        return False


async def _load_match_target(conn, media_type, media_id, query, episode_target=None):
    """
    What a search is for, loaded from the media item, so releases of other titles,
    years or seasons are rejected. The season and episode come from the query, since
    episode and season searches put SxxEyy or Sxx there. episode_target, a dict with
    season, episode and absolute_episode, replaces them for an episode search. Without a
    library list in episode_target the target accepts only releases of that one episode.
    With one, packs are accepted and checked by the caller. Returns None when the item
    cannot be loaded, which leaves selection unchanged.
    """
    from app.db import get_pool
    from app.services import release_matching

    if not media_id or media_type not in ("movie", "show", "anime", "album"):
        return None
    sql = {
        "movie": "SELECT title, original_title, release_date AS item_date, metadata FROM movies WHERE id = $1",
        "show": "SELECT title, original_title, first_air_date AS item_date, metadata FROM shows WHERE id = $1",
        "anime": "SELECT title, original_title, release_date AS item_date, metadata FROM anime WHERE id = $1",
        "album": (
            "SELECT a.title, NULL AS original_title, a.release_date AS item_date, NULL::jsonb AS metadata, "
            "ar.name AS artist FROM albums a LEFT JOIN artists ar ON ar.id = a.artist_id WHERE a.id = $1"
        ),
    }[media_type]
    try:
        if conn is not None:
            row = await conn.fetchrow(sql, media_id)
        else:
            pool = await get_pool()
            async with pool.acquire() as poolConn:
                row = await poolConn.fetchrow(sql, media_id)
    except Exception as e:
        print(f"Could not load match target for {media_type} {media_id}: {e}")
        return None
    if not row:
        return None
    metadata = row["metadata"]
    if isinstance(metadata, str):
        try:
            import json

            metadata = json.loads(metadata)
        except ValueError:
            metadata = None
    titles = [row["title"], row["original_title"]] + release_matching.alternativeTitles(metadata)
    titles = list(dict.fromkeys(t for t in titles if t))
    season, episode = release_matching.seasonEpisodeFromQuery(query)
    absoluteEpisode = None
    singleEpisode = False
    if episode_target and media_type in ("show", "anime"):
        season = episode_target.get("season")
        episode = episode_target.get("episode")
        absoluteEpisode = episode_target.get("absolute_episode")
        singleEpisode = episode_target.get("library") is None
    itemDate = row["item_date"]
    return release_matching.MatchTarget(
        kind=media_type,
        titles=titles,
        year=itemDate.year if itemDate else None,
        season=season if media_type in ("show", "anime") else None,
        episode=episode if media_type in ("show", "anime") else None,
        absoluteEpisode=absoluteEpisode,
        singleEpisode=singleEpisode,
        artist=row["artist"] if media_type == "album" else None,
    )


def _episodeUpgradeCheck(target, library, profile, media_type, upgrade_allowed):
    """
    The release check for an episode upgrade. A release must hold the target episode,
    and every library episode it holds must get a better file, so a season pack never
    replaces an episode that already has the same or a better quality.
    """
    from app.services import release_matching

    def isTarget(episode):
        if target.absoluteEpisode is not None and episode.get("absolute") == target.absoluteEpisode:
            return True
        return episode.get("season") == target.season and episode.get("episode") == target.episode

    def check(release):
        covered = release_matching.coveredEpisodes(release.title, target, library)
        if not covered or not any(isTarget(e) for e in covered):
            return False
        return all(
            media_profile_service.needs_upgrade(
                e.get("quality"), release.quality, profile, media_type, upgrade_allowed=upgrade_allowed
            )
            for e in covered
        )

    return check


async def _notify_template_blocked(media_type, media_id, query, rejected, template) -> None:
    """
    Tell the user a search found releases that the profile's safety template rejected
    and nothing else was acceptable, once per item per window, so a Trusted profile that
    keeps finding nothing is visible instead of looking like an empty search.
    """
    try:
        from app.services.notifications import create_notification

        name = {"trusted": "Trusted", "balanced": "Balanced"}.get(template or "", template or "")
        await create_notification(
            type=f"template_blocked_{media_type}_{media_id}",
            title=f"No allowed release for {query}",
            message=(
                f"Found {rejected} release(s), none allowed by the {name} template. "
                "Switching the profile to Balanced allows more sources."
            ),
            severity="info",
            data={"media_type": media_type, "media_id": media_id, "template": template, "rejected": rejected},
            dedup_window_seconds=7 * 24 * 3600,
        )
    except Exception as e:
        print(f"Could not send the template notice for {query}: {e}")


async def _fetch_blocklisted_titles(conn, media_type, media_id) -> set:
    """
    Return the set of release titles blocklisted for a media item (lowercased for
    case-insensitive matching). Music types map to the 'album' blocklist scope. Returns an
    empty set when no connection/item is given or on error, so search never fails on this.
    """
    if conn is None or media_id is None or not media_type:
        return set()
    normalized = "album" if media_type in ("music", "track", "album") else media_type
    try:
        rows = await conn.fetch(
            "SELECT release_title FROM blocklist WHERE media_type = $1 AND media_id = $2",
            normalized,
            media_id,
        )
        return {r["release_title"].strip().lower() for r in rows if r["release_title"]}
    except Exception as e:
        print(f"Could not load blocklist for {media_type} {media_id}: {e}")
        return set()


class SearchEngine:
    """
    Cascading Search Engine

    Search Strategy:
    1. Start with highest quality from profile
    2. Search with quality suffix (e.g., "Movie 2160p")
    3. Filter by allowed uploaders/groups
    4. If no results, try next uploader at same quality
    5. If exhausted all uploaders, cascade to next lower quality
    6. Stop as soon as acceptable release is found
    """

    def __init__(self):
        self.general_indexers = [
            leetx_indexer,
            yts_indexer,
        ]
        # YTS lists only movies, so TV searches without a profile indexer list use 1337x alone.
        self.show_indexers = [
            leetx_indexer,
        ]
        # Nyaa only for anime - best quality releases with proper fansubs
        self.nyaa_indexer = NyaaIndexer()
        self.anime_indexers = [
            self.nyaa_indexer,
        ]
        # 1337x for music torrents
        self.music_indexers = [
            leetx_indexer,
        ]

    async def _search_indexer_with_retry(
        self, indexer, query, category, limit_per_indexer, max_retries, search_stats=None
    ):
        """
        Search a single indexer, retrying on transient errors up to max_retries times
        with a short backoff. Returns an empty list when every attempt fails, and records
        the failure in search_stats["indexer_errors"] and the indexer's health so an
        outage is told apart from a search that found nothing.
        """
        name = getattr(indexer, "name", str(indexer))
        attempts = max(0, max_retries) + 1
        for attempt in range(attempts):
            try:
                results = await indexer.search(query, category, limit_per_indexer)
                await indexer_health.record_success(name)
                return results
            except Exception as e:
                if attempt >= attempts - 1:
                    print(f"Indexer {name} failed after {attempt + 1} attempt(s): {e}")
                    if search_stats is not None:
                        search_stats.setdefault("indexer_errors", {})[name] = str(e)[:300]
                    await indexer_health.record_failure(name, str(e))
                    return []
                await asyncio.sleep(min(2**attempt, 5))
        return []

    async def search_all_indexers(
        self,
        query: str,
        category: Optional[str] = None,
        limit_per_indexer: int = 50,
        media_type: Optional[str] = None,
        selected_indexers: Optional[List[str]] = None,
        timeout: int = 30,
        max_results: int = 100,
        max_retries: int = 0,
        search_stats: Optional[dict] = None,
    ) -> List[TorrentRelease]:
        """
        Search all enabled indexers in parallel.
        Returns combined and deduplicated results.
        Uses selected_indexers if provided, otherwise falls back to type-based defaults.
        search_stats, when given, gets live_queries incremented for every sweep
        that actually reaches the indexers. Cache hits and local-index answers
        never count, so callers can rate-limit only real indexer traffic.
        """
        tasks = []
        await custom_indexers.ensureLoaded()

        # Use selected indexers if provided
        if selected_indexers:
            indexers = [self._indexer_by_name(name) for name in selected_indexers if self._indexer_by_name(name)]
        # Fall back to media type based selection
        elif media_type == "anime":
            indexers = list(self.anime_indexers)
        elif media_type == "music":
            indexers = list(self.music_indexers)
            category = "music"  # Force music category for 1337x
        elif media_type in ("show", "episode"):
            indexers = list(self.show_indexers)
        else:
            indexers = list(self.general_indexers)

        # A profile's indexer list decides which user-defined indexers it searches, the same
        # as built-in ones. Without a list, every user-defined indexer enabled for search
        # joins searches of the media types it covers.
        context = search_context.current()
        scope = context.scope if context and context.scope else search_context.scopeFor(media_type, category)
        indexers = [indexer for indexer in indexers if getattr(indexer, "searchEnabled", True)]
        if not selected_indexers:
            for indexer in custom_indexers.searchIndexers(scope):
                if indexer not in indexers:
                    indexers.append(indexer)

        # Short-TTL cache so repeated identical searches (re-runs, cascade retries,
        # search-again after blocklist) skip the indexer round trip. Magnets are
        # resolved on demand at download time, so cached results are complete.
        cache_key = self._search_cache_key(query, category, media_type, selected_indexers)
        cached = await cacheGet(cache_key)
        if cached is not None:
            return [TorrentRelease.from_dict(item) for item in cached][:max_results]

        if search_stats is not None:
            search_stats["live_queries"] = search_stats.get("live_queries", 0) + 1

        for indexer in indexers:
            task = asyncio.create_task(
                self._search_indexer_with_retry(indexer, query, category, limit_per_indexer, max_retries, search_stats)
            )
            tasks.append(task)

        # Run with timeout, preserving partial results
        done, pending = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.ALL_COMPLETED)

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        if pending:
            print(f"Search timeout after {timeout}s - {len(done)} indexers completed, {len(pending)} cancelled")

        # Collect results from completed tasks
        all_releases = []
        for task in done:
            try:
                result = task.result()
                if not isinstance(result, Exception):
                    all_releases.extend(result)
            except Exception as e:
                print(f"Indexer error: {e}")

        # When every indexer failed or timed out, the empty result says nothing about
        # whether the item exists, so callers leave the search backoff unchanged.
        if search_stats is not None and indexers:
            failed = len(search_stats.get("indexer_errors", {})) + len(pending)
            if not all_releases and failed >= len(indexers):
                search_stats["all_indexers_failed"] = True

        # Merge copies of the same torrent (by hash, or title and size) and set each
        # release's trust category, so a copy found through ext.to and through 1337x
        # counts once with the best trust and every site it is listed on.
        unique_releases = await release_trust.annotate(all_releases)

        # Persist everything the live sweep saw into the local release index so
        # future searches can answer locally.
        await release_index.upsertReleases(unique_releases)

        # Limit total results
        result = unique_releases[:max_results]

        # Cache non-empty result sets for a short window (10 minutes). Empty results are
        # never cached, so a transient failure or a Cloudflare challenge is retried on the
        # next search (which also refreshes the clearance) instead of returning empty for
        # the whole window.
        if result:
            await cacheSet(cache_key, [release.to_dict() for release in result], expire=600)

        return result

    def _indexer_by_name(self, name: Optional[str]):
        """Resolve an indexer instance from its display name, built-in or user-defined."""
        return {
            "1337x": leetx_indexer,
            "YTS": yts_indexer,
            "Nyaa": self.nyaa_indexer,
            "ext.to": extto_indexer,
        }.get(
            name
        ) or custom_indexers.byName(name)

    def _search_cache_key(self, query, category, media_type, selected_indexers) -> str:
        """
        Build a deterministic cache key for a search. The user-defined indexer set and the
        item ids are part of it, because indexers that search by id answer per item.
        """
        idx = ",".join(sorted(selected_indexers)) if selected_indexers else (media_type or "auto")
        context = search_context.current()
        item = (
            f"{context.imdbId}|{context.tmdbId}|{context.tvdbId}|{context.season}|{context.episode}|{context.artist}"
            if context
            else ""
        )
        raw = f"{query}|{category}|{media_type}|{idx}|{custom_indexers.versionTag()}|{item}".lower()
        return "idxsearch:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()

    async def resolve_download_source(self, release: TorrentRelease) -> None:
        """
        Fill a chosen release's magnet or torrent source on demand. Search defers this
        for indexers that need a detail-page fetch (1337x), so only the selected
        release pays the cost instead of every result.
        """
        if release.torrent_url or release.magnet:
            return
        indexer = self._indexer_by_name(release.indexer)
        if not indexer:
            return
        try:
            await indexer.ensure_download_source(release)
            # Remember the resolved magnet so a future pick of the same release
            # from the local index skips the detail-page fetch entirely.
            if release.magnet or release.torrent_url:
                await release_index.upsertReleases([release])
        except Exception as e:
            print(f"Failed to resolve download source for '{release.title}': {e}")

    def _filter_and_select(
        self,
        releases: List[TorrentRelease],
        profile: MediaProfile,
        media_type: Optional[str],
        preferred_uploaders: Optional[List[str]],
        blocked_uploaders: Optional[List[str]],
        blocklisted_titles: Optional[set],
        match_target=None,
        rejection_stats: Optional[dict] = None,
        site_deferred: Optional[list] = None,
    ) -> Optional[TorrentRelease]:
        """
        Apply the full profile gate (item match, blocklist, minimum requirements,
        blocked uploaders, anime rules) to a batch and return the highest-scoring release.
        score_release ranks by the profile's preference order across resolution,
        source, codec, audio, and HDR, so this preserves the cascade priorities.
        When site_deferred is a list, releases that pass every gate except a Balanced
        site rejection a detail page could reverse are added to it instead of dropped.
        """
        template = getattr(profile, "safety_template", "open")
        filtered_releases = []
        for release in releases:
            # Skip releases of a different title, year, season or episode.
            if not release_matching.releaseMatches(release.title, match_target):
                continue
            if match_target is not None and match_target.releaseCheck and not match_target.releaseCheck(release):
                continue

            # Skip releases the user has blocklisted for this item.
            if blocklisted_titles and (release.title or "").strip().lower() in blocklisted_titles:
                continue

            # Skip releases the profile's safety template does not allow, unless a detail
            # page could show the release is also on a site the template allows.
            allowed, _reason = release_trust.isAllowed(release, template)
            needsSiteCheck = False
            if not allowed:
                if rejection_stats is not None:
                    rejection_stats["template_rejected"] = rejection_stats.get("template_rejected", 0) + 1
                if site_deferred is None or not release_trust.siteCheckCouldAllow(release, template):
                    continue
                needsSiteCheck = True

            if not media_profile_service._meets_minimum_requirements(release, profile, media_type):
                continue

            if blocked_uploaders and release.uploader in blocked_uploaders:
                continue

            # Anime-specific filtering
            if media_type == "anime" and not self._meets_anime_requirements(release, profile):
                continue

            (site_deferred if needsSiteCheck else filtered_releases).append(release)

        if not filtered_releases:
            return None

        return media_profile_service.select_best_release(
            filtered_releases,
            profile,
            preferred_uploaders,
            blocked_uploaders,
            media_type,
        )

    async def _select_with_site_check(
        self,
        releases: List[TorrentRelease],
        profile: MediaProfile,
        media_type: Optional[str],
        preferred_uploaders: Optional[List[str]],
        blocked_uploaders: Optional[List[str]],
        blocklisted_titles: Optional[set],
        match_target=None,
        rejection_stats: Optional[dict] = None,
    ) -> Optional[TorrentRelease]:
        """_filter_and_select, then a detail-page site check of deferred releases that would outrank its pick."""
        deferred: List[TorrentRelease] = []
        best = self._filter_and_select(
            releases,
            profile,
            media_type,
            preferred_uploaders,
            blocked_uploaders,
            blocklisted_titles,
            match_target,
            rejection_stats,
            site_deferred=deferred,
        )
        if not deferred:
            return best

        def rank(release):
            return media_profile_service.score_release(
                release, profile, preferred_uploaders, blocked_uploaders, media_type
            )

        return await self._confirm_deferred_sites(best, deferred, profile, rank)

    async def _confirm_deferred_sites(self, best, deferred, profile, rank):
        """
        Read the detail pages of releases a Balanced profile rejected only for their site,
        best ranked first, and return the first one the full site list shows is allowed.
        Only releases that would outrank the current pick are read, and no more than
        SITE_CHECKS_PER_SELECTION of them, so a search costs at most that many page reads.
        Each site list read is stored in the release index so later searches already know it.
        """
        template = getattr(profile, "safety_template", "open")
        bestRank = rank(best) if best is not None else None
        checked = 0
        for release in sorted(deferred, key=rank, reverse=True):
            releaseRank = rank(release)
            if isinstance(releaseRank, (int, float)) and releaseRank < 0:
                continue
            if bestRank is not None and releaseRank <= bestRank:
                break
            if checked >= SITE_CHECKS_PER_SELECTION:
                break
            checked += 1
            try:
                await extto_indexer.refresh_sites(release)
            except Exception as e:
                print(f"Could not read the sites for '{release.title}': {e}")
                continue
            await release_index.addOriginSites(release.indexer, release.detail_url, release.origin_sites)
            allowed, _reason = release_trust.isAllowed(release, template)
            if not allowed:
                continue
            print(f"[OK] Detail page shows '{release.title}' is also on {', '.join(release.origin_sites)}")
            return release
        return best

    async def cascading_search(
        self,
        base_query: str,
        profile: MediaProfile,
        category: Optional[str] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
        blocklisted_titles: Optional[set] = None,
        search_stats: Optional[dict] = None,
        match_target=None,
    ) -> Optional[TorrentRelease]:
        """
        Broad-first cascading search.

        Stage 1: the local release index, filtered and scored against the full
                 profile. Zero indexer round trips when the answer is already known.
        Stage 2: one broad live sweep (title only) of the selected indexers, with
                 the whole profile cascade applied locally to the results. Because
                 scoring ranks by the profile's preference order, this selects the
                 same release the old per-combination sweeps would have chosen.
        Stage 3: targeted gap sweeps, only when the broad results had nothing
                 acceptable: resolution by resolution in profile priority order,
                 expanded through naming synonyms (2160p also searches 4K and UHD),
                 then per preferred uploader, cascading down exactly like before.

        Sources, codecs, HDR, and audio remain hard gates and ranking dimensions
        via the profile filter and score, they are just no longer query keywords,
        which previously dropped any release whose title used a different spelling.
        """
        resolution_order = self._get_quality_cascade(profile, media_type)
        uploader_order = profile.uploaders or [None]

        # Get per-media-type indexers
        selected_indexers = profile.get_indexers_for_type(media_type) if media_type else None

        # Get search timing settings from profile
        search_timeout = profile.search_timeout
        max_results = profile.max_results

        print(f"Cascading search: {base_query}")
        print(f"Resolution order: {resolution_order}")
        print(f"Uploader order: {uploader_order}")
        if selected_indexers:
            print(f"Selected indexers: {selected_indexers}")

        # Stage 1: local index. Skipped for anime because subtitle/audio metadata
        # (hardsub, dual audio) only exists on live Nyaa results and the profile
        # rules cannot be verified against index rows.
        if media_type != "anime":
            local_releases = await release_index.searchLocal(
                base_query,
                media_type=media_type,
                limit=200,
                max_age_days=LOCAL_INDEX_MAX_AGE_DAYS,
            )
            local_releases = await release_trust.annotate(local_releases)
            best_release = await self._select_with_site_check(
                local_releases,
                profile,
                media_type,
                preferred_uploaders,
                blocked_uploaders,
                blocklisted_titles,
                match_target,
                search_stats,
            )
            if best_release:
                print(
                    f"[OK] Selected from local index: {best_release.title} ({best_release.quality}, {best_release.seeders} seeders)"
                )
                return best_release

        # Stage 2: broad live sweep, filtered locally.
        print(f"\nBroad query: {base_query}")
        releases = await self.search_all_indexers(
            base_query,
            category,
            limit_per_indexer=50,
            media_type=media_type,
            selected_indexers=selected_indexers,
            timeout=search_timeout,
            max_results=max_results,
            max_retries=profile.max_retries,
            search_stats=search_stats,
        )
        best_release = await self._select_with_site_check(
            releases,
            profile,
            media_type,
            preferred_uploaders,
            blocked_uploaders,
            blocklisted_titles,
            match_target,
            search_stats,
        )
        if best_release:
            print(
                f"[OK] Selected from broad sweep: {best_release.title} ({best_release.quality}, {best_release.seeders} seeders)"
            )
            return best_release

        # Stage 3: targeted gap sweeps per resolution synonym and uploader.
        for resolution in resolution_order:
            for variant in RESOLUTION_QUERY_SYNONYMS.get(resolution, [resolution]):
                for uploader in uploader_order:
                    query = f"{base_query} {variant}"
                    if uploader:
                        query += f" {uploader}"

                    print(f"\nQuery: {query}")

                    releases = await self.search_all_indexers(
                        query,
                        category,
                        limit_per_indexer=50,
                        media_type=media_type,
                        selected_indexers=selected_indexers,
                        timeout=search_timeout,
                        max_results=max_results,
                        max_retries=profile.max_retries,
                        search_stats=search_stats,
                    )

                    if not releases:
                        continue

                    best_release = await self._select_with_site_check(
                        releases,
                        profile,
                        media_type,
                        preferred_uploaders,
                        blocked_uploaders,
                        blocklisted_titles,
                        match_target,
                        search_stats,
                    )

                    if not best_release:
                        continue

                    print(f"\n[OK] Selected: {best_release.title}")
                    print(f"  Resolution: {best_release.quality}")
                    print(f"  Source: {best_release.source}")
                    print(f"  Codec: {best_release.codec}")
                    print(f"  HDR: {best_release.hdr}")
                    print(f"  Uploader: {best_release.uploader}")
                    print(f"  Seeders: {best_release.seeders}")

                    return best_release

        print(f"\n[FAIL] No acceptable release found")
        return None

    async def search_and_select(
        self,
        query: str,
        profile: MediaProfile,
        category: Optional[str] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
    ) -> Optional[TorrentRelease]:
        """
        Search with cascading quality strategy
        """
        return await self.cascading_search(
            query, profile, category, preferred_uploaders, blocked_uploaders, media_type
        )

    async def search_and_download(
        self,
        query: str,
        profile: MediaProfile,
        save_path: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
        history_conn=None,
        history_media_id: Optional[int] = None,
        current_quality: Optional[str] = None,
        grab_mode: str = "auto",
        upgrade_allowed: Optional[bool] = None,
        search_stats: Optional[dict] = None,
        episode_target: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Search with cascading quality, select best, and download.
        Returns torrent hash if successful. When history_conn and history_media_id
        are provided, records a download_history row (with the re-addable source).
        When current_quality is provided, only grabs a release that is an upgrade;
        upgrade_allowed is the effective per-item decision (item override, else profile)
        and lets a per-item override drive the upgrade regardless of the profile default.
        episode_target (season, episode, absolute_episode) aims a show or anime search at
        one episode. With a library list in it (every episode of the series that has a file,
        with its quality) a pack is accepted only when it holds the episode and every
        library episode it holds would get a better file. Without one, only releases of
        that single episode are accepted.
        """
        if search_stats is None:
            search_stats = {}
        # Skip releases the user has blocklisted for this item (auto-search only).
        blocklisted_titles = set(await _fetch_blocklisted_titles(history_conn, media_type, history_media_id) or ())
        match_target = await _load_match_target(history_conn, media_type, history_media_id, query, episode_target)
        if match_target is not None and episode_target and episode_target.get("library") is not None:
            match_target.releaseCheck = _episodeUpgradeCheck(
                match_target, episode_target["library"], profile, media_type, upgrade_allowed
            )
        # The item's ids, for indexers that search by IMDb, TMDB or TVDB id.
        itemContext = await search_context.forItem(history_conn, media_type, history_media_id, match_target)
        for _attempt in range(_BLOCKED_RESELECT_LIMIT):
            with search_context.using(itemContext):
                best_release = await self.cascading_search(
                    query,
                    profile,
                    category,
                    preferred_uploaders,
                    blocked_uploaders,
                    media_type,
                    blocklisted_titles=blocklisted_titles,
                    search_stats=search_stats,
                    match_target=match_target,
                )

            if not best_release:
                if search_stats.get("template_rejected") and history_media_id:
                    await _notify_template_blocked(
                        media_type,
                        history_media_id,
                        query,
                        search_stats["template_rejected"],
                        getattr(profile, "safety_template", None),
                    )
                return None

            # Upgrade mode: only proceed when the found release beats the current quality.
            if current_quality:
                if not media_profile_service.needs_upgrade(
                    current_quality,
                    best_release.quality,
                    profile,
                    media_type,
                    upgrade_allowed=upgrade_allowed,
                ):
                    return None

            # Resolve the magnet on demand for the one release we are grabbing, then
            # skip it and pick again when its hash failed validation before.
            await self.resolve_download_source(best_release)
            if not await _isReleaseHashBlocked(history_conn, best_release, media_type, history_media_id):
                break
            print(f"Skipping blocklisted torrent: {best_release.title}")
            blocklisted_titles.add((best_release.title or "").strip().lower())
        else:
            return None

        # Prefer .torrent file if available, fallback to magnet
        torrent_source = best_release.torrent_url or best_release.magnet

        if not torrent_source:
            print(f"No download source for release: {best_release.title}")
            return None

        try:
            client = await get_qbittorrent_client()
            if not client:
                print("qBittorrent client not configured")
                return None

            # Resolve the paired root folder so the torrent downloads into the hardlink
            # folder and the organizer knows where to place it. An explicit save_path (rare)
            # takes precedence.
            root_folder_id = None
            if save_path is None:
                folder = await _resolve_grab_folder(history_conn, media_type, history_media_id)
                if folder:
                    save_path = folder["download_path"]
                    root_folder_id = folder["id"]

            # Add torrent paused with validating tag for pre-download validation
            validation_tags = (tags or []) + ["validating"]
            torrent_hash = await client.add_torrent(
                torrent=torrent_source,
                save_path=save_path,
                category=category,
                tags=validation_tags,
                paused=True,
            )

            print(f"[OK] Added to download client (pending validation): {torrent_hash}")

            # Record the full history row (with re-addable source) when the caller
            # supplies a DB connection and media id.
            if history_conn is not None and history_media_id is not None:
                await _record_download_history(
                    history_conn,
                    torrent_hash,
                    best_release,
                    history_media_id,
                    media_type or "movie",
                    grab_mode=grab_mode,
                    was_upgrade=(grab_mode == "upgrade"),
                    root_folder_id=root_folder_id,
                    safety_template=getattr(profile, "safety_template", None),
                )

            # Trigger validation immediately after adding
            validation_result = await validate_and_resume_torrent(
                torrent_hash=torrent_hash,
                client=client,
                profile=profile,
                media_type=media_type or "movie",
            )
            print(f"Validation result: {validation_result.message}")

            return torrent_hash

        except Exception as e:
            print(f"Error adding torrent to client: {e}")
            return None

    async def get_rss_updates(self) -> List[TorrentRelease]:
        """
        Get recent releases from all indexers (RSS monitoring).
        Pulls the newest-uploads stream per category so shows, anime, and music are
        covered rather than only movies, deduplicates across feeds, and persists
        everything into the local release index.
        """
        # (indexer, category) per feed. 1337x new-upload listings are per category,
        # YTS covers movies, Nyaa's RSS covers anime.
        feeds = [
            (leetx_indexer, "movies"),
            (leetx_indexer, "tv"),
            (leetx_indexer, "anime"),
            (leetx_indexer, "music"),
            (yts_indexer, None),
            (self.nyaa_indexer, None),
        ]
        # User-defined indexers enabled for RSS read their own newest-uploads feed.
        await custom_indexers.ensureLoaded()
        feeds.extend((indexer, None) for indexer in custom_indexers.rssIndexers())

        tasks = [indexer.get_rss(category) for indexer, category in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_releases = []
        seen_keys = set()
        for result in results:
            if isinstance(result, Exception):
                print(f"Indexer RSS error: {result}")
                continue
            for release in result:
                key = release_index.dedupeKey(release)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_releases.append(release)

        # Every RSS cycle grows the local index for free.
        await release_index.upsertReleases(all_releases)

        return all_releases

    def _get_quality_cascade(self, profile: MediaProfile, media_type: Optional[str] = None) -> List[str]:
        """
        Build quality cascade order from profile resolutions.
        Uses per-media-type resolutions (no fallback).
        Resolutions list is already ordered by preference (highest priority first)
        """
        resolutions = profile.get_resolutions_for_type(media_type) if media_type else []
        return resolutions

    def _meets_anime_requirements(self, release: TorrentRelease, profile: MediaProfile) -> bool:
        """
        Check if anime release meets profile-specific anime requirements
        Filters by: audio language, subtitle language, hardsub/softsub, dual audio
        """
        if not release.raw_data:
            return True

        raw_data = release.raw_data

        # Get anime preferences from profile
        anime_subtitle_pref = getattr(profile, "anime_subtitle_preference", "softsub")
        anime_allow_hardsub = getattr(profile, "anime_allow_hardsub", False)
        anime_prefer_dual_audio = getattr(profile, "anime_prefer_dual_audio", False)
        anime_audio_lang = getattr(profile, "anime_audio_language", "ja")
        anime_subtitle_lang = getattr(profile, "anime_subtitle_language", "en")

        subtitle_type = raw_data.get("subtitle_type")
        audio_language = raw_data.get("audio_language")
        subtitle_language = raw_data.get("subtitle_language")

        # Filter by audio language if detected
        if audio_language and audio_language != anime_audio_lang:
            # Allow dual audio if it contains preferred language
            if not (subtitle_type == "dual_audio" and anime_audio_lang in ["ja", "en"]):
                return False

        # Filter by subtitle language if detected
        if subtitle_language and subtitle_language != anime_subtitle_lang:
            return False

        # Filter by dual audio preference
        if anime_prefer_dual_audio and subtitle_type != "dual_audio":
            return False

        # Filter by hardsub/softsub
        if subtitle_type == "hardsub" and not anime_allow_hardsub:
            return False

        if anime_subtitle_pref == "softsub" and subtitle_type == "hardsub" and not anime_allow_hardsub:
            return False

        # Block raw releases (no subtitles)
        if subtitle_type == "raw":
            return False

        return True

    async def music_cascading_search(
        self,
        query: str,
        profile: MediaProfile,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        blocklisted_titles: Optional[set] = None,
        min_tier: Optional[str] = None,
        search_stats: Optional[dict] = None,
        match_target=None,
    ) -> Optional[TorrentRelease]:
        """
        Music cascading search over the profile's allowed quality tiers, highest
        quality first. Each tier maps to a search term (the lossless rungs share the
        FLAC search since a title rarely states bit depth or sample rate), and the
        first tier that yields an allowed release wins.

        min_tier restricts the search to tiers strictly above a current tier, used by
        the upgrade search so it never re-downloads the same or lower quality.
        """
        allowed = getattr(profile, "music_quality_tiers", None) or music_quality.DEFAULT_TIERS
        # Order allowed tiers highest quality first for the cascade.
        ordered = sorted(set(allowed), key=music_quality.rank, reverse=True)
        if min_tier is not None:
            ordered = [tier for tier in ordered if music_quality.rank(tier) > music_quality.rank(min_tier)]
            if not ordered:
                return None
        allowed_set = set(ordered)

        selected_indexers = profile.get_indexers_for_type("music")
        search_timeout = profile.search_timeout
        max_results = profile.max_results

        # Dedupe the per-tier search terms while preserving the highest-first order.
        seen_terms = set()
        search_plan = []
        for tier in ordered:
            term = music_quality.SEARCH_TERMS.get(tier, "")
            if term in seen_terms:
                continue
            seen_terms.add(term)
            search_plan.append(term)

        print(f"Music cascading search: {query}")
        print(f"Allowed tiers (high to low): {ordered}")
        if selected_indexers:
            print(f"Selected indexers: {selected_indexers}")

        template = getattr(profile, "safety_template", "open")

        def music_filter(candidates, deferred):
            """
            Item match, blocklist, uploader, and tier gate shared by the local and live
            passes. Releases a detail page could move past a Balanced site rejection go to
            deferred instead of being dropped.
            """
            kept = []
            for release in candidates:
                if not release_matching.releaseMatches(release.title, match_target):
                    continue
                allowed, _reason = release_trust.isAllowed(release, template)
                needsSiteCheck = False
                if not allowed:
                    if search_stats is not None:
                        search_stats["template_rejected"] = search_stats.get("template_rejected", 0) + 1
                    if not release_trust.siteCheckCouldAllow(release, template):
                        continue
                    needsSiteCheck = True
                if blocklisted_titles and (release.title or "").strip().lower() in blocklisted_titles:
                    continue
                if blocked_uploaders and release.uploader in blocked_uploaders:
                    continue
                tier = self._release_tier(release)
                # Accept a release whose tier is unknown so a mislabeled torrent is not
                # dropped, unless an allowed set or min_tier would exclude it.
                if tier is not None:
                    if tier not in allowed_set:
                        continue
                    if min_tier is not None and music_quality.rank(tier) <= music_quality.rank(min_tier):
                        continue
                elif min_tier is not None:
                    continue
                (deferred if needsSiteCheck else kept).append(release)
            return kept

        def rank(release):
            return self._music_rank(release, preferred_uploaders)

        # Local index pass first: zero indexer round trips when the album is known.
        local_deferred: List[TorrentRelease] = []
        local_candidates = music_filter(
            await release_trust.annotate(
                await release_index.searchLocal(
                    query, media_type="music", limit=200, max_age_days=LOCAL_INDEX_MAX_AGE_DAYS
                )
            ),
            local_deferred,
        )
        if local_candidates or local_deferred:
            best_release = self._select_best_music_release(local_candidates, profile, preferred_uploaders)
            best_release = await self._confirm_deferred_sites(best_release, local_deferred, profile, rank)
            if best_release:
                print(
                    f"[OK] Selected from local index: {best_release.title} (tier {self._release_tier(best_release)})"
                )
                return best_release

        for search_term in search_plan:
            search_query = f"{query} {search_term}".strip()

            print(f"\nSearching: {search_query}")

            releases = await self.search_all_indexers(
                search_query,
                category="music",
                limit_per_indexer=50,
                media_type="music",
                selected_indexers=selected_indexers,
                timeout=search_timeout,
                max_results=max_results,
                max_retries=profile.max_retries,
                search_stats=search_stats,
            )

            if not releases:
                continue

            deferred: List[TorrentRelease] = []
            filtered_releases = music_filter(releases, deferred)

            if not filtered_releases and not deferred:
                continue

            best_release = self._select_best_music_release(filtered_releases, profile, preferred_uploaders)
            best_release = await self._confirm_deferred_sites(best_release, deferred, profile, rank)

            if best_release:
                print(f"\n[OK] Selected: {best_release.title}")
                print(f"  Tier: {self._release_tier(best_release)}")
                print(f"  Format: {best_release.audio_format}")
                print(f"  Seeders: {best_release.seeders}")
                return best_release

        print(f"\n[FAIL] No acceptable music release found")
        return None

    def _release_tier(self, release: TorrentRelease) -> Optional[str]:
        """Best-effort music quality tier for a release from its parsed title fields."""
        return getattr(release, "quality_tier", None) or music_quality.tier_from_release(release)

    def _meets_music_requirements(self, release: TorrentRelease, profile: MediaProfile) -> bool:
        """Whether a release's quality tier is in the profile's allowed tiers."""
        allowed = getattr(profile, "music_quality_tiers", None)
        if not allowed:
            return True
        tier = self._release_tier(release)
        # Accept when the tier cannot be determined so a mislabeled torrent is not dropped.
        if tier is None:
            return True
        return tier in allowed

    def _select_best_music_release(
        self,
        releases: List[TorrentRelease],
        profile: MediaProfile,
        preferred_uploaders: Optional[List[str]] = None,
    ) -> Optional[TorrentRelease]:
        """
        Select the best music release. Ranks by parsed quality tier first, then by
        preferred uploader, then by seeders.
        """
        if not releases:
            return None
        releases.sort(key=lambda release: self._music_rank(release, preferred_uploaders), reverse=True)
        return releases[0]

    def _music_rank(self, release: TorrentRelease, preferred_uploaders: Optional[List[str]] = None) -> tuple:
        """Music ranking key, by quality tier, then preferred uploader, then seeders."""
        tier_score = music_quality.rank(self._release_tier(release))
        uploader_score = 1 if preferred_uploaders and release.uploader in preferred_uploaders else 0
        return (tier_score, uploader_score, release.seeders or 0)

    async def search_music_and_download(
        self,
        query: str,
        profile: MediaProfile,
        save_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        history_conn=None,
        history_media_id: Optional[int] = None,
        current_quality: Optional[str] = None,
        grab_mode: str = "auto",
        upgrade_allowed: Optional[bool] = None,
        search_stats: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Search for music across the profile's quality tiers, select the best release,
        and download. Returns torrent hash if successful. When history_conn and
        history_media_id are provided, records a download_history row.

        For an upgrade (grab_mode 'upgrade' with current_quality set as the album's
        current tier), the search only considers tiers above the current one and only
        proceeds when the found release beats it.
        """
        upgrade = grab_mode == "upgrade" and current_quality is not None
        if search_stats is None:
            search_stats = {}
        blocklisted_titles = set(await _fetch_blocklisted_titles(history_conn, "album", history_media_id) or ())
        match_target = await _load_match_target(history_conn, "album", history_media_id, query)
        # The artist and album, for indexers that search those fields.
        itemContext = await search_context.forItem(history_conn, "album", history_media_id, match_target)
        for _attempt in range(_BLOCKED_RESELECT_LIMIT):
            with search_context.using(itemContext):
                best_release = await self.music_cascading_search(
                    query,
                    profile,
                    preferred_uploaders,
                    blocked_uploaders,
                    blocklisted_titles=blocklisted_titles,
                    min_tier=current_quality if upgrade else None,
                    search_stats=search_stats,
                    match_target=match_target,
                )

            if not best_release:
                if search_stats.get("template_rejected") and history_media_id:
                    await _notify_template_blocked(
                        "album",
                        history_media_id,
                        query,
                        search_stats["template_rejected"],
                        getattr(profile, "safety_template", None),
                    )
                return None

            # Upgrade gate: only proceed when the found release is a worthwhile upgrade.
            if upgrade:
                candidate_tier = self._release_tier(best_release)
                if not music_quality.needs_music_upgrade(current_quality, candidate_tier, profile, upgrade_allowed):
                    return None

            # Resolve the magnet on demand for the one release we are grabbing, then
            # skip it and pick again when its hash failed validation before.
            await self.resolve_download_source(best_release)
            if not await _isReleaseHashBlocked(history_conn, best_release, "album", history_media_id):
                break
            print(f"Skipping blocklisted torrent: {best_release.title}")
            blocklisted_titles.add((best_release.title or "").strip().lower())
        else:
            return None

        torrent_source = best_release.torrent_url or best_release.magnet

        if not torrent_source:
            print(f"No download source for release: {best_release.title}")
            return None

        try:
            client = await get_qbittorrent_client()
            if not client:
                print("qBittorrent client not configured")
                return None

            # Resolve the paired music root folder (hardlink folder + organize target).
            root_folder_id = None
            if save_path is None:
                folder = await _resolve_grab_folder(history_conn, "album", history_media_id)
                if folder:
                    save_path = folder["download_path"]
                    root_folder_id = folder["id"]

            # Add torrent paused with validating tag for pre-download validation
            validation_tags = (tags or []) + ["validating"]
            torrent_hash = await client.add_torrent(
                torrent=torrent_source,
                save_path=save_path,
                category="music",
                tags=validation_tags,
                paused=True,
            )

            print(f"[OK] Added to download client (pending validation): {torrent_hash}")

            # Record the full history row (with re-addable source) when the caller
            # supplies a DB connection and media id.
            if history_conn is not None and history_media_id is not None:
                await _record_download_history(
                    history_conn,
                    torrent_hash,
                    best_release,
                    history_media_id,
                    "album",
                    grab_mode=grab_mode,
                    was_upgrade=(grab_mode == "upgrade"),
                    root_folder_id=root_folder_id,
                    safety_template=getattr(profile, "safety_template", None),
                )

            # Trigger validation immediately after adding
            validation_result = await validate_and_resume_torrent(
                torrent_hash=torrent_hash,
                client=client,
                profile=profile,
                media_type="album",
            )
            print(f"Validation result: {validation_result.message}")

            return torrent_hash

        except Exception as e:
            print(f"Error adding torrent to client: {e}")
            return None


search_engine = SearchEngine()
