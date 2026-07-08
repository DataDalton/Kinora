"""
Naming token engine.

Renders the Radarr/Sonarr-style naming presets stored in media_profiles
(*_naming_format / *_folder_format) into real file and folder names. The frontend
presets use tokens like {Movie CleanTitle}, {Release Year}, {TmdbId},
{MediaInfo AudioCodec}, {-Release Group}, and Radarr optional-group syntax such as
{[Quality Full]}. This module resolves those tokens from database rows plus ffprobe
media info and the release filename, then cleans up empty groups and separators.

The presets themselves are never modified.
"""

import re
from typing import Any, Dict, Optional

from app.services.metadata_extractor import metadata_extractor
from app.services.filename_parser import FilenameParser
from app.services.media_profile import media_profile_service

_filename_parser = FilenameParser()

# Every token the presets can contain. Longer names first so substring matching
# inside a brace group resolves the most specific token.
KNOWN_TOKENS = [
    "Movie CleanTitle",
    "Show Title",
    "Anime Title",
    "Release Year",
    "Episode Title",
    "Absolute Episode",
    "Edition Tags",
    "Quality Resolution",
    "Quality Full",
    "MediaInfo AudioChannels",
    "MediaInfo AudioLanguages",
    "MediaInfo AudioCodec",
    "MediaInfo VideoDynamicRangeType",
    "MediaInfo VideoBitDepth",
    "MediaInfo VideoCodec",
    "Release Group",
    "TmdbId",
    "TvdbId",
    "AnilistId",
    "MalId",
    "ImdbId",
    "Season",
    "Episode",
    # music (lowercase, already matched the backend token maps)
    "artist",
    "album",
    "year",
    "track",
    "disc",
    "title",
    "genre",
]
_TOKENS_BY_LENGTH = sorted(KNOWN_TOKENS, key=len, reverse=True)

# ffprobe codec_name -> display codec used in release names
_VIDEO_CODEC_MAP = {
    "hevc": "HEVC",
    "h265": "HEVC",
    "x265": "HEVC",
    "h264": "H264",
    "avc": "H264",
    "x264": "H264",
    "av1": "AV1",
    "mpeg4": "XVID",
    "vp9": "VP9",
}
_AUDIO_CODEC_MAP = {
    "aac": "AAC",
    "ac3": "AC3",
    "eac3": "EAC3",
    "dts": "DTS",
    "truehd": "TrueHD",
    "flac": "FLAC",
    "opus": "Opus",
    "mp3": "MP3",
    "vorbis": "Vorbis",
}


def _channels_to_layout(channels: Optional[int]) -> str:
    if not channels:
        return ""
    return {1: "1.0", 2: "2.0", 6: "5.1", 7: "6.1", 8: "7.1"}.get(channels, f"{channels}.0")


def _resolution_from_height(height: Optional[int]) -> str:
    if not height:
        return ""
    if height >= 2160:
        return "2160p"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return f"{height}p"


def _extract_release_group(release_name: Optional[str]) -> str:
    """Release group is the trailing -GROUP token of a scene/p2p release name."""
    if not release_name:
        return ""
    stem = release_name.rsplit(".", 1)[0]
    m = re.search(r"-([A-Za-z0-9]{2,})$", stem.strip())
    if m:
        return m.group(1)
    # anime style [Group] prefix
    m = re.match(r"^\[([^\]]+)\]", stem.strip())
    return m.group(1) if m else ""


def build_media_info(file_path: Optional[str]) -> Dict[str, str]:
    """Resolve the {MediaInfo ...} and {Quality ...} tokens from ffprobe."""
    info = {
        "Quality Resolution": "",
        "MediaInfo VideoCodec": "",
        "MediaInfo VideoBitDepth": "",
        "MediaInfo VideoDynamicRangeType": "",
        "MediaInfo AudioCodec": "",
        "MediaInfo AudioChannels": "",
        "MediaInfo AudioLanguages": "",
    }
    if not file_path:
        return info
    meta = metadata_extractor.extract_metadata(file_path)
    if not meta:
        return info

    video = meta.get("video") or {}
    info["Quality Resolution"] = _resolution_from_height(video.get("height"))
    vcodec = (video.get("codec") or "").lower()
    info["MediaInfo VideoCodec"] = _VIDEO_CODEC_MAP.get(vcodec, video.get("codec") or "")
    if video.get("bit_depth"):
        info["MediaInfo VideoBitDepth"] = str(video["bit_depth"])
    dynamic_range = video.get("dynamic_range")
    # SDR is the absence of HDR - do not print it in names
    info["MediaInfo VideoDynamicRangeType"] = "" if dynamic_range in (None, "SDR") else dynamic_range

    audio_list = meta.get("audio") or []
    if audio_list:
        first = audio_list[0]
        acodec = (first.get("codec") or "").lower()
        info["MediaInfo AudioCodec"] = _AUDIO_CODEC_MAP.get(acodec, first.get("codec") or "")
        info["MediaInfo AudioChannels"] = _channels_to_layout(first.get("channels"))
        langs = [a.get("language") for a in audio_list if a.get("language") and a.get("language") != "und"]
        # de-duplicate, preserve order, uppercase
        seen = []
        for lang in langs:
            up = lang.upper()
            if up not in seen:
                seen.append(up)
        info["MediaInfo AudioLanguages"] = "+".join(seen)
    return info


def _quality_full(context: Dict[str, str], source: str) -> str:
    """Compose {Quality Full} as Source-Resolution (e.g. Bluray-1080p)."""
    resolution = context.get("Quality Resolution") or ""
    if source and resolution:
        return f"{source}-{resolution}"
    return source or resolution


def build_movie_context(row: Dict[str, Any], file_path: Optional[str], release_name: Optional[str]) -> Dict[str, str]:
    title = row.get("title") or ""
    year = ""
    rd = row.get("release_date")
    if rd:
        year = str(rd.year) if hasattr(rd, "year") else str(rd)[:4]
    ctx = build_media_info(file_path)
    source = media_profile_service._extract_source(release_name or "") or ""
    ctx.update(
        {
            "Movie CleanTitle": title,
            "Release Year": year,
            "TmdbId": str(row["tmdb_id"]) if row.get("tmdb_id") else "",
            "ImdbId": str(row["imdb_id"]) if row.get("imdb_id") else "",
            "Edition Tags": media_profile_service._extract_edition(release_name or "") or "",
            "Release Group": _extract_release_group(release_name),
            "Quality Full": _quality_full(ctx, source),
        }
    )
    return ctx


def build_show_context(
    row: Dict[str, Any], episode_info: Dict[str, Any], file_path: Optional[str], release_name: Optional[str]
) -> Dict[str, str]:
    year = ""
    date = row.get("first_air_date") or row.get("release_date")
    if date:
        year = str(date.year) if hasattr(date, "year") else str(date)[:4]
    ctx = build_media_info(file_path)
    source = media_profile_service._extract_source(release_name or "") or ""
    ctx.update(
        {
            "Show Title": row.get("title") or "",
            "Release Year": year,
            "TmdbId": str(row["tmdb_id"]) if row.get("tmdb_id") else "",
            "TvdbId": str(row["tvdb_id"]) if row.get("tvdb_id") else "",
            "Season": str(episode_info.get("season_number") or ""),
            "Episode": str(episode_info.get("episode_number") or ""),
            "Episode Title": episode_info.get("episode_title") or "",
            "Release Group": _extract_release_group(release_name),
            "Quality Full": _quality_full(ctx, source),
        }
    )
    return ctx


def build_anime_context(
    row: Dict[str, Any], episode_info: Dict[str, Any], file_path: Optional[str], release_name: Optional[str]
) -> Dict[str, str]:
    ctx = build_media_info(file_path)
    source = media_profile_service._extract_source(release_name or "") or ""
    ctx.update(
        {
            "Anime Title": row.get("title") or "",
            "Release Year": str(row["season_year"]) if row.get("season_year") else "",
            "TmdbId": str(row["tmdb_id"]) if row.get("tmdb_id") else "",
            "AnilistId": str(row["anilist_id"]) if row.get("anilist_id") else "",
            "MalId": str(row["mal_id"]) if row.get("mal_id") else "",
            "Season": str(episode_info.get("season_number") or ""),
            "Episode": str(episode_info.get("episode_number") or ""),
            "Absolute Episode": str(episode_info.get("absolute_episode") or ""),
            "Episode Title": episode_info.get("episode_title") or "",
            "Release Group": _extract_release_group(release_name),
            "Quality Full": _quality_full(ctx, source),
        }
    )
    return ctx


def _resolve_group(inner: str, context: Dict[str, str]) -> str:
    """
    Resolve one {...} group. The inner text may carry literal decoration around the
    token name (e.g. '[Quality Full]', '-Release Group', 'Season:00'). If the token
    has a value, keep the decoration; if empty, the whole group renders empty.
    """
    for name in _TOKENS_BY_LENGTH:
        idx = inner.find(name)
        if idx < 0:
            continue
        prefix = inner[:idx]
        rest = inner[idx + len(name) :]
        pad = None
        m = re.match(r":(0+)", rest)
        if m:
            pad = len(m.group(1))
            rest = rest[m.end() :]
        suffix = rest
        value = context.get(name, "")
        if value is None or value == "":
            return ""
        sval = str(value)
        if pad is not None:
            try:
                sval = str(int(sval)).zfill(pad)
            except ValueError, TypeError:
                pass
        return f"{prefix}{sval}{suffix}"
    # unknown token -> render empty so stray {tokens} never reach disk
    return ""


def _cleanup(name: str) -> str:
    """Remove empty decorations and collapse separators left by absent tokens."""
    # empty id brackets: [tmdbid-], [tvdbid-], [anilistid-]
    name = re.sub(r"\[[a-zA-Z]*id-\]", "", name)
    # empty brackets / parens
    name = re.sub(r"\[\s*\]", "", name)
    name = re.sub(r"\(\s*\)", "", name)
    # collapse whitespace within each path segment
    parts = []
    for seg in name.split("/"):
        seg = re.sub(r"\s{2,}", " ", seg)
        seg = re.sub(r"\s*-\s*$", "", seg)  # trailing separator dash
        seg = re.sub(r"^\s*-\s*", "", seg)  # leading separator dash
        seg = seg.replace(" .", ".").strip(" .")
        parts.append(seg)
    return "/".join(parts)


def _clean_illegal(name: str, illegal_replacement: str, colon_replacement: str) -> str:
    """Apply colon and illegal-character replacement per path segment (keep '/')."""
    out_parts = []
    for seg in name.split("/"):
        seg = seg.replace(":", colon_replacement)
        seg = re.sub(r'[\\*?"<>|]', illegal_replacement, seg)
        out_parts.append(seg.strip())
    return "/".join(out_parts)


def sample_context(media_type: str) -> Dict[str, str]:
    """Representative token values for the live naming preview in the UI."""
    common = {
        "Quality Resolution": "1080p",
        "Quality Full": "Bluray-1080p",
        "MediaInfo VideoCodec": "HEVC",
        "MediaInfo VideoBitDepth": "10",
        "MediaInfo VideoDynamicRangeType": "HDR10",
        "MediaInfo AudioCodec": "DTS-HD MA",
        "MediaInfo AudioChannels": "5.1",
        "MediaInfo AudioLanguages": "EN",
        "Release Group": "GROUP",
        "Edition Tags": "IMAX",
    }
    if media_type == "movie":
        return {
            **common,
            "Movie CleanTitle": "The Matrix",
            "Release Year": "1999",
            "TmdbId": "603",
            "ImdbId": "tt0133093",
        }
    if media_type == "show":
        return {
            **common,
            "Show Title": "Breaking Bad",
            "Release Year": "2008",
            "TmdbId": "1396",
            "TvdbId": "81189",
            "Season": "1",
            "Episode": "5",
            "Episode Title": "Gray Matter",
        }
    if media_type == "anime":
        return {
            **common,
            "Anime Title": "Attack on Titan",
            "Release Year": "2013",
            "TmdbId": "1429",
            "AnilistId": "16498",
            "MalId": "16498",
            "Season": "1",
            "Episode": "5",
            "Episode Title": "First Battle",
            "Absolute Episode": "5",
        }
    if media_type == "music":
        return {
            "artist": "Pink Floyd",
            "album": "The Wall",
            "year": "1979",
            "track": "5",
            "disc": "1",
            "title": "Mother",
            "genre": "Rock",
        }
    return {}


def unknown_tokens(fmt: str) -> list:
    """Return token names in a format string that the engine does not recognize."""
    unknown = []
    for inner in re.findall(r"\{([^{}]*)\}", fmt or ""):
        if not any(name in inner for name in KNOWN_TOKENS):
            token = inner.strip("[]-: ")
            if token:
                unknown.append(token)
    return sorted(set(unknown))


def render(
    fmt: str,
    context: Dict[str, str],
    *,
    illegal_replacement: str = "_",
    colon_replacement: str = " -",
    extension: str = "",
) -> str:
    """
    Render a naming/folder format string against a resolved token context.
    Pass extension (with leading dot) for file names; omit for folder names.
    """
    if not fmt:
        return ""
    rendered = re.sub(r"\{([^{}]*)\}", lambda m: _resolve_group(m.group(1), context), fmt)
    rendered = _cleanup(rendered)
    rendered = _clean_illegal(rendered, illegal_replacement, colon_replacement)
    rendered = rendered.strip("/ ").rstrip(".")
    if extension:
        rendered += extension
    return rendered
