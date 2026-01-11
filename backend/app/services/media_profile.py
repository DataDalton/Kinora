from typing import List, Optional
from dataclasses import dataclass
import re
import math

from app.services.indexers.base import TorrentRelease
from app.services.quality_definitions import QualityHierarchy


@dataclass
class MediaProfile:
    """
    Media profile for automated release selection

    All list fields are ordered by preference (highest priority first):
    - If value is in the list: it is allowed
    - Position in list: determines preference (index 0 = most preferred)
    - If value is NOT in the list: it is rejected

    Season pack preference options:
    - "prefer": Try season packs first, fall back to individual episodes
    - "only": Only download season packs, reject individual episodes
    - "avoid": Only download individual episodes, reject season packs
    """

    id: int
    name: str
    # Per-media-type quality: Movies
    movie_resolutions: Optional[List[str]] = None
    movie_codecs: Optional[List[str]] = None
    movie_sources: Optional[List[str]] = None
    movie_audio_codecs: Optional[List[str]] = None
    movie_audio_channels: Optional[List[str]] = None
    movie_hdr_formats: Optional[List[str]] = None
    movie_editions: Optional[List[str]] = None
    movie_min_size: Optional[int] = None
    movie_max_size: Optional[int] = None
    # Per-media-type quality: TV Shows
    show_resolutions: Optional[List[str]] = None
    show_codecs: Optional[List[str]] = None
    show_sources: Optional[List[str]] = None
    show_audio_codecs: Optional[List[str]] = None
    show_audio_channels: Optional[List[str]] = None
    show_hdr_formats: Optional[List[str]] = None
    show_min_size: Optional[int] = None
    show_max_size: Optional[int] = None
    # Per-media-type quality: Anime
    anime_resolutions: Optional[List[str]] = None
    anime_codecs: Optional[List[str]] = None
    anime_sources: Optional[List[str]] = None
    anime_audio_codecs: Optional[List[str]] = None
    anime_audio_channels: Optional[List[str]] = None
    anime_hdr_formats: Optional[List[str]] = None
    anime_min_size: Optional[int] = None
    anime_max_size: Optional[int] = None
    # Per-media-type indexers
    movie_indexers: Optional[List[str]] = None
    show_indexers: Optional[List[str]] = None
    anime_indexers: Optional[List[str]] = None
    music_indexers: Optional[List[str]] = None
    # Common settings
    languages: Optional[List[str]] = None
    subtitle_languages: Optional[List[str]] = None
    upgrade_allowed: bool = True
    indexers: Optional[List[str]] = None
    uploaders: Optional[List[str]] = None
    release_groups: Optional[List[str]] = None
    regex_filters: Optional[List[str]] = None
    seeder_weight: int = 34
    size_weight: int = 33
    recency_weight: int = 33
    search_sort_preference: str = "weighted"
    season_pack_preference: str = "prefer"
    search_timeout: int = 30
    max_retries: int = 3
    max_results: int = 100
    # Torrent validation settings
    validation_enabled: bool = True
    validation_mode: str = "allowlist"
    forbidden_extensions: Optional[List[str]] = None
    validation_failure_action: str = "pause_notify"
    movie_allowed_extensions: Optional[List[str]] = None
    show_allowed_extensions: Optional[List[str]] = None
    anime_allowed_extensions: Optional[List[str]] = None
    music_allowed_extensions: Optional[List[str]] = None

    def get_allowed_extensions_for_type(self, media_type: str) -> List[str]:
        """
        Get allowed extensions for a specific media type.
        Only used when validation_mode is 'allowlist'.

        Args:
            media_type: One of 'movie', 'show', 'anime', 'album'

        Returns:
            List of allowed file extensions (with leading dot)
        """
        # Map media type to attribute name
        type_map = {
            'movie': 'movie_allowed_extensions',
            'show': 'show_allowed_extensions',
            'anime': 'anime_allowed_extensions',
            'album': 'music_allowed_extensions',
            'music': 'music_allowed_extensions',
        }

        attr_name = type_map.get(media_type)
        if attr_name:
            type_specific = getattr(self, attr_name, None)
            if type_specific:
                return type_specific

        # Default extensions by media type (only used if type-specific not configured)
        defaults = {
            'movie': ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
            'show': ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
            'anime': ['.mkv', '.mp4', '.avi', '.m4v'],
            'album': ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'],
            'music': ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'],
        }
        return defaults.get(media_type, [])

    def get_resolutions_for_type(self, media_type: str) -> List[str]:
        """Get resolutions for specific media type."""
        type_map = {
            'movie': 'movie_resolutions',
            'show': 'show_resolutions',
            'anime': 'anime_resolutions',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_codecs_for_type(self, media_type: str) -> List[str]:
        """Get codecs for specific media type."""
        type_map = {
            'movie': 'movie_codecs',
            'show': 'show_codecs',
            'anime': 'anime_codecs',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_sources_for_type(self, media_type: str) -> List[str]:
        """Get sources for specific media type."""
        type_map = {
            'movie': 'movie_sources',
            'show': 'show_sources',
            'anime': 'anime_sources',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_audio_codecs_for_type(self, media_type: str) -> List[str]:
        """Get audio codecs for specific media type."""
        type_map = {
            'movie': 'movie_audio_codecs',
            'show': 'show_audio_codecs',
            'anime': 'anime_audio_codecs',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_audio_channels_for_type(self, media_type: str) -> List[str]:
        """Get audio channels for specific media type."""
        type_map = {
            'movie': 'movie_audio_channels',
            'show': 'show_audio_channels',
            'anime': 'anime_audio_channels',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_hdr_formats_for_type(self, media_type: str) -> List[str]:
        """Get HDR formats for specific media type."""
        type_map = {
            'movie': 'movie_hdr_formats',
            'show': 'show_hdr_formats',
            'anime': 'anime_hdr_formats',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None) or []
        return []

    def get_editions_for_type(self, media_type: str) -> List[str]:
        """Get editions for specific media type (movies only)."""
        if media_type == 'movie':
            return self.movie_editions or []
        return []

    def get_indexers_for_type(self, media_type: str) -> Optional[List[str]]:
        """Get indexers for specific media type."""
        type_map = {
            'movie': 'movie_indexers',
            'show': 'show_indexers',
            'anime': 'anime_indexers',
            'album': 'music_indexers',
            'music': 'music_indexers',
        }
        attr = type_map.get(media_type)
        if attr:
            return getattr(self, attr, None)
        return None

    def get_size_limits_for_type(self, media_type: str) -> tuple[Optional[int], Optional[int]]:
        """Get min/max size limits for specific media type."""
        type_map = {
            'movie': ('movie_min_size', 'movie_max_size'),
            'show': ('show_min_size', 'show_max_size'),
            'anime': ('anime_min_size', 'anime_max_size'),
        }
        attrs = type_map.get(media_type)
        if attrs:
            min_size = getattr(self, attrs[0], None)
            max_size = getattr(self, attrs[1], None)
            return (min_size, max_size)
        return (None, None)


class MediaProfileService:
    """
    Service for media profile management and release scoring
    Uses comprehensive quality definitions for detailed scoring
    """

    # Use QualityHierarchy from quality_definitions for scoring
    QUALITY_HIERARCHY = QualityHierarchy.RESOLUTION_SCORES
    CODEC_HIERARCHY = QualityHierarchy.CODEC_SCORES
    SOURCE_HIERARCHY = QualityHierarchy.SOURCE_SCORES
    AUDIO_HIERARCHY = QualityHierarchy.AUDIO_CODEC_SCORES
    HDR_HIERARCHY = QualityHierarchy.HDR_SCORES
    EDITION_HIERARCHY = QualityHierarchy.EDITION_SCORES

    def score_release(
        self,
        release: TorrentRelease,
        profile: MediaProfile,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
    ) -> float:
        """
        Score a release based on quality profile.
        Uses per-media-type settings when media_type is provided.
        Returns float score (higher is better)
        Returns -1 if release should be rejected
        """
        score = 0.0

        # Check if release meets minimum requirements
        if not self._meets_minimum_requirements(release, profile, media_type):
            return -1.0

        # Blocked uploader check
        if blocked_uploaders and release.uploader in blocked_uploaders:
            return -1.0

        # Quality score (0-100 points)
        quality_score = self._score_quality(release.quality, profile, media_type)
        if quality_score < 0:
            return -1.0
        score += quality_score

        # Codec score (0-30 points)
        codec_score = self._score_codec(release.codec, profile, media_type)
        score += codec_score

        # Source score (0-30 points)
        source_score = self._score_source(release.source, profile, media_type)
        score += source_score

        # Audio score (0-20 points)
        audio_score = self._score_audio(release.audio, profile, media_type)
        score += audio_score

        # Resolution score (0-15 points)
        resolution_score = self._score_resolution(release, profile, media_type)
        score += resolution_score

        # Audio channels score (0-10 points)
        channels_score = self._score_audio_channels(release, profile, media_type)
        score += channels_score

        # HDR score (0-20 points)
        hdr_score = self._score_hdr(release, profile, media_type)
        score += hdr_score

        # Edition score (0-10 points)
        edition_score = self._score_edition(release, profile, media_type)
        score += edition_score

        # Weighted scoring based on profile preferences
        if profile.search_sort_preference == "weighted":
            # Seeders weighted (configurable weight)
            if release.seeders > 0:
                seeders_score = min(50, math.log10(release.seeders + 1) * 15)
                score += seeders_score * (profile.seeder_weight / 100.0)

            # Size weighted (configurable weight)
            size_penalty = self._score_size(release.size, profile, media_type)
            score += size_penalty * (profile.size_weight / 100.0)

            # Recency weighted (configurable weight)
            # TODO: Add timestamp to TorrentRelease and score based on age
        elif profile.search_sort_preference == "seeders":
            # Pure seeder sorting
            if release.seeders > 0:
                score += min(100, math.log10(release.seeders + 1) * 30)
        elif profile.search_sort_preference == "size":
            # Prefer releases closer to expected size
            size_score = self._score_size(release.size, profile, media_type)
            score += size_score * 2
        elif profile.search_sort_preference == "date":
            # Recency preference
            # TODO: Implement when timestamp added to TorrentRelease
            pass

        # Preferred uploader bonus (50 points)
        if preferred_uploaders and release.uploader in preferred_uploaders:
            score += 50

        # Release group bonus (30 points) - if in profile.release_groups
        if profile.release_groups and release.release_group:
            if any(group.lower() in release.release_group.lower() for group in profile.release_groups):
                # Position in list determines bonus (earlier = better)
                try:
                    position = next(i for i, group in enumerate(profile.release_groups)
                                  if group.lower() in release.release_group.lower())
                    position_bonus = max(0, 30 - (position * 5))
                    score += position_bonus
                except StopIteration:
                    pass

        # PROPER/REPACK bonus (20 points)
        if release.is_proper or release.is_repack:
            score += 20

        # Season pack bonus/penalty based on preference
        is_season_pack = self._is_season_pack(release.title)
        if profile.season_pack_preference == "prefer" and is_season_pack:
            score += 100  # Strong preference for season packs
        elif profile.season_pack_preference == "only" and not is_season_pack:
            return -1.0  # Reject individual episodes
        elif profile.season_pack_preference == "avoid" and is_season_pack:
            return -1.0  # Reject season packs

        return score

    def _meets_minimum_requirements(
        self, release: TorrentRelease, profile: MediaProfile, media_type: Optional[str] = None
    ) -> bool:
        """
        Check if release meets minimum requirements.
        Requires media_type to use per-media-type settings.
        Only values in the profile lists are allowed.
        """
        # Get per-type settings (no fallback to global)
        resolutions = profile.get_resolutions_for_type(media_type) if media_type else []
        codecs = profile.get_codecs_for_type(media_type) if media_type else []
        sources = profile.get_sources_for_type(media_type) if media_type else []
        audio_codecs = profile.get_audio_codecs_for_type(media_type) if media_type else []
        audio_channels = profile.get_audio_channels_for_type(media_type) if media_type else []
        hdr_formats = profile.get_hdr_formats_for_type(media_type) if media_type else []
        editions = profile.get_editions_for_type(media_type) if media_type else []
        min_size, max_size = profile.get_size_limits_for_type(media_type) if media_type else (None, None)

        # Resolution must be in list (if specified)
        if resolutions:
            resolution = release.quality or self._extract_resolution(release.title)
            if resolution and resolution not in resolutions:
                return False

        # Codec must be in list (if specified)
        if codecs:
            codec = release.codec or self._extract_codec(release.title)
            if codec and codec not in codecs:
                return False

        # Source must be in list (if specified)
        if sources:
            source = release.source or self._extract_source(release.title)
            if source and source not in sources:
                return False

        # Audio codec must be in list (if specified)
        if audio_codecs:
            audio = release.audio or self._extract_audio(release.title)
            if audio and audio not in audio_codecs:
                return False

        # Audio channels must be in list (if specified)
        if audio_channels:
            channels = release.audio_channels or self._extract_audio_channels(release.title)
            if channels and channels not in audio_channels:
                return False

        # HDR format must be in list (if specified)
        if hdr_formats:
            hdr = release.hdr or self._extract_hdr(release.title)
            if hdr and hdr not in hdr_formats:
                return False

        # Edition must be in list (if specified)
        if editions:
            edition = release.edition or self._extract_edition(release.title)
            if edition and edition not in editions:
                return False

        # Language must be in list (if specified)
        if profile.languages:
            language = release.language or self._extract_language(release.title)
            if language and language not in profile.languages:
                return False

        # Size constraints
        if min_size and release.size and release.size < min_size:
            return False

        if max_size and release.size and release.size > max_size:
            return False

        # Minimum seeders (hardcoded for now, can be made configurable)
        if release.seeders < 1:
            return False

        # Uploader must be in list (if specified)
        if profile.uploaders:
            if not any(uploader.lower() in release.uploader.lower() for uploader in profile.uploaders):
                return False

        # Release group must be in list (if specified)
        if profile.release_groups and release.release_group:
            if not any(group.lower() in release.release_group.lower() for group in profile.release_groups):
                return False

        # Regex filters (must match all patterns)
        if profile.regex_filters:
            if not all(re.search(pattern, release.title, re.IGNORECASE) for pattern in profile.regex_filters):
                return False

        return True

    def _score_quality(
        self, quality: Optional[str], profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score quality (resolution) based on position in list
        Earlier in list = higher score
        """
        resolutions = profile.get_resolutions_for_type(media_type) if media_type else []
        if not quality or not resolutions:
            return 0.0

        if quality not in resolutions:
            return -1.0

        # Base score from hierarchy
        base_score = self.QUALITY_HIERARCHY.get(quality, 0) * 25

        # Bonus based on position in list (earlier = better)
        try:
            position = resolutions.index(quality)
            position_bonus = max(0, 25 - (position * 5))  # First item gets 25, decreases by 5 per position
            base_score += position_bonus
        except ValueError:
            pass

        return base_score

    def _score_codec(
        self, codec: Optional[str], profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score codec based on position in list
        Earlier in list = higher score
        """
        codecs = profile.get_codecs_for_type(media_type) if media_type else []
        if not codec or not codecs:
            return 0.0

        if codec not in codecs:
            return 0.0

        base_score = self.CODEC_HIERARCHY.get(codec, 0) * 10

        # Bonus based on position in list
        try:
            position = codecs.index(codec)
            position_bonus = max(0, 15 - (position * 3))
            base_score += position_bonus
        except ValueError:
            pass

        return base_score

    def _score_source(
        self, source: Optional[str], profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score source based on position in list
        Earlier in list = higher score
        """
        sources = profile.get_sources_for_type(media_type) if media_type else []
        if not source or not sources:
            return 0.0

        if source not in sources:
            return 0.0

        base_score = self.SOURCE_HIERARCHY.get(source, 0) * 5

        # Bonus based on position in list
        try:
            position = sources.index(source)
            position_bonus = max(0, 15 - (position * 3))
            base_score += position_bonus
        except ValueError:
            pass

        return base_score

    def _score_audio(
        self, audio: Optional[str], profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score audio codec based on position in list
        Earlier in list = higher score
        """
        audio_codecs = profile.get_audio_codecs_for_type(media_type) if media_type else []
        if not audio or not audio_codecs:
            return 0.0

        if audio not in audio_codecs:
            return 0.0

        # Use comprehensive audio hierarchy
        base_score = self.AUDIO_HIERARCHY.get(audio, 0) * 0.2

        # Bonus based on position in list
        try:
            position = audio_codecs.index(audio)
            position_bonus = max(0, 20 - (position * 4))
            base_score += position_bonus
        except ValueError:
            pass

        return base_score

    def _score_hdr(
        self, release: TorrentRelease, profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score HDR format based on position in list
        Earlier in list = higher score
        """
        hdr_formats = profile.get_hdr_formats_for_type(media_type) if media_type else []
        if not hdr_formats:
            return 0.0

        hdr_detected = release.hdr or self._extract_hdr(release.title)
        if not hdr_detected:
            return 0.0

        if hdr_detected not in hdr_formats:
            return 0.0

        # Base score from hierarchy
        score = self.HDR_HIERARCHY.get(hdr_detected, 0) * 0.1

        # Bonus based on position in list
        try:
            position = hdr_formats.index(hdr_detected)
            position_bonus = max(0, 20 - (position * 5))
            score += position_bonus
        except ValueError:
            pass

        return score

    def _score_edition(
        self, release: TorrentRelease, profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score edition type based on position in list
        Earlier in list = higher score
        """
        editions = profile.get_editions_for_type(media_type) if media_type else []
        if not editions:
            return 0.0

        edition_detected = release.edition or self._extract_edition(release.title)
        if not edition_detected:
            return 0.0

        if edition_detected not in editions:
            return 0.0

        # Base score from hierarchy
        score = self.EDITION_HIERARCHY.get(edition_detected, 0) * 0.1

        # Bonus based on position in list
        try:
            position = editions.index(edition_detected)
            position_bonus = max(0, 10 - (position * 2))
            score += position_bonus
        except ValueError:
            pass

        return score

    def _score_size(
        self, size: Optional[int], profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """Penalty for size outside optimal range"""
        if not size:
            return 0.0

        min_size, max_size = profile.get_size_limits_for_type(media_type) if media_type else (None, None)
        penalty = 0.0

        # If size is way outside range, apply penalty
        if min_size and size < min_size * 0.8:
            penalty -= 20

        if max_size and size > max_size * 1.2:
            penalty -= 20

        return penalty

    def _is_season_pack(self, title: str) -> bool:
        """
        Detect if release is a season pack
        Common patterns: S01, Season 1, Complete Season, etc.
        """
        title_upper = title.upper()

        # Season pack indicators
        season_pack_patterns = [
            r'S\d{1,2}\s*COMPLETE',
            r'SEASON\s*\d{1,2}\s*COMPLETE',
            r'COMPLETE\s*SEASON',
            r'SEASON\s*\d{1,2}(?!\s*E\d{1,2})',  # S01 without E01
            r'S\d{1,2}(?!\s*E\d{1,2})',  # S01 without episode number
        ]

        import re
        for pattern in season_pack_patterns:
            if re.search(pattern, title_upper):
                # Make sure it's not a single episode (S01E01)
                if not re.search(r'S\d{1,2}E\d{1,2}', title_upper):
                    return True

        return False

    def _extract_resolution(self, title: str) -> Optional[str]:
        """Extract resolution from title"""
        title_upper = title.upper()
        resolutions = ['4320P', '2160P', '1080P', '720P', '576P', '480P', '360P', '240P']
        for res in resolutions:
            if res in title_upper:
                return res.lower()
        return None

    def _extract_codec(self, title: str) -> Optional[str]:
        """Extract codec from title"""
        title_upper = title.upper()

        if "AV1" in title_upper:
            return "AV1"
        elif "HEVC" in title_upper:
            return "HEVC"
        elif "X265" in title_upper:
            return "x265"
        elif "H.265" in title_upper or "H265" in title_upper:
            return "H265"
        elif "X264" in title_upper:
            return "x264"
        elif "H.264" in title_upper or "H264" in title_upper:
            return "H264"
        elif "XVID" in title_upper:
            return "XVID"

        return None

    def _extract_source(self, title: str) -> Optional[str]:
        """Extract source from title"""
        title_upper = title.upper()

        if "REMUX" in title_upper:
            return "REMUX"
        elif "DVDSCR" in title_upper or "DVD-SCR" in title_upper:
            return "DVDSCR"
        elif "SCREENER" in title_upper:
            return "SCREENER"
        elif "BLURAY" in title_upper or "BLU-RAY" in title_upper or "BDRIP" in title_upper:
            return "BluRay"
        elif "WEB-DL" in title_upper or "WEBDL" in title_upper:
            return "WEB-DL"
        elif "WEBRIP" in title_upper or "WEB-RIP" in title_upper:
            return "WEBRip"
        elif "DVD" in title_upper:
            return "DVD"
        elif "HDTV" in title_upper:
            return "HDTV"
        elif "SDTV" in title_upper:
            return "SDTV"
        elif "TELESYNC" in title_upper or "TS" in title_upper:
            return "TELESYNC"
        elif "CAM" in title_upper:
            return "CAM"

        return None

    def _extract_audio(self, title: str) -> Optional[str]:
        """Extract audio codec from title"""
        title_upper = title.upper()

        if "DTS-HD.MA" in title_upper or "DTS.HD.MA" in title_upper or "DTSHD.MA" in title_upper or "DTS-HD MA" in title_upper:
            return "DTS-HD MA"
        elif "DTS" in title_upper:
            return "DTS"
        elif "FLAC" in title_upper:
            return "FLAC"
        elif "TRUEHD" in title_upper or "TRUE-HD" in title_upper:
            return "TrueHD"
        elif "ATMOS" in title_upper or "DOLBY ATMOS" in title_upper:
            return "Dolby Atmos"
        elif "AC3" in title_upper or "DD" in title_upper:
            return "AC3"
        elif "AAC" in title_upper:
            return "AAC"
        elif "MP3" in title_upper:
            return "MP3"

        return None

    def _extract_audio_channels(self, title: str) -> Optional[str]:
        """Extract audio channels from title"""
        title_upper = title.upper()

        # Check for Atmos first (most specific)
        if 'ATMOS' in title_upper or 'DOLBY ATMOS' in title_upper:
            return 'Atmos'

        # Check for channel configurations
        if '7.1' in title_upper or '7 1' in title_upper:
            return '7.1'
        if '5.1' in title_upper or '5 1' in title_upper:
            return '5.1'
        if '2.0' in title_upper or 'STEREO' in title_upper:
            return '2.0'
        if 'MONO' in title_upper or '1.0' in title_upper:
            return 'Mono'

        return None

    def _extract_hdr(self, title: str) -> Optional[str]:
        """Extract HDR format from title"""
        title_upper = title.upper()

        # Check for Dolby Vision with HDR fallback (DV HDR / hybrid) first
        # These releases have HDR10 base layer for non-DV devices
        hasDv = 'DOLBY VISION' in title_upper or 'DV' in title_upper or 'DOVI' in title_upper
        hasHdr = 'HDR10' in title_upper or 'HDR' in title_upper

        if hasDv and hasHdr:
            return 'DV HDR'

        # Pure Dolby Vision (no HDR fallback)
        if hasDv:
            return 'Dolby Vision'

        if 'HDR10+' in title_upper or 'HDR10PLUS' in title_upper:
            return 'HDR10+'
        if hasHdr:
            return 'HDR10'
        if 'SDR' in title_upper:
            return 'SDR'

        return None

    def _extract_edition(self, title: str) -> Optional[str]:
        """Extract edition from title"""
        title_upper = title.upper()

        editions = {
            'IMAX': 'IMAX',
            'REMASTERED': 'Remastered',
            "DIRECTOR'S CUT": "Director's Cut",
            'DIRECTORS CUT': "Director's Cut",
            'UNRATED': 'Unrated',
            'EXTENDED': 'Extended',
            'THEATRICAL': 'Theatrical',
            'PROPER': 'PROPER',
            'REPACK': 'REPACK'
        }

        for key, value in editions.items():
            if key in title_upper:
                return value

        return None

    def _extract_language(self, title: str) -> Optional[str]:
        """Extract language from title"""
        title_upper = title.upper()

        # Common language codes in releases
        language_patterns = {
            'MULTI': 'multi',
            'ENGLISH': 'en',
            'SPANISH': 'es',
            'FRENCH': 'fr',
            'GERMAN': 'de',
            'ITALIAN': 'it',
            'JAPANESE': 'ja',
            'KOREAN': 'ko',
            'CHINESE': 'zh',
            'PORTUGUESE': 'pt',
            'RUSSIAN': 'ru',
            'HINDI': 'hi',
            'ARABIC': 'ar',
            'DUTCH': 'nl',
            'POLISH': 'pl',
            'TURKISH': 'tr',
        }

        for key, code in language_patterns.items():
            if key in title_upper:
                return code

        # Check for language codes in brackets or tags
        lang_match = re.search(r'\[([A-Z]{2})\]', title_upper)
        if lang_match:
            return lang_match.group(1).lower()

        # Default to English if no language detected
        return 'en'

    def _score_resolution(
        self, release: TorrentRelease, profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score resolution based on position in list
        Earlier in list = higher score
        """
        resolutions = profile.get_resolutions_for_type(media_type) if media_type else []
        if not resolutions:
            return 0.0

        resolution = release.quality or self._extract_resolution(release.title)
        if not resolution:
            return 0.0

        if resolution not in resolutions:
            return 0.0

        # Bonus based on position in list
        try:
            position = resolutions.index(resolution)
            score = max(0, 15 - (position * 3))
            return score
        except ValueError:
            return 0.0

    def _score_audio_channels(
        self, release: TorrentRelease, profile: MediaProfile, media_type: Optional[str] = None
    ) -> float:
        """
        Score audio channels based on position in list
        Earlier in list = higher score
        """
        audio_channels = profile.get_audio_channels_for_type(media_type) if media_type else []
        if not audio_channels:
            return 0.0

        channels = release.audio_channels or self._extract_audio_channels(release.title)
        if not channels:
            return 0.0

        if channels not in audio_channels:
            return 0.0

        # Bonus based on position in list
        try:
            position = audio_channels.index(channels)
            score = max(0, 10 - (position * 2))
            return score
        except ValueError:
            return 0.0

    def select_best_release(
        self,
        releases: List[TorrentRelease],
        profile: MediaProfile,
        preferred_uploaders: Optional[List[str]] = None,
        blocked_uploaders: Optional[List[str]] = None,
        media_type: Optional[str] = None,
    ) -> Optional[TorrentRelease]:
        """
        Select the best release from a list based on quality profile.
        Uses per-media-type settings when media_type is provided.
        """
        if not releases:
            return None

        scored_releases = []

        for release in releases:
            score = self.score_release(
                release, profile, preferred_uploaders, blocked_uploaders, media_type
            )
            if score >= 0:  # Only include valid releases
                scored_releases.append((release, score))

        if not scored_releases:
            return None

        # Sort by score (highest first)
        scored_releases.sort(key=lambda x: x[1], reverse=True)

        return scored_releases[0][0]

    def needs_upgrade(
        self,
        current_quality: str,
        new_quality: str,
        profile: MediaProfile,
        media_type: Optional[str] = None,
    ) -> bool:
        """
        Check if new release is an upgrade over current
        """
        if not profile.upgrade_allowed:
            return False

        current_rank = self.QUALITY_HIERARCHY.get(current_quality, 0)
        new_rank = self.QUALITY_HIERARCHY.get(new_quality, 0)

        # New quality must be higher
        if new_rank <= current_rank:
            return False

        # Check if new quality is in the allowed resolutions list
        resolutions = profile.get_resolutions_for_type(media_type) if media_type else []
        if resolutions and new_quality not in resolutions:
            return False

        return True


media_profile_service = MediaProfileService()
