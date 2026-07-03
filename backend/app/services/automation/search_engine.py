"""
Cascading Search Engine

Search strategy:
1. Resolution-first: Search highest quality first, cascade down
2. Uploader-aware: Try all allowed uploaders at each quality level
3. Stop as soon as acceptable release is found
"""

from typing import List, Optional
import asyncio

from app.services.indexers.base import TorrentRelease
from app.services.indexers.leetx import leetx_indexer
from app.services.indexers.yts import yts_indexer
from app.services.indexers.nyaa import NyaaIndexer
from app.services.media_profile import MediaProfile, media_profile_service
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.torrent_validator import validate_and_resume_torrent


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

    async def search_all_indexers(
        self,
        query: str,
        category: Optional[str] = None,
        limit_per_indexer: int = 50,
        media_type: Optional[str] = None,
        selected_indexers: Optional[List[str]] = None,
        timeout: int = 30,
        max_results: int = 100,
    ) -> List[TorrentRelease]:
        """
        Search all enabled indexers in parallel.
        Returns combined and deduplicated results.
        Uses selected_indexers if provided, otherwise falls back to type-based defaults.
        """
        # Map indexer names to instances
        indexer_map = {
            "1337x": leetx_indexer,
            "YTS": yts_indexer,
            "Nyaa": self.nyaa_indexer,
            "Rutracker": None,  # Not implemented yet
        }

        tasks = []

        # Use selected indexers if provided
        if selected_indexers:
            indexers = [indexer_map[name] for name in selected_indexers if name in indexer_map and indexer_map[name]]
        # Fall back to media type based selection
        elif media_type == "anime":
            indexers = self.anime_indexers
        elif media_type == "music":
            indexers = self.music_indexers
            category = "music"  # Force music category for 1337x
        else:
            indexers = self.general_indexers

        for indexer in indexers:
            task = asyncio.create_task(indexer.search(query, category, limit_per_indexer))
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
        return unique_releases[:max_results]

    async def cascading_search(
        self,
        base_query: str,
        profile: MediaProfile,
        category: Optional[str] = None,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
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
                            )

                            if not releases:
                                continue

                            # Filter by profile requirements
                            filtered_releases = []
                            for release in releases:
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
    ) -> Optional[str]:
        """
        Search with cascading quality, select best, and download
        Returns torrent hash if successful
        """
        best_release = await self.cascading_search(
            query, profile, category, preferred_uploaders, blocked_uploaders, media_type
        )

        if not best_release:
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
    ) -> Optional[TorrentRelease]:
        """
        Music-specific cascading search

        Priority order (highest to lowest):
        1. Audio format (FLAC -> MP3 320 -> MP3 256 -> MP3 128)
        2. Uploader preferences

        Cascade: FLAC -> mp3_320 -> mp3_256 -> mp3_128 -> aac -> ogg
        """
        # Get preferred quality order from profile
        quality_order = getattr(profile, "music_preferred_quality", None) or [
            "flac",
            "mp3_320",
            "mp3_256",
            "mp3_128",
            "aac",
            "ogg",
        ]

        # Get per-media-type indexers and timing
        selected_indexers = profile.get_indexers_for_type("music")
        search_timeout = profile.search_timeout
        max_results = profile.max_results

        # Map quality values to search terms
        format_search_terms = {
            "flac": "FLAC",
            "mp3_320": "MP3 320",
            "mp3_256": "MP3 256",
            "mp3_128": "MP3 128",
            "aac": "AAC",
            "ogg": "OGG",
        }

        print(f"Music cascading search: {query}")
        print(f"Quality order: {quality_order}")
        if selected_indexers:
            print(f"Selected indexers: {selected_indexers}")

        for quality in quality_order:
            search_term = format_search_terms.get(quality, quality.upper())
            search_query = f"{query} {search_term}"

            print(f"\nSearching: {search_query}")

            releases = await self.search_all_indexers(
                search_query,
                category="music",
                limit_per_indexer=50,
                media_type="music",
                selected_indexers=selected_indexers,
                timeout=search_timeout,
                max_results=max_results,
            )

            if not releases:
                continue

            # Filter by quality and preferences
            filtered_releases = []
            for release in releases:
                if not self._meets_music_requirements(release, profile):
                    continue

                if blocked_uploaders and release.uploader in blocked_uploaders:
                    continue

                filtered_releases.append(release)

            if not filtered_releases:
                continue

            # Select best release (most seeders for music)
            best_release = self._select_best_music_release(filtered_releases, profile, preferred_uploaders)

            if best_release:
                print(f"\n[OK] Selected: {best_release.title}")
                print(f"  Format: {best_release.audio_format}")
                print(f"  Bitrate: {best_release.audio_bitrate}")
                print(f"  Lossless: {best_release.is_lossless}")
                print(f"  Seeders: {best_release.seeders}")
                return best_release

        print(f"\n[FAIL] No acceptable music release found")
        return None

    def _meets_music_requirements(self, release: TorrentRelease, profile: MediaProfile) -> bool:
        """
        Check if music release meets profile requirements
        """
        preferred_quality = getattr(profile, "music_preferred_quality", None) or []

        if not preferred_quality:
            return True

        # Map release format to quality values
        format_to_quality = {
            "FLAC": "flac",
            "MP3": "mp3_320",  # Default MP3 to 320
            "AAC": "aac",
            "OGG": "ogg",
            "ALAC": "flac",  # Treat ALAC as equivalent to FLAC
            "WAV": "flac",  # Treat WAV as lossless
        }

        # Map bitrate to quality
        bitrate_to_quality = {
            "320": "mp3_320",
            "256": "mp3_256",
            "192": "mp3_192",
            "128": "mp3_128",
            "V0": "mp3_320",  # V0 is roughly equivalent to 320
            "V2": "mp3_256",
        }

        # Determine release quality
        release_quality = None

        if release.audio_format:
            release_quality = format_to_quality.get(release.audio_format.upper())

        # Override with bitrate if available
        if release.audio_bitrate:
            bitrate_quality = bitrate_to_quality.get(release.audio_bitrate)
            if bitrate_quality:
                release_quality = bitrate_quality

        # If we can't determine quality, accept it
        if not release_quality:
            return True

        # Check if release quality is in preferred list
        return release_quality in preferred_quality

    def _select_best_music_release(
        self,
        releases: List[TorrentRelease],
        profile: MediaProfile,
        preferred_uploaders: Optional[List[str]] = None,
    ) -> Optional[TorrentRelease]:
        """
        Select best music release based on seeders and preferences
        """
        if not releases:
            return None

        # Sort by: lossless first, then seeders
        def score_release(release: TorrentRelease) -> tuple:
            lossless_score = 1 if release.is_lossless else 0
            uploader_score = 1 if preferred_uploaders and release.uploader in preferred_uploaders else 0
            return (lossless_score, uploader_score, release.seeders)

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
    ) -> Optional[str]:
        """
        Search for music with cascading quality, select best, and download
        Returns torrent hash if successful
        """
        best_release = await self.music_cascading_search(query, profile, preferred_uploaders, blocked_uploaders)

        if not best_release:
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
