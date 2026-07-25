"""
Persistent per-file media metadata.

The media_files table stores one row per physical media file with its ffprobe
attributes (quality, resolution, codec, audio, bit depth, HDR, container). Rows are
written at download completion from the metadata already extracted there, and the read
path reconciles with disk and lazily probes any file without a row (imports, manual
files, legacy libraries). In steady state the file panel is a plain database read
instead of an ffprobe per load, and one row per file represents movie versions.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional

from app.services.metadata_extractor import MetadataExtractor
from app.services import music_quality

_extractor = MetadataExtractor()

# Columns written for each file, in INSERT order (after media_type, media_id, file_path).
_COLUMNS = [
    "file_name",
    "file_size",
    "quality",
    "resolution",
    "codec",
    "audio_codec",
    "audio_channels",
    "container",
    "bit_depth",
    "hdr",
]

_UPSERT_SQL = """
    INSERT INTO media_files (
        media_type, media_id, file_path, file_name, file_size, quality, resolution,
        codec, audio_codec, audio_channels, container, bit_depth, hdr
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    ON CONFLICT (file_path) DO UPDATE SET
        media_type = EXCLUDED.media_type,
        media_id = EXCLUDED.media_id,
        file_name = EXCLUDED.file_name,
        file_size = EXCLUDED.file_size,
        quality = EXCLUDED.quality,
        resolution = EXCLUDED.resolution,
        codec = EXCLUDED.codec,
        audio_codec = EXCLUDED.audio_codec,
        audio_channels = EXCLUDED.audio_channels,
        container = EXCLUDED.container,
        bit_depth = EXCLUDED.bit_depth,
        hdr = EXCLUDED.hdr,
        updated_at = NOW()
    RETURNING *
"""


def _audio_channels(stream: Dict[str, Any]) -> Optional[str]:
    channels = stream.get("channel_layout")
    if not channels and stream.get("channels"):
        channels = str(stream.get("channels"))
    return channels


def attrs_from_metadata(path: str, metadata: Optional[Dict[str, Any]], is_audio: bool) -> Dict[str, Any]:
    """Map an ffprobe metadata dict to the media_files column values for one file."""
    attrs: Dict[str, Any] = {
        "file_name": os.path.basename(path),
        "file_size": None,
        "quality": None,
        "resolution": None,
        "codec": None,
        "audio_codec": None,
        "audio_channels": None,
        "container": (os.path.splitext(path)[1].lstrip(".").upper() or None),
        "bit_depth": None,
        "hdr": False,
    }
    try:
        attrs["file_size"] = os.path.getsize(path)
    except OSError:
        pass

    if not metadata:
        return attrs

    audio_streams = metadata.get("audio") or []
    first_audio = audio_streams[0] if audio_streams else None

    if is_audio:
        if first_audio:
            attrs["audio_codec"] = (first_audio.get("codec") or "").upper() or None
            attrs["audio_channels"] = _audio_channels(first_audio)
            depth = first_audio.get("bit_depth")
            if depth:
                attrs["bit_depth"] = f"{depth}-bit"
            tier = music_quality.tier_from_audio_info(first_audio)
            if tier:
                attrs["quality"] = music_quality.label(tier)
        return attrs

    attrs["quality"] = metadata.get("quality")
    video = metadata.get("video") or {}
    if video:
        width, height = video.get("width"), video.get("height")
        if width and height:
            attrs["resolution"] = f"{width}x{height}"
        attrs["codec"] = (video.get("codec") or "").upper() or None
        depth = video.get("bit_depth")
        if depth:
            attrs["bit_depth"] = f"{depth}bit"
        dynamic_range = video.get("dynamic_range")
        attrs["hdr"] = bool(dynamic_range and dynamic_range.upper() != "SDR")
    if first_audio:
        attrs["audio_codec"] = (first_audio.get("codec") or "").upper() or None
        attrs["audio_channels"] = _audio_channels(first_audio)
    return attrs


def _probe(path: str, is_audio: bool) -> Dict[str, Any]:
    """Blocking ffprobe of one file into the media_files column values."""
    try:
        metadata = _extractor.extract_metadata(path)
    except Exception:
        metadata = None
    return attrs_from_metadata(path, metadata, is_audio)


async def store(conn, media_type: str, media_id: int, path: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert one media_files row from precomputed attributes. Returns the stored row."""
    row = await conn.fetchrow(_UPSERT_SQL, media_type, media_id, path, *[attrs[column] for column in _COLUMNS])
    return dict(row)


async def sync_and_get(conn, media_type: str, media_id: int, paths: List[str], is_audio: bool) -> List[Dict[str, Any]]:
    """
    Reconcile stored rows with the given on-disk paths and return the rows for those
    paths. A file without a row is probed once (off the event loop) and persisted, a
    row whose file is no longer listed is removed, and everything else is a plain read.
    """
    rows = await conn.fetch(
        "SELECT * FROM media_files WHERE media_type = $1 AND media_id = $2",
        media_type,
        media_id,
    )
    by_path = {r["file_path"]: dict(r) for r in rows}
    path_set = set(paths)

    stale = [p for p in by_path if p not in path_set]
    if stale:
        await conn.execute("DELETE FROM media_files WHERE file_path = ANY($1)", stale)

    result: List[Dict[str, Any]] = []
    for path in paths:
        existing = by_path.get(path)
        if existing:
            result.append(existing)
            continue
        attrs = await asyncio.to_thread(_probe, path, is_audio)
        result.append(await store(conn, media_type, media_id, path, attrs))

    return result


async def delete_for_item(conn, media_type: str, media_id: int) -> None:
    """Remove all stored file rows for a media item (called when the item is deleted)."""
    await conn.execute("DELETE FROM media_files WHERE media_type = $1 AND media_id = $2", media_type, media_id)


async def delete_one(conn, file_path: str) -> None:
    """Remove the stored row for a single file (called when one version is deleted)."""
    await conn.execute("DELETE FROM media_files WHERE file_path = $1", file_path)
