"""
Music quality tiers.

Defines the ordered ladder of music quality tiers, from lossy bitrates through
lossless bit-depth and sample-rate rungs up to DSD, and the logic to map a
release title or a decoded file to a tier, compare tiers, and decide upgrades.

The "lossless_unknown" rung is the best-effort floor for a lossless release whose
title omits bit depth and sample rate. The true rung is resolved from the file
after import via tier_from_audio_info.
"""

from typing import Optional, Dict, Any, List

# Tier keys in ascending quality order. A tier's rank is its index in this list.
TIER_ORDER: List[str] = [
    "ogg",
    "aac",
    "mp3_128",
    "mp3_192",
    "mp3_256",
    "mp3_320",
    "lossless_unknown",
    "lossless_16_44",
    "lossless_16_48",
    "lossless_24_unknown",
    "lossless_24_48",
    "lossless_24_96",
    "lossless_24_192",
    "dsd",
]

TIER_RANK: Dict[str, int] = {tier: index for index, tier in enumerate(TIER_ORDER)}

TIER_LABELS: Dict[str, str] = {
    "ogg": "OGG / Opus",
    "aac": "AAC",
    "mp3_128": "MP3 128",
    "mp3_192": "MP3 192",
    "mp3_256": "MP3 256 / V2",
    "mp3_320": "MP3 320 / V0",
    "lossless_unknown": "Lossless (unspecified)",
    "lossless_16_44": "FLAC 16-bit / 44.1kHz (CD)",
    "lossless_16_48": "FLAC 16-bit / 48kHz",
    "lossless_24_unknown": "FLAC 24-bit (Hi-Res, rate unspecified)",
    "lossless_24_48": "FLAC 24-bit / 44.1-48kHz (Hi-Res)",
    "lossless_24_96": "FLAC 24-bit / 88.2-96kHz (Hi-Res)",
    "lossless_24_192": "FLAC 24-bit / 176.4-192kHz (Hi-Res)",
    "dsd": "DSD / SACD",
}

LOSSLESS_TIERS = {
    "lossless_unknown",
    "lossless_16_44",
    "lossless_16_48",
    "lossless_24_unknown",
    "lossless_24_48",
    "lossless_24_96",
    "lossless_24_192",
    "dsd",
}

# Uppercase format tokens considered lossless when parsed from a release title.
LOSSLESS_FORMATS = {"FLAC", "ALAC", "WAV", "APE", "WAVPACK", "WV", "TAK", "TTA", "DSD", "DSF", "DFF"}

# Cascade search terms per tier. Lossless rungs share the FLAC search text because a
# torrent title rarely states bit depth or sample rate, so the true rung is confirmed
# from the file after download.
SEARCH_TERMS: Dict[str, str] = {
    "ogg": "OGG",
    "aac": "AAC",
    "mp3_128": "MP3 128",
    "mp3_192": "MP3 192",
    "mp3_256": "MP3 256",
    "mp3_320": "MP3 320",
    "lossless_unknown": "FLAC",
    "lossless_16_44": "FLAC",
    "lossless_16_48": "FLAC",
    "lossless_24_unknown": "FLAC 24bit",
    "lossless_24_48": "FLAC 24bit",
    "lossless_24_96": "FLAC 24bit 96kHz",
    "lossless_24_192": "FLAC 24bit 192kHz",
    "dsd": "DSD",
}

# Default tier order when a profile has none configured. Highest quality first.
DEFAULT_TIERS: List[str] = [
    "lossless_24_192",
    "lossless_24_96",
    "lossless_24_48",
    "lossless_24_unknown",
    "lossless_16_48",
    "lossless_16_44",
    "lossless_unknown",
    "mp3_320",
    "mp3_256",
]


def rank(tier: Optional[str]) -> int:
    """Return the ascending-quality rank of a tier, or -1 when unknown."""
    return TIER_RANK.get(tier or "", -1)


def label(tier: Optional[str]) -> str:
    """Return the human label for a tier."""
    return TIER_LABELS.get(tier or "", "Unknown")


def is_lossless(tier: Optional[str]) -> bool:
    return tier in LOSSLESS_TIERS


def _lossless_tier(bit_depth: Optional[int], sample_rate_hz: Optional[int]) -> str:
    """
    Map a lossless bit depth and sample rate to a tier. When the bit depth is known
    but the sample rate is not, a 24-bit release still ranks as hi-res and a 16-bit
    release is assumed to be CD. When neither is known, the floor tier is used.
    """
    if bit_depth and bit_depth >= 24:
        if not sample_rate_hz:
            return "lossless_24_unknown"
        if sample_rate_hz > 96000:
            return "lossless_24_192"
        if sample_rate_hz > 48000:
            return "lossless_24_96"
        return "lossless_24_48"
    if bit_depth == 16:
        if sample_rate_hz and sample_rate_hz >= 48000:
            return "lossless_16_48"
        return "lossless_16_44"
    return "lossless_unknown"


def _lossy_tier(fmt: str, bitrate: Optional[str]) -> Optional[str]:
    """Map a lossy format and bitrate token to a tier."""
    token = str(bitrate).upper() if bitrate is not None else ""
    if fmt == "MP3":
        if "320" in token or token == "V0":
            return "mp3_320"
        if "256" in token or token == "V2":
            return "mp3_256"
        if "192" in token:
            return "mp3_192"
        if "128" in token:
            return "mp3_128"
        # Unknown MP3 bitrate lands in the middle rather than the top.
        return "mp3_256"
    if fmt == "AAC":
        return "aac"
    if fmt in ("OGG", "VORBIS", "OPUS"):
        return "ogg"
    if fmt == "WMA":
        return "aac"
    return None


def tier_from_fields(
    audio_format: Optional[str],
    audio_bitrate: Optional[str] = None,
    is_lossless: bool = False,
    bit_depth: Optional[int] = None,
    sample_rate: Optional[int] = None,
) -> Optional[str]:
    """
    Best-effort tier from parsed release fields. Returns None when the format
    cannot be identified.
    """
    fmt = (audio_format or "").upper()
    lossless = bool(is_lossless) or fmt in LOSSLESS_FORMATS

    if fmt in ("DSD", "DSF", "DFF"):
        return "dsd"
    if lossless:
        return _lossless_tier(bit_depth, sample_rate)
    if not fmt:
        return None
    return _lossy_tier(fmt, audio_bitrate)


def tier_from_release(release: Any) -> Optional[str]:
    """Best-effort tier from a parsed release object (title-derived fields)."""
    return tier_from_fields(
        getattr(release, "audio_format", None),
        getattr(release, "audio_bitrate", None),
        getattr(release, "is_lossless", False),
        getattr(release, "bit_depth", None),
        getattr(release, "sample_rate", None),
    )


def tier_from_audio_info(audio_info: Dict[str, Any]) -> Optional[str]:
    """
    Authoritative tier from a decoded audio stream (ffprobe). Reads codec,
    sample_rate (Hz), bit_depth (bits per sample), and bit_rate (bps).
    """
    codec = (audio_info.get("codec") or "").upper()

    sample_rate = audio_info.get("sample_rate")
    try:
        sample_rate = int(sample_rate) if sample_rate else None
    except TypeError, ValueError:
        sample_rate = None

    bit_depth = audio_info.get("bit_depth")
    try:
        bit_depth = int(bit_depth) if bit_depth else None
    except TypeError, ValueError:
        bit_depth = None

    bit_rate = audio_info.get("bit_rate") or 0

    if codec.startswith("DSD") or codec in ("DSDIFF", "DSF", "DFF"):
        return "dsd"

    lossless_codecs = {"FLAC", "ALAC", "APE", "WAVPACK", "TAK", "TTA", "TRUEHD", "MLP", "WAV"}
    if codec in lossless_codecs or codec.startswith("PCM"):
        return _lossless_tier(bit_depth, sample_rate)

    kbps = bit_rate / 1000.0
    if codec == "MP3":
        if kbps >= 300:
            return "mp3_320"
        if kbps >= 240:
            return "mp3_256"
        if kbps >= 176:
            return "mp3_192"
        if kbps > 0:
            return "mp3_128"
        return "mp3_256"
    if codec == "AAC":
        return "aac"
    if codec in ("VORBIS", "OPUS", "OGG"):
        return "ogg"
    return None


def meets_allowed(tier: Optional[str], allowed_tiers: Optional[List[str]]) -> bool:
    """Whether a tier is in the profile's allowed set. Empty allowed set accepts all."""
    if not allowed_tiers:
        return True
    return tier in allowed_tiers


def needs_music_upgrade(
    current_tier: Optional[str],
    candidate_tier: Optional[str],
    profile: Any,
    upgrade_allowed: Optional[bool] = None,
) -> bool:
    """
    Whether candidate_tier is a worthwhile upgrade over current_tier for a profile.

    upgrade_allowed is the effective per-item decision (item override, else the
    profile default). The candidate must be an allowed tier, must outrank the
    current tier, and the current tier must sit below the profile cutoff.
    """
    effective_allowed = getattr(profile, "upgrade_allowed", None) if upgrade_allowed is None else upgrade_allowed
    if not effective_allowed:
        return False

    allowed = getattr(profile, "music_quality_tiers", None) or []
    if allowed and candidate_tier not in allowed:
        return False

    cutoff = getattr(profile, "music_quality_cutoff", None)
    if cutoff and rank(current_tier) >= rank(cutoff):
        return False

    return rank(candidate_tier) > rank(current_tier)
