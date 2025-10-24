from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TorrentRelease:
    """
    Standardized torrent release information
    """

    title: str
    magnet: Optional[str] = None
    torrent_url: Optional[str] = None
    info_hash: Optional[str] = None
    size: Optional[int] = None  # Size in bytes
    size_string: Optional[str] = None
    seeders: int = 0
    leechers: int = 0
    upload_date: Optional[datetime] = None
    uploader: Optional[str] = None
    category: Optional[str] = None
    indexer: str = ""
    quality: Optional[str] = None  # Parsed quality (1080p, 720p, etc.)
    codec: Optional[str] = None  # Parsed codec (x264, x265, etc.)
    source: Optional[str] = None  # Parsed source (BluRay, WEB-DL, etc.)
    audio: Optional[str] = None  # Parsed audio codec
    audio_channels: Optional[str] = None  # Parsed audio channels (7.1, 5.1, Atmos, etc.)
    hdr: Optional[str] = None  # Parsed HDR format (Dolby Vision, HDR10+, HDR10, SDR)
    edition: Optional[str] = None  # Parsed edition (IMAX, Director's Cut, etc.)
    language: Optional[str] = None  # Parsed language code
    release_group: Optional[str] = None
    is_proper: bool = False
    is_repack: bool = False
    raw_data: Optional[Dict[str, Any]] = None


class BaseIndexer(ABC):
    """
    Base class for all indexer implementations
    Ensures consistent interface across different torrent sites
    """

    name: str = ""
    base_url: str = ""
    alternative_urls: List[str] = []
    requires_cloudflare_bypass: bool = False
    categories: Dict[str, str] = {}

    @abstractmethod
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TorrentRelease]:
        """
        Search the indexer for torrents
        """
        pass

    @abstractmethod
    async def get_rss(self, category: Optional[str] = None) -> List[TorrentRelease]:
        """
        Get recent uploads from RSS feed
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the indexer is reachable
        """
        pass

    def parse_quality(self, title: str) -> Dict[str, Optional[str]]:
        """
        Parse quality information from release title
        Extracts: resolution, codec, source, audio codec, audio channels, HDR, edition, language
        """
        import re

        title_upper = title.upper()

        # Resolution (4320p, 2160p, 1080p, 720p, 576p, 480p, 360p, 240p)
        quality = None
        if any(x in title_upper for x in ["8K", "4320P"]):
            quality = "4320p"
        elif any(x in title_upper for x in ["4K", "2160P", "UHD"]):
            quality = "2160p"
        elif "1080P" in title_upper:
            quality = "1080p"
        elif "720P" in title_upper:
            quality = "720p"
        elif "576P" in title_upper:
            quality = "576p"
        elif "480P" in title_upper:
            quality = "480p"
        elif "360P" in title_upper:
            quality = "360p"
        elif "240P" in title_upper:
            quality = "240p"

        # Codec (AV1, HEVC, x265, H265, x264, H264, XVID)
        codec = None
        if "AV1" in title_upper:
            codec = "AV1"
        elif "HEVC" in title_upper:
            codec = "HEVC"
        elif "X265" in title_upper:
            codec = "x265"
        elif "H.265" in title_upper or "H265" in title_upper:
            codec = "H265"
        elif "H.264" in title_upper or "H264" in title_upper:
            codec = "H264"
        elif "X264" in title_upper:
            codec = "x264"
        elif "XVID" in title_upper or "DIVX" in title_upper:
            codec = "XVID"
        elif "VP9" in title_upper:
            codec = "VP9"

        # Source (REMUX, BLURAY, WEB-DL, WEBRIP, DVD, HDTV, SDTV, DVDSCR, SCREENER, TELESYNC, CAM)
        # Check most specific patterns first to avoid false matches
        source = None
        if "REMUX" in title_upper:
            source = "REMUX"
        elif "BLURAY" in title_upper or "BLU-RAY" in title_upper or "BDRIP" in title_upper or "BRRip" in title_upper:
            source = "BLURAY"
        elif "WEB-DL" in title_upper or "WEBDL" in title_upper or "WEB.DL" in title_upper:
            source = "WEB-DL"
        elif "WEBRIP" in title_upper or "WEB-RIP" in title_upper or "WEB.RIP" in title_upper:
            source = "WEBRIP"
        elif "DVDSCR" in title_upper or "DVD-SCR" in title_upper or "DVDSCREENER" in title_upper:
            source = "DVDSCR"
        elif "DVDRIP" in title_upper or "DVD-RIP" in title_upper:
            source = "DVD"
        elif "SCREENER" in title_upper or ("SCR" in title_upper and "DVD" not in title_upper):
            source = "SCREENER"
        elif "TELESYNC" in title_upper or ("TS" in title_upper and "ATMOS" not in title_upper):
            source = "TELESYNC"
        elif "HDTV" in title_upper:
            source = "HDTV"
        elif "SDTV" in title_upper:
            source = "SDTV"
        elif "CAM" in title_upper or "CAMRIP" in title_upper:
            source = "CAM"
        elif "DVD" in title_upper:
            source = "DVD"

        # Audio Codec (FLAC, TrueHD, Dolby Atmos, DTS-HD MA, DTS, AC3, AAC, MP3)
        # Check most specific patterns first
        audio = None
        if "FLAC" in title_upper:
            audio = "FLAC"
        elif "TRUEHD" in title_upper or "TRUE-HD" in title_upper or "TRUE HD" in title_upper:
            audio = "TrueHD"
        elif "ATMOS" in title_upper or "DOLBY ATMOS" in title_upper:
            audio = "Dolby Atmos"
        elif "DTS-HD.MA" in title_upper or "DTS.HD.MA" in title_upper or "DTSHD.MA" in title_upper or "DTS-HD MA" in title_upper or "DTSHDMA" in title_upper:
            audio = "DTS-HD MA"
        elif "DTS" in title_upper:
            audio = "DTS"
        elif "AC3" in title_upper or "DD5.1" in title_upper or "DD+" in title_upper or "DD5 1" in title_upper:
            audio = "AC3"
        elif "AAC" in title_upper:
            audio = "AAC"
        elif "MP3" in title_upper:
            audio = "MP3"

        # Audio Channels (Atmos, 7.1, 5.1, 2.0)
        audio_channels = None
        if "ATMOS" in title_upper or "DOLBY ATMOS" in title_upper:
            audio_channels = "Atmos"
        elif "7.1" in title or "7 1" in title_upper:
            audio_channels = "7.1"
        elif "5.1" in title or "5 1" in title_upper:
            audio_channels = "5.1"
        elif "2.0" in title or "STEREO" in title_upper:
            audio_channels = "2.0"

        # HDR Format (Dolby Vision, HDR10+, HDR10, SDR)
        hdr = None
        if "DOLBY VISION" in title_upper or "DOLBYVISION" in title_upper or "DV" in title_upper or "DOVI" in title_upper:
            hdr = "Dolby Vision"
        elif "HDR10+" in title_upper or "HDR10PLUS" in title_upper:
            hdr = "HDR10+"
        elif "HDR10" in title_upper or "HDR" in title_upper:
            hdr = "HDR10"
        elif "SDR" in title_upper:
            hdr = "SDR"

        # Edition (IMAX, Remastered, Director's Cut, Unrated, Extended, Theatrical)
        edition = None
        if "IMAX" in title_upper:
            edition = "IMAX"
        elif "REMASTERED" in title_upper:
            edition = "Remastered"
        elif "DIRECTOR" in title_upper and "CUT" in title_upper:
            edition = "Director's Cut"
        elif "UNRATED" in title_upper:
            edition = "Unrated"
        elif "EXTENDED" in title_upper:
            edition = "Extended"
        elif "THEATRICAL" in title_upper:
            edition = "Theatrical"

        # Language (default to English if not specified)
        language = None
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
                language = code
                break

        # Check for language codes in brackets
        if not language:
            lang_match = re.search(r'\[([A-Z]{2})\]', title_upper)
            if lang_match:
                language = lang_match.group(1).lower()

        # Default to English
        if not language:
            language = 'en'

        # Release group (usually at the end in brackets or after dash)
        release_group = None
        group_match = re.search(r"-([A-Za-z0-9]+)$", title) or re.search(r"\[([A-Za-z0-9]+)\]$", title)
        if group_match:
            release_group = group_match.group(1)

        return {
            "quality": quality,
            "codec": codec,
            "source": source,
            "audio": audio,
            "audio_channels": audio_channels,
            "hdr": hdr,
            "edition": edition,
            "language": language,
            "release_group": release_group,
        }

    def parse_size(self, size_str: str) -> Optional[int]:
        """
        Parse size string to bytes
        Examples: "1.5 GB", "700 MB", "4.2 GiB"
        """
        import re

        if not size_str:
            return None

        match = re.search(r"([\d.]+)\s*([KMGT])i?B", size_str, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2).upper()

        multipliers = {
            "K": 1024,
            "M": 1024 ** 2,
            "G": 1024 ** 3,
            "T": 1024 ** 4,
        }

        return int(value * multipliers.get(unit, 1))
