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
    detail_url: Optional[str] = None  # indexer detail/page URL for the release
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
    # Music-specific fields
    audio_format: Optional[str] = None  # FLAC, MP3, AAC, OGG, etc.
    audio_bitrate: Optional[str] = None  # 320, 256, 128, V0, etc.
    bit_depth: Optional[int] = None  # Lossless bit depth parsed from title (16, 24)
    sample_rate: Optional[int] = None  # Lossless sample rate in Hz parsed from title (44100, 96000)
    quality_tier: Optional[str] = None  # Best-effort music quality tier from the title
    is_lossless: bool = False
    is_discography: bool = False
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for caching. raw_data is dropped."""
        from dataclasses import asdict

        data = asdict(self)
        data.pop("raw_data", None)
        if self.upload_date is not None:
            data["upload_date"] = self.upload_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TorrentRelease":
        """Rebuild a TorrentRelease from a cached dict."""
        data = dict(data)
        data.pop("raw_data", None)
        upload_date = data.get("upload_date")
        if isinstance(upload_date, str):
            try:
                data["upload_date"] = datetime.fromisoformat(upload_date)
            except ValueError:
                data["upload_date"] = None
        return cls(**data)


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

    async def ensure_download_source(self, release: TorrentRelease) -> TorrentRelease:
        """
        Resolve the magnet or torrent source for a chosen release when it was not
        captured during search. Indexers whose listings already include the source
        (YTS, Nyaa) keep the default no-op. Indexers that require a detail-page fetch
        (1337x) override this so the fetch happens once, at download time, rather than
        for every search result.
        """
        return release

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
        elif (
            "DTS-HD.MA" in title_upper
            or "DTS.HD.MA" in title_upper
            or "DTSHD.MA" in title_upper
            or "DTS-HD MA" in title_upper
            or "DTSHDMA" in title_upper
        ):
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
        if (
            "DOLBY VISION" in title_upper
            or "DOLBYVISION" in title_upper
            or "DV" in title_upper
            or "DOVI" in title_upper
        ):
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
            "MULTI": "multi",
            "ENGLISH": "en",
            "SPANISH": "es",
            "FRENCH": "fr",
            "GERMAN": "de",
            "ITALIAN": "it",
            "JAPANESE": "ja",
            "KOREAN": "ko",
            "CHINESE": "zh",
            "PORTUGUESE": "pt",
            "RUSSIAN": "ru",
            "HINDI": "hi",
            "ARABIC": "ar",
            "DUTCH": "nl",
            "POLISH": "pl",
            "TURKISH": "tr",
        }
        for key, code in language_patterns.items():
            if key in title_upper:
                language = code
                break

        # Check for language codes in brackets
        if not language:
            lang_match = re.search(r"\[([A-Z]{2})\]", title_upper)
            if lang_match:
                language = lang_match.group(1).lower()

        # Default to English
        if not language:
            language = "en"

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
            "M": 1024**2,
            "G": 1024**3,
            "T": 1024**4,
        }

        return int(value * multipliers.get(unit, 1))

    def parse_music_quality(self, title: str) -> Dict[str, Any]:
        """
        Parse music-specific quality information from release title
        Extracts: audio format, bitrate, lossless flag, discography flag, artist, album, year
        """
        import re

        title_upper = title.upper()

        # Audio Format. FLAC and ALAC are checked before DSD/SACD so a PCM rip of an
        # SACD titled "... SACD ... FLAC" is read as FLAC, while a pure "[DSD 64]" or
        # "SACD" release with no PCM format falls through to DSD.
        audio_format = None
        is_lossless = False

        if "FLAC" in title_upper:
            audio_format = "FLAC"
            is_lossless = True
        elif "ALAC" in title_upper:
            audio_format = "ALAC"
            is_lossless = True
        elif "WAV" in title_upper:
            audio_format = "WAV"
            is_lossless = True
        elif "APE" in title_upper:
            audio_format = "APE"
            is_lossless = True
        elif "DSD" in title_upper or "DSF" in title_upper or "DFF" in title_upper or "SACD" in title_upper:
            audio_format = "DSD"
            is_lossless = True
        elif "MP3" in title_upper:
            audio_format = "MP3"
        elif "AAC" in title_upper:
            audio_format = "AAC"
        elif "OGG" in title_upper or "VORBIS" in title_upper:
            audio_format = "OGG"
        elif "OPUS" in title_upper:
            audio_format = "OPUS"
        elif "WMA" in title_upper:
            audio_format = "WMA"

        # Lossless indicators.
        if "LOSSLESS" in title_upper or "HI-RES" in title_upper or "HIRES" in title_upper:
            is_lossless = True

        # Lossless bit depth and sample rate. A combined form like "24-96" or "24/192"
        # is parsed first, then standalone bit depth and sample rate tokens.
        def _sr_hz(token):
            return {
                "44": 44100,
                "441": 44100,
                "48": 48000,
                "480": 48000,
                "88": 88200,
                "882": 88200,
                "96": 96000,
                "960": 96000,
                "176": 176400,
                "1764": 176400,
                "192": 192000,
            }.get(token.replace(".", ""))

        _sr_token = r"(44\.1|441|44|48\.0|480|48|88\.2|882|88|96\.0|960|96|176\.4|1764|176|192)"

        bit_depth = None
        sample_rate = None

        combo = re.search(r"\b(24|16)[\-/ ]" + _sr_token + r"\b", title_upper)
        if combo:
            bit_depth = int(combo.group(1))
            sample_rate = _sr_hz(combo.group(2))
            is_lossless = True

        if bit_depth is None:
            if "24BIT" in title_upper or "24-BIT" in title_upper or "24 BIT" in title_upper:
                bit_depth = 24
                is_lossless = True
            elif "16BIT" in title_upper or "16-BIT" in title_upper or "16 BIT" in title_upper:
                bit_depth = 16

        if sample_rate is None:
            sr_match = re.search(_sr_token + r"\s*K?HZ", title_upper)
            if sr_match:
                sample_rate = _sr_hz(sr_match.group(1))

        # Lossy bitrate (320, 256, 192, 128, V0, V2). Only parsed for lossy releases so a
        # lossless sample rate like "192kHz" is never read as a 192 kbps bitrate.
        audio_bitrate = None
        if not is_lossless:
            if "320" in title_upper:
                audio_bitrate = "320"
            elif "256" in title_upper:
                audio_bitrate = "256"
            elif "192" in title_upper:
                audio_bitrate = "192"
            elif "128" in title_upper:
                audio_bitrate = "128"
            elif "V0" in title_upper:
                audio_bitrate = "V0"
            elif "V2" in title_upper:
                audio_bitrate = "V2"

        # Discography detection
        is_discography = any(
            x in title_upper
            for x in [
                "DISCOGRAPHY",
                "DISCOGRAFIA",
                "COMPLETE DISCOGRAPHY",
                "FULL DISCOGRAPHY",
                "COLLECTION",
                "COMPLETE COLLECTION",
                "ANTHOLOGY",
                "COMPLETE WORKS",
            ]
        )

        # Year detection
        year = None
        year_match = re.search(r"[\[\(]?(19\d{2}|20[0-2]\d)[\]\)]?", title)
        if year_match:
            year = int(year_match.group(1))

        # Artist/Album parsing (common patterns)
        artist = None
        album = None

        # Pattern: "Artist - Album"
        artist_album_match = re.match(r"^([^-]+)\s*-\s*(.+?)(?:\s*[\[\(]|$)", title)
        if artist_album_match:
            artist = artist_album_match.group(1).strip()
            album = artist_album_match.group(2).strip()
            # Clean up album name (remove year, format indicators)
            album = re.sub(r"\s*[\[\(].*$", "", album).strip()

        # Release group
        release_group = None
        group_match = re.search(r"-([A-Za-z0-9]+)$", title) or re.search(r"\[([A-Za-z0-9]+)\]$", title)
        if group_match:
            release_group = group_match.group(1)

        from app.services import music_quality

        quality_tier = music_quality.tier_from_fields(audio_format, audio_bitrate, is_lossless, bit_depth, sample_rate)

        return {
            "audio_format": audio_format,
            "audio_bitrate": audio_bitrate,
            "bit_depth": bit_depth,
            "sample_rate": sample_rate,
            "quality_tier": quality_tier,
            "is_lossless": is_lossless,
            "is_discography": is_discography,
            "artist": artist,
            "album": album,
            "year": year,
            "release_group": release_group,
        }
