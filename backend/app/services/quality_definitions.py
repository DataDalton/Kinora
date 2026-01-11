from typing import Dict, List
from dataclasses import dataclass
from enum import Enum


class Resolution(str, Enum):
    """Video resolution options"""
    R_240P = "240p"
    R_360P = "360p"
    R_480P = "480p"
    R_576P = "576p"
    R_720P = "720p"
    R_1080P = "1080p"
    R_2160P = "2160p"
    R_4320P = "4320p"


class Source(str, Enum):
    """Media source types with quality hierarchy"""
    CAM = "CAM"
    TELESYNC = "TELESYNC"
    TELECINE = "TELECINE"
    WORKPRINT = "WORKPRINT"
    SCREENER = "SCREENER"
    DVDSCR = "DVDSCR"
    REGIONAL = "REGIONAL"
    SDTV = "SDTV"
    HDTV = "HDTV"
    PDTV = "PDTV"
    DSR = "DSR"
    TVRIP = "TVRIP"
    DVD = "DVD"
    DVDR = "DVDR"
    DVD5 = "DVD5"
    DVD9 = "DVD9"
    HDDVD = "HDDVD"
    PPVRIP = "PPVRIP"
    VODRIP = "VODRIP"
    WEBRIP = "WEBRIP"
    WEBDL = "WEB-DL"
    WEB = "WEB"
    HDTC = "HDTC"
    BDRIP = "BDRIP"
    BRRIP = "BRRIP"
    BLURAY = "BLURAY"
    REMUX = "REMUX"
    RAW = "RAW"


class Codec(str, Enum):
    """Video codec options"""
    XVID = "XVID"
    DIVX = "DIVX"
    H264 = "H264"
    X264 = "x264"
    H265 = "H265"
    X265 = "x265"
    HEVC = "HEVC"
    AV1 = "AV1"
    VP9 = "VP9"
    MPEG2 = "MPEG2"
    VC1 = "VC1"


class AudioCodec(str, Enum):
    """Audio codec options"""
    MP3 = "MP3"
    MP2 = "MP2"
    AAC = "AAC"
    AC3 = "AC3"
    EAC3 = "EAC3"
    DTS = "DTS"
    DTS_HD = "DTS-HD"
    DTS_X = "DTS-X"
    DTS_HD_MA = "DTS-HD MA"
    DOLBY_DIGITAL = "Dolby Digital"
    DOLBY_DIGITAL_PLUS = "Dolby Digital Plus"
    DOLBY_ATMOS = "Dolby Atmos"
    TRUEHD = "TrueHD"
    TRUEHD_ATMOS = "TrueHD Atmos"
    FLAC = "FLAC"
    PCM = "PCM"
    OPUS = "OPUS"
    VORBIS = "VORBIS"


class AudioChannels(str, Enum):
    """Audio channel configurations"""
    MONO = "1.0"
    STEREO = "2.0"
    SURROUND_2_1 = "2.1"
    SURROUND_5_1 = "5.1"
    SURROUND_6_1 = "6.1"
    SURROUND_7_1 = "7.1"
    ATMOS = "Atmos"


class HDR(str, Enum):
    """HDR formats"""
    NONE = "SDR"
    HDR = "HDR"
    HDR10 = "HDR10"
    HDR10_PLUS = "HDR10+"
    DV_HDR = "DV HDR"
    DOLBY_VISION = "Dolby Vision"
    HLG = "HLG"


class Edition(str, Enum):
    """Release edition types"""
    THEATRICAL = "Theatrical"
    EXTENDED = "Extended"
    UNRATED = "Unrated"
    DIRECTORS_CUT = "Director's Cut"
    CRITERION = "Criterion"
    SPECIAL = "Special Edition"
    REMASTERED = "Remastered"
    IMAX = "IMAX"
    PROPER = "PROPER"
    REPACK = "REPACK"


@dataclass
class QualityDefinition:
    """Complete quality definition with all attributes"""
    resolution: Resolution
    source: Source
    codec: Codec
    audio_codec: AudioCodec
    audio_channels: AudioChannels
    hdr: HDR
    edition: Edition = Edition.THEATRICAL

    def __str__(self) -> str:
        parts = [
            self.resolution.value,
            self.source.value,
            self.codec.value,
            self.audio_codec.value,
            self.audio_channels.value
        ]
        if self.hdr != HDR.NONE:
            parts.append(self.hdr.value)
        if self.edition != Edition.THEATRICAL:
            parts.append(self.edition.value)
        return " ".join(parts)


class QualityHierarchy:
    """
    Hierarchical scoring for quality attributes
    Higher scores indicate better quality
    """

    RESOLUTION_SCORES: Dict[str, int] = {
        Resolution.R_240P.value: 10,
        Resolution.R_360P.value: 20,
        Resolution.R_480P.value: 30,
        Resolution.R_576P.value: 35,
        Resolution.R_720P.value: 50,
        Resolution.R_1080P.value: 75,
        Resolution.R_2160P.value: 100,
        Resolution.R_4320P.value: 125,
    }

    SOURCE_SCORES: Dict[str, int] = {
        Source.CAM.value: 5,
        Source.TELESYNC.value: 10,
        Source.TELECINE.value: 15,
        Source.WORKPRINT.value: 18,
        Source.SCREENER.value: 20,
        Source.DVDSCR.value: 22,
        Source.REGIONAL.value: 25,
        Source.SDTV.value: 28,
        Source.PDTV.value: 30,
        Source.DSR.value: 32,
        Source.TVRIP.value: 35,
        Source.HDTV.value: 40,
        Source.DVD.value: 45,
        Source.DVDR.value: 47,
        Source.DVD5.value: 48,
        Source.DVD9.value: 49,
        Source.HDDVD.value: 52,
        Source.PPVRIP.value: 55,
        Source.VODRIP.value: 58,
        Source.WEBRIP.value: 60,
        Source.WEB.value: 65,
        Source.WEBDL.value: 70,
        Source.HDTC.value: 75,
        Source.BDRIP.value: 78,
        Source.BRRIP.value: 80,
        Source.BLURAY.value: 90,
        Source.REMUX.value: 95,
        Source.RAW.value: 100,
    }

    CODEC_SCORES: Dict[str, int] = {
        Codec.XVID.value: 10,
        Codec.DIVX.value: 15,
        Codec.MPEG2.value: 20,
        Codec.VC1.value: 25,
        Codec.H264.value: 50,
        Codec.X264.value: 55,
        Codec.VP9.value: 60,
        Codec.H265.value: 75,
        Codec.X265.value: 80,
        Codec.HEVC.value: 80,
        Codec.AV1.value: 100,
    }

    AUDIO_CODEC_SCORES: Dict[str, int] = {
        AudioCodec.MP2.value: 5,
        AudioCodec.MP3.value: 10,
        AudioCodec.AAC.value: 20,
        AudioCodec.VORBIS.value: 25,
        AudioCodec.OPUS.value: 30,
        AudioCodec.AC3.value: 40,
        AudioCodec.DOLBY_DIGITAL.value: 45,
        AudioCodec.EAC3.value: 50,
        AudioCodec.DOLBY_DIGITAL_PLUS.value: 55,
        AudioCodec.DTS.value: 60,
        AudioCodec.DTS_HD.value: 70,
        AudioCodec.DTS_HD_MA.value: 75,
        AudioCodec.DTS_X.value: 80,
        AudioCodec.TRUEHD.value: 85,
        AudioCodec.DOLBY_ATMOS.value: 90,
        AudioCodec.TRUEHD_ATMOS.value: 95,
        AudioCodec.FLAC.value: 98,
        AudioCodec.PCM.value: 100,
    }

    AUDIO_CHANNELS_SCORES: Dict[str, int] = {
        AudioChannels.MONO.value: 10,
        AudioChannels.STEREO.value: 30,
        AudioChannels.SURROUND_2_1.value: 40,
        AudioChannels.SURROUND_5_1.value: 60,
        AudioChannels.SURROUND_6_1.value: 70,
        AudioChannels.SURROUND_7_1.value: 80,
        AudioChannels.ATMOS.value: 100,
    }

    HDR_SCORES: Dict[str, int] = {
        HDR.NONE.value: 0,
        HDR.HDR.value: 30,
        HDR.HLG.value: 40,
        HDR.HDR10.value: 50,
        HDR.HDR10_PLUS.value: 70,
        HDR.DV_HDR.value: 85,
        HDR.DOLBY_VISION.value: 100,
    }

    EDITION_SCORES: Dict[str, int] = {
        Edition.THEATRICAL.value: 0,
        Edition.SPECIAL.value: 5,
        Edition.UNRATED.value: 10,
        Edition.EXTENDED.value: 15,
        Edition.REMASTERED.value: 20,
        Edition.DIRECTORS_CUT.value: 25,
        Edition.IMAX.value: 30,
        Edition.CRITERION.value: 35,
        Edition.PROPER.value: 40,
        Edition.REPACK.value: 45,
    }

    @classmethod
    def get_quality_score(cls, quality_str: str) -> int:
        """
        Calculate overall quality score from quality string
        Returns total score based on all quality attributes
        """
        score = 0
        quality_upper = quality_str.upper()

        # Resolution scoring
        for resolution, res_score in cls.RESOLUTION_SCORES.items():
            if resolution.replace('p', 'P') in quality_upper:
                score += res_score
                break

        # Source scoring
        for source, src_score in cls.SOURCE_SCORES.items():
            if source in quality_upper:
                score += src_score
                break

        # Codec scoring
        for codec, codec_score in cls.CODEC_SCORES.items():
            if codec.upper() in quality_upper:
                score += codec_score
                break

        return score


# Preset quality profiles for common use cases
QUALITY_PRESETS = {
    "Ultra HD": {
        "description": "Maximum quality 4K releases",
        "preferred_resolutions": [Resolution.R_2160P.value, Resolution.R_4320P.value],
        "allowed_resolutions": [Resolution.R_2160P.value, Resolution.R_4320P.value],
        "preferred_sources": [Source.REMUX.value, Source.BLURAY.value, Source.WEBDL.value],
        "preferred_codecs": [Codec.AV1.value, Codec.HEVC.value, Codec.X265.value],
        "preferred_audio": [AudioCodec.TRUEHD_ATMOS.value, AudioCodec.DTS_HD_MA.value, AudioCodec.DOLBY_ATMOS.value],
        "preferred_hdr": [HDR.DOLBY_VISION.value, HDR.HDR10_PLUS.value, HDR.HDR10.value],
        "cutoff_resolution": Resolution.R_2160P.value,
        "min_size_gb": 15,
        "max_size_gb": 150,
    },
    "High Quality": {
        "description": "1080p high quality releases",
        "preferred_resolutions": [Resolution.R_1080P.value],
        "allowed_resolutions": [Resolution.R_1080P.value, Resolution.R_720P.value],
        "preferred_sources": [Source.BLURAY.value, Source.WEBDL.value, Source.REMUX.value],
        "preferred_codecs": [Codec.X265.value, Codec.X264.value],
        "preferred_audio": [AudioCodec.DTS_HD_MA.value, AudioCodec.DTS.value, AudioCodec.AC3.value],
        "preferred_hdr": [HDR.HDR10.value],
        "cutoff_resolution": Resolution.R_1080P.value,
        "min_size_gb": 5,
        "max_size_gb": 40,
    },
    "Balanced": {
        "description": "Balanced quality and file size",
        "preferred_resolutions": [Resolution.R_1080P.value, Resolution.R_720P.value],
        "allowed_resolutions": [Resolution.R_1080P.value, Resolution.R_720P.value, Resolution.R_480P.value],
        "preferred_sources": [Source.WEBDL.value, Source.WEBRIP.value, Source.BLURAY.value],
        "preferred_codecs": [Codec.X265.value, Codec.X264.value],
        "preferred_audio": [AudioCodec.AAC.value, AudioCodec.AC3.value],
        "preferred_hdr": [],
        "cutoff_resolution": Resolution.R_720P.value,
        "min_size_gb": 1,
        "max_size_gb": 15,
    },
    "Space Saver": {
        "description": "Smaller file sizes with acceptable quality",
        "preferred_resolutions": [Resolution.R_720P.value, Resolution.R_480P.value],
        "allowed_resolutions": [Resolution.R_720P.value, Resolution.R_480P.value, Resolution.R_360P.value],
        "preferred_sources": [Source.WEBRIP.value, Source.WEBDL.value],
        "preferred_codecs": [Codec.X265.value, Codec.HEVC.value],
        "preferred_audio": [AudioCodec.AAC.value],
        "preferred_hdr": [],
        "cutoff_resolution": Resolution.R_480P.value,
        "min_size_gb": 0.3,
        "max_size_gb": 5,
    },
}
