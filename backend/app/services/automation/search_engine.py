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
from app.services.indexers.leetx import leetx_indexer
from app.services.indexers.yts import yts_indexer
from app.services.indexers.nyaa import NyaaIndexer
from app.services.media_profile import MediaProfile, media_profile_service
from app.services import music_quality
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.core.cache import cacheGet, cacheSet
from app.services.torrent_validator import validate_and_resume_torrent
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
) -> None:
    """
    Write a complete download_history row for an added release, including the magnet/
    .torrent source and info hash so it can be re-added later from the archive, plus the
    root_folder_id so the organizer can place the completed files. Keyed on torrent_hash and
    idempotent. Best effort, never raises.
    """
    try:
        await conn.execute(
            """
            INSERT INTO download_history (
                media_id, media_type, torrent_hash, torrent_title, indexer,
                quality, size, magnet_link, torrent_url, info_hash, status,
                grab_mode, was_upgrade, root_folder_id, download_client, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'downloading', $11, $12, $13, 'qbittorrent', NOW())
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
        )
    except Exception as e:
        print(f"Failed to record download history for {torrent_hash}: {e}")


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
        # Nyaa only for anime - best quality releases with proper fansubs
        self.nyaa_indexer = NyaaIndexer()
        self.anime_indexers = [
            self.nyaa_indexer,
        ]
        # 1337x for music torrents
        self.music_indexers = [
            leetx_indexer,
        ]

    async def _search_indexer_with_retry(self, indexer, query, category, limit_per_indexer, max_retries):
        """
        Search a single indexer, retrying on transient errors up to max_retries times
        with a short backoff. Returns an empty list when every attempt fails.
        """
        attempts = max(0, max_retries) + 1
        for attempt in range(attempts):
            try:
                return await indexer.search(query, category, limit_per_indexer)
            except Exception as e:
                if attempt >= attempts - 1:
                    print(f"Indexer {getattr(indexer, 'name', indexer)} failed after {attempt + 1} attempt(s): {e}")
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
    ) -> List[TorrentRelease]:
        """
        Search all enabled indexers in parallel.
        Returns combined and deduplicated results.
        Uses selected_indexers if provided, otherwise falls back to type-based defaults.
        """
        tasks = []

        # Use selected indexers if provided
        if selected_indexers:
            indexers = [self._indexer_by_name(name) for name in selected_indexers if self._indexer_by_name(name)]
        # Fall back to media type based selection
        elif media_type == "anime":
            indexers = self.anime_indexers
        elif media_type == "music":
            indexers = self.music_indexers
            category = "music"  # Force music category for 1337x
        else:
            indexers = self.general_indexers

        # Short-TTL cache so repeated identical searches (re-runs, cascade retries,
        # search-again after blocklist) skip the indexer round trip. Magnets are
        # resolved on demand at download time, so cached results are complete.
        cache_key = self._search_cache_key(query, category, media_type, selected_indexers)
        cached = await cacheGet(cache_key)
        if cached is not None:
            return [TorrentRelease.from_dict(item) for item in cached][:max_results]

        for indexer in indexers:
            task = asyncio.create_task(
                self._search_indexer_with_retry(indexer, query, category, limit_per_indexer, max_retries)
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

        # Deduplicate by info_hash
        seen_hashes = set()
        unique_releases = []

        for release in all_releases:
            if release.info_hash and release.info_hash in seen_hashes:
                continue

            if release.info_hash:
                seen_hashes.add(release.info_hash)

            unique_releases.append(release)

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
        """Resolve an indexer instance from its display name."""
        return {
            "1337x": leetx_indexer,
            "YTS": yts_indexer,
            "Nyaa": self.nyaa_indexer,
        }.get(name)

    def _search_cache_key(self, query, category, media_type, selected_indexers) -> str:
        """Build a deterministic cache key for a search."""
        idx = ",".join(sorted(selected_indexers)) if selected_indexers else (media_type or "auto")
        raw = f"{query}|{category}|{media_type}|{idx}".lower()
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
        except Exception as e:
            print(f"Failed to resolve download source for '{release.title}': {e}")

    async def cascading_search(
        self,
        base_query: str,
        profile: MediaProfile,
        category: Optional[str] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
        blocklisted_titles: Optional[set] = None,
    ) -> Optional[TorrentRelease]:
        """
        Multi-dimensional cascading search

        Priority order (highest to lowest):
        1. Resolution (from per-type resolutions, first = highest priority)
        2. Source (from per-type sources, first = highest priority)
        3. Codec (from per-type codecs, first = highest priority)
        4. HDR (from per-type hdr_formats, first = highest priority)
        5. Uploader (from profile.uploaders, first = highest priority)

        If value is in list: allowed
        If value NOT in list: rejected
        Position in list: determines search order (index 0 = try first)

        Example: ["2160p", "1080p"] + ["BluRay", "WEB-DL"] cascades:
        2160p BluRay -> 2160p WEB-DL -> 1080p BluRay -> 1080p WEB-DL
        """
        # Use per-media-type settings (no fallback)
        resolution_order = self._get_quality_cascade(profile, media_type)
        source_order = profile.get_sources_for_type(media_type) if media_type else []
        codec_order = profile.get_codecs_for_type(media_type) if media_type else []
        hdr_order = profile.get_hdr_formats_for_type(media_type) if media_type else []
        uploader_order = profile.uploaders or [None]

        # Get per-media-type indexers
        selected_indexers = profile.get_indexers_for_type(media_type) if media_type else None

        # Get search timing settings from profile
        search_timeout = profile.search_timeout
        max_results = profile.max_results

        # Ensure we have at least [None] for empty lists so iteration works
        source_order = source_order or [None]
        codec_order = codec_order or [None]
        hdr_order = hdr_order or [None]

        print(f"Cascading search: {base_query}")
        print(f"Resolution order: {resolution_order}")
        print(f"Source order: {source_order}")
        print(f"Codec order: {codec_order}")
        print(f"HDR order: {hdr_order}")
        print(f"Uploader order: {uploader_order}")
        if selected_indexers:
            print(f"Selected indexers: {selected_indexers}")

        # Multi-dimensional cascade
        for resolution in resolution_order:
            for source in source_order:
                for codec in codec_order:
                    for hdr in hdr_order:
                        for uploader in uploader_order:
                            # Build query with all specified attributes
                            query = f"{base_query} {resolution}"
                            if source:
                                query += f" {source}"
                            if codec:
                                query += f" {codec}"
                            if hdr:
                                query += f" {hdr}"
                            if uploader:
                                query += f" {uploader}"

                            print(f"\nQuery: {query}")

                            # Search indexers with per-type selection and timing
                            releases = await self.search_all_indexers(
                                query,
                                category,
                                limit_per_indexer=50,
                                media_type=media_type,
                                selected_indexers=selected_indexers,
                                timeout=search_timeout,
                                max_results=max_results,
                                max_retries=profile.max_retries,
                            )

                            if not releases:
                                continue

                            # Filter by profile requirements
                            filtered_releases = []
                            for release in releases:
                                # Skip releases the user has blocklisted for this item.
                                if blocklisted_titles and (release.title or "").strip().lower() in blocklisted_titles:
                                    continue

                                if not media_profile_service._meets_minimum_requirements(release, profile, media_type):
                                    continue

                                if blocked_uploaders and release.uploader in blocked_uploaders:
                                    continue

                                # Anime-specific filtering
                                if media_type == "anime" and not self._meets_anime_requirements(release, profile):
                                    continue

                                filtered_releases.append(release)

                            if not filtered_releases:
                                continue

                            # Score and select best from this batch
                            best_release = media_profile_service.select_best_release(
                                filtered_releases,
                                profile,
                                preferred_uploaders,
                                blocked_uploaders,
                                media_type,
                            )

                            if not best_release:
                                continue

                            # Found acceptable release!
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
    ) -> Optional[str]:
        """
        Search with cascading quality, select best, and download.
        Returns torrent hash if successful. When history_conn and history_media_id
        are provided, records a download_history row (with the re-addable source).
        When current_quality is provided, only grabs a release that is an upgrade;
        upgrade_allowed is the effective per-item decision (item override, else profile)
        and lets a per-item override drive the upgrade regardless of the profile default.
        """
        # Skip releases the user has blocklisted for this item (auto-search only).
        blocklisted_titles = await _fetch_blocklisted_titles(history_conn, media_type, history_media_id)
        best_release = await self.cascading_search(
            query,
            profile,
            category,
            preferred_uploaders,
            blocked_uploaders,
            media_type,
            blocklisted_titles=blocklisted_titles,
        )

        if not best_release:
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

        # Resolve the magnet on demand for the one release we are grabbing.
        await self.resolve_download_source(best_release)

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
        Get recent releases from all indexers (RSS monitoring)
        """
        tasks = []

        # Get RSS from both general and anime indexers
        all_indexers = self.general_indexers + self.anime_indexers

        for indexer in all_indexers:
            if hasattr(indexer, "get_rss"):
                task = indexer.get_rss()
                tasks.append(task)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_releases = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Indexer RSS error: {result}")
                continue
            all_releases.extend(result)

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
            )

            if not releases:
                continue

            filtered_releases = []
            for release in releases:
                # Skip releases the user has blocklisted for this album.
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

                filtered_releases.append(release)

            if not filtered_releases:
                continue

            best_release = self._select_best_music_release(filtered_releases, profile, preferred_uploaders)

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

        def score_release(release: TorrentRelease) -> tuple:
            tier_score = music_quality.rank(self._release_tier(release))
            uploader_score = 1 if preferred_uploaders and release.uploader in preferred_uploaders else 0
            return (tier_score, uploader_score, release.seeders)

        releases.sort(key=score_release, reverse=True)
        return releases[0]

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
        blocklisted_titles = await _fetch_blocklisted_titles(history_conn, "album", history_media_id)
        best_release = await self.music_cascading_search(
            query,
            profile,
            preferred_uploaders,
            blocked_uploaders,
            blocklisted_titles=blocklisted_titles,
            min_tier=current_quality if upgrade else None,
        )

        if not best_release:
            return None

        # Upgrade gate: only proceed when the found release is a worthwhile upgrade.
        if upgrade:
            candidate_tier = self._release_tier(best_release)
            if not music_quality.needs_music_upgrade(current_quality, candidate_tier, profile, upgrade_allowed):
                return None

        # Resolve the magnet on demand for the one release we are grabbing.
        await self.resolve_download_source(best_release)

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
