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
from app.services.download_clients.qbittorrent import qbittorrent_client


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

    async def search_all_indexers(
        self,
        query: str,
        category: Optional[str] = None,
        limit_per_indexer: int = 50,
        media_type: Optional[str] = None,
    ) -> List[TorrentRelease]:
        """
        Search all enabled indexers in parallel
        Returns combined and deduplicated results
        Uses anime indexers for anime, general indexers for movies/shows
        """
        tasks = []

        # Select indexers based on media type
        if media_type == "anime":
            indexers = self.anime_indexers
        else:
            indexers = self.general_indexers

        for indexer in indexers:
            task = indexer.search(query, category, limit_per_indexer)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_releases = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Indexer error: {result}")
                continue
            all_releases.extend(result)

        # Deduplicate by info_hash
        seen_hashes = set()
        unique_releases = []

        for release in all_releases:
            if release.info_hash and release.info_hash in seen_hashes:
                continue

            if release.info_hash:
                seen_hashes.add(release.info_hash)

            unique_releases.append(release)

        return unique_releases

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
        1. Resolution (from profile.resolutions, first = highest priority)
        2. Source (from profile.sources, first = highest priority)
        3. Codec (from profile.codecs, first = highest priority)
        4. HDR (from profile.hdr_formats, first = highest priority)
        5. Uploader (from profile.uploaders, first = highest priority)

        If value is in list: allowed
        If value NOT in list: rejected
        Position in list: determines search order (index 0 = try first)

        Example: ["2160p", "1080p"] + ["BluRay", "WEB-DL"] cascades:
        2160p BluRay -> 2160p WEB-DL -> 1080p BluRay -> 1080p WEB-DL
        """
        resolution_order = self._get_quality_cascade(profile)
        source_order = profile.sources or [None]
        codec_order = profile.codecs or [None]
        hdr_order = profile.hdr_formats or [None]
        uploader_order = profile.uploaders or [None]

        print(f"Cascading search: {base_query}")
        print(f"Resolution order: {resolution_order}")
        print(f"Source order: {source_order}")
        print(f"Codec order: {codec_order}")
        print(f"HDR order: {hdr_order}")
        print(f"Uploader order: {uploader_order}")

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

                            # Search all indexers
                            releases = await self.search_all_indexers(query, category, limit_per_indexer=50, media_type=media_type)

                            if not releases:
                                continue

                            # Filter by profile requirements
                            filtered_releases = []
                            for release in releases:
                                if not media_profile_service._meets_minimum_requirements(release, profile):
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
                            )

                            if not best_release:
                                continue

                            # Found acceptable release!
                            print(f"\n✓ Selected: {best_release.title}")
                            print(f"  Resolution: {best_release.quality}")
                            print(f"  Source: {best_release.source}")
                            print(f"  Codec: {best_release.codec}")
                            print(f"  HDR: {best_release.hdr}")
                            print(f"  Uploader: {best_release.uploader}")
                            print(f"  Seeders: {best_release.seeders}")

                            return best_release

        print(f"\n✗ No acceptable release found")
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
            torrent_hash = await qbittorrent_client.add_torrent(
                torrent=torrent_source,
                save_path=save_path,
                category=category,
                tags=tags,
            )

            print(f"✓ Added to download client: {torrent_hash}")
            return torrent_hash

        except Exception as e:
            print(f"Error adding torrent to client: {e}")
            return None

    async def get_rss_updates(self) -> List[TorrentRelease]:
        """
        Get recent releases from all indexers (RSS monitoring)
        """
        tasks = []

        for indexer in self.indexers:
            task = indexer.get_rss()
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_releases = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Indexer RSS error: {result}")
                continue
            all_releases.extend(result)

        return all_releases

    def _get_quality_cascade(self, profile: MediaProfile) -> List[str]:
        """
        Build quality cascade order from profile resolutions
        Resolutions list is already ordered by preference (highest priority first)
        """
        resolutions = profile.resolutions or []

        if not resolutions:
            # Default cascade if no resolutions specified
            return ['2160p', '1080p', '720p', '480p']

        # Resolutions are already ordered by preference (first = most preferred)
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
        anime_subtitle_pref = getattr(profile, 'anime_subtitle_preference', 'softsub')
        anime_allow_hardsub = getattr(profile, 'anime_allow_hardsub', False)
        anime_prefer_dual_audio = getattr(profile, 'anime_prefer_dual_audio', False)
        anime_audio_lang = getattr(profile, 'anime_audio_language', 'ja')
        anime_subtitle_lang = getattr(profile, 'anime_subtitle_language', 'en')

        subtitle_type = raw_data.get('subtitle_type')
        audio_language = raw_data.get('audio_language')
        subtitle_language = raw_data.get('subtitle_language')

        # Filter by audio language if detected
        if audio_language and audio_language != anime_audio_lang:
            # Allow dual audio if it contains preferred language
            if not (subtitle_type == 'dual_audio' and anime_audio_lang in ['ja', 'en']):
                return False

        # Filter by subtitle language if detected
        if subtitle_language and subtitle_language != anime_subtitle_lang:
            return False

        # Filter by dual audio preference
        if anime_prefer_dual_audio and subtitle_type != 'dual_audio':
            return False

        # Filter by hardsub/softsub
        if subtitle_type == 'hardsub' and not anime_allow_hardsub:
            return False

        if anime_subtitle_pref == 'softsub' and subtitle_type == 'hardsub' and not anime_allow_hardsub:
            return False

        # Block raw releases (no subtitles)
        if subtitle_type == 'raw':
            return False

        return True


search_engine = SearchEngine()
