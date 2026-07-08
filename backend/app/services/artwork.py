"""
Artwork writer.

Downloads poster/backdrop/cover images (stored as TMDB paths or full URLs) and writes
Jellyfin-compatible image files into the organized media folders.
"""

import os
from typing import Optional

from app.core.http_client import http_get

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"


def _resolve_url(path_or_url: Optional[str]) -> Optional[str]:
    if not path_or_url:
        return None
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{TMDB_IMAGE_BASE}{path_or_url if path_or_url.startswith('/') else '/' + path_or_url}"


async def download_image(path_or_url: Optional[str]) -> Optional[bytes]:
    resolved = _resolve_url(path_or_url)
    if not resolved:
        return None
    try:
        response = await http_get(resolved)
        response.raise_for_status()
        return response.content
    except Exception:
        return None


async def write_image(folder: str, filename: str, path_or_url: Optional[str]) -> bool:
    data = await download_image(path_or_url)
    if not data:
        return False
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "wb") as f:
            f.write(data)
        return True
    except OSError:
        return False


async def write_video_artwork(folder: str, poster_path: Optional[str], backdrop_path: Optional[str]) -> int:
    """Write poster.jpg + backdrop.jpg into a movie/show/anime folder (Jellyfin reads these)."""
    wrote = 0
    if poster_path and await write_image(folder, "poster.jpg", poster_path):
        wrote += 1
    if backdrop_path and await write_image(folder, "backdrop.jpg", backdrop_path):
        wrote += 1
    return wrote


async def write_album_cover(folder: str, cover_url: Optional[str]) -> bool:
    """Write cover.jpg into an album folder."""
    return await write_image(folder, "cover.jpg", cover_url)


async def write_artist_image(folder: str, picture_url: Optional[str]) -> bool:
    """Write folder.jpg into an artist folder."""
    return await write_image(folder, "folder.jpg", picture_url)
