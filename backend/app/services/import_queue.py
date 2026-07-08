"""
Manual import queue.

Holds video files from completed downloads that could not be auto-organized
(usually because season/episode numbers could not be parsed), and resolves them
once a user maps them to a media item and (for shows/anime) a season/episode.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.services.file_manager import FileManager
from app.services import naming_tokens
from app.services.metadata_extractor import MetadataExtractor
from app.services.folder_selector import folderSelector

logger = logging.getLogger(__name__)


async def queue_unmatched_file(
    conn,
    torrent_hash: str,
    torrent_name: str,
    file_path: str,
    media_type: str,
    media_id: int,
    root_folder_id: Optional[int],
) -> None:
    """Insert a file into the import queue if not already present."""
    try:
        size = os.path.getsize(file_path) if os.path.exists(file_path) else None
    except OSError:
        size = None

    await conn.execute(
        """
        INSERT INTO import_queue (
            torrent_hash, torrent_name, file_path, size, media_type, media_id,
            root_folder_id, status
        )
        SELECT $1, $2, $3, $4, $5, $6, $7, 'pending'
        WHERE NOT EXISTS (
            SELECT 1 FROM import_queue WHERE torrent_hash = $1 AND file_path = $3
        )
        """,
        torrent_hash,
        torrent_name,
        file_path,
        size,
        media_type,
        media_id,
        root_folder_id,
    )


async def _get_profile_settings(conn, media_id: int, media_type: str) -> Dict[str, Any]:
    table_map = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums"}
    table = table_map.get(media_type)
    if not table:
        return {}
    row = await conn.fetchrow(
        f"""
        SELECT mp.illegal_char_replacement, mp.colon_replacement,
               mp.movie_naming_format, mp.movie_folder_format,
               mp.show_naming_format, mp.show_folder_format,
               mp.anime_naming_format, mp.anime_folder_format
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
    )
    return dict(row) if row else {}


async def resolve_import_item(
    conn,
    item: Dict[str, Any],
    media_id: int,
    season_number: Optional[int],
    episode_number: Optional[int],
) -> str:
    """
    Organize a queued file into the library using the resolved media mapping.
    Returns the final destination path. Raises on failure.
    """
    media_type = item["media_type"]
    source_path = item["file_path"]
    root_folder_id = item.get("root_folder_id")

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file no longer exists: {source_path}")

    root_folder = await folderSelector.getFolder(conn, root_folder_id) if root_folder_id else None
    if not root_folder:
        raise ValueError("No root folder available for this import")
    root_path = root_folder["root_path"]

    file_manager = FileManager()
    metadata_extractor = MetadataExtractor()
    profile = await _get_profile_settings(conn, media_id, media_type)
    illegal_replacement = profile.get("illegal_char_replacement") or ""
    colon_replacement = profile.get("colon_replacement") or " -"
    source_ext = Path(source_path).suffix
    file_metadata = metadata_extractor.extract_metadata(source_path)
    quality_detected = file_metadata.get("quality") if file_metadata else None

    if media_type == "movie":
        movie = await conn.fetchrow("SELECT title, release_date, tmdb_id FROM movies WHERE id = $1", media_id)
        if not movie:
            raise ValueError("Movie not found")
        naming = profile.get("movie_naming_format") or "{Movie CleanTitle} ({Release Year})"
        folder = profile.get("movie_folder_format") or "{Movie CleanTitle} ({Release Year})"
        nameContext = naming_tokens.build_movie_context(dict(movie), source_path, Path(source_path).name)
        folder_name = naming_tokens.render(
            folder,
            nameContext,
            illegal_replacement=illegal_replacement,
            colon_replacement=colon_replacement,
        )
        filename = naming_tokens.render(
            naming,
            nameContext,
            illegal_replacement=illegal_replacement,
            colon_replacement=colon_replacement,
            extension=source_ext,
        )
        destination = os.path.join(root_path, folder_name, filename)
        file_manager.organize_file(source_path, destination, "hardlink")
        await conn.execute(
            """
            UPDATE movies SET status = 'completed', has_file = TRUE,
                file_path = $1, quality_detected = $2, root_folder_id = $3, updated_at = NOW()
            WHERE id = $4
            """,
            destination,
            quality_detected,
            root_folder_id,
            media_id,
        )
        return destination

    if media_type in ("show", "anime"):
        if episode_number is None:
            raise ValueError("Episode number is required for shows and anime")
        table = "shows" if media_type == "show" else "anime"
        media = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", media_id)
        if not media:
            raise ValueError(f"{media_type} not found")
        title = media["title"]

        episodeInfo = {
            "season_number": season_number or 1,
            "episode_number": episode_number,
            "episode_title": "",
        }
        if media_type == "show":
            naming = profile.get("show_naming_format") or "{Show Title} - S{Season:00}E{Episode:00}"
            folder = profile.get("show_folder_format") or "{Show Title}/Season {Season:00}"
            nameContext = naming_tokens.build_show_context(
                dict(media), episodeInfo, source_path, Path(source_path).name
            )
        else:
            naming = profile.get("anime_naming_format") or "{Anime Title} - {Episode:00}"
            folder = profile.get("anime_folder_format") or "{Anime Title}"
            nameContext = naming_tokens.build_anime_context(
                dict(media), episodeInfo, source_path, Path(source_path).name
            )

        folder_name = naming_tokens.render(
            folder,
            nameContext,
            illegal_replacement=illegal_replacement,
            colon_replacement=colon_replacement,
        )
        filename = naming_tokens.render(
            naming,
            nameContext,
            illegal_replacement=illegal_replacement,
            colon_replacement=colon_replacement,
            extension=source_ext,
        )
        destination = os.path.join(root_path, folder_name, filename)
        file_manager.organize_file(source_path, destination, "hardlink")
        await conn.execute(
            f"""
            UPDATE {table} SET status = 'completed', has_file = TRUE,
                file_path = $1, quality_detected = $2, root_folder_id = $3, updated_at = NOW()
            WHERE id = $4
            """,
            destination,
            quality_detected,
            root_folder_id,
            media_id,
        )
        return destination

    raise ValueError(f"Unsupported media type for import: {media_type}")
