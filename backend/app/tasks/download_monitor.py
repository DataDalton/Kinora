import os
import re
import time
from pathlib import Path
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.download_clients.base import TorrentState
from app.core.webtransport import webtransport_manager
from app.services.file_manager import FileManager
from app.services.metadata_extractor import MetadataExtractor
from app.services.folder_selector import folderSelector
from app.core.cache import cacheSet


async def get_file_operation(conn, media_id: int, media_type: str) -> str:
    """
    Get file operation (hardlink/copy) from media's profile.
    Returns 'hardlink' if use_hardlinks is True, 'copy' otherwise.
    Defaults to 'hardlink' if no profile is set.
    """
    table_map = {
        'movie': 'movies',
        'show': 'shows',
        'anime': 'anime',
        'album': 'albums',
    }

    table = table_map.get(media_type)
    if not table:
        return 'hardlink'

    result = await conn.fetchrow(
        f"""
        SELECT mp.use_hardlinks
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id
    )

    if result and result['use_hardlinks'] is not None:
        return 'hardlink' if result['use_hardlinks'] else 'copy'

    return 'hardlink'


async def get_profile_settings(conn, media_id: int, media_type: str) -> dict:
    """
    Get profile settings for file organization.
    Returns dict with naming formats and character replacement settings.
    """
    table_map = {
        'movie': 'movies',
        'show': 'shows',
        'anime': 'anime',
        'album': 'albums',
    }

    table = table_map.get(media_type)
    if not table:
        return {}

    result = await conn.fetchrow(
        f"""
        SELECT
            mp.use_hardlinks,
            mp.illegal_char_replacement,
            mp.colon_replacement,
            mp.movie_naming_format,
            mp.movie_folder_format,
            mp.show_naming_format,
            mp.show_folder_format,
            mp.anime_naming_format,
            mp.anime_folder_format,
            mp.music_artist_folder_format,
            mp.music_album_folder_format,
            mp.music_track_naming_format
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id
    )

    if not result:
        return {}

    return dict(result)


def organize_file_hardlink(file_manager: FileManager, source: str, dest: str) -> bool:
    """
    Organize file using hardlink only. No fallback to copy.
    Root folder and download folder are paired on same filesystem to guarantee hardlinks work.
    Returns True on success, raises exception on failure.
    """
    return file_manager.organize_file(source, dest, 'hardlink')


def parse_episode_info(filename: str) -> dict:
    """
    Parse season and episode numbers from filename.
    Returns dict with season_number, episode_number, and episode_title (if found).
    """
    result = {
        'season_number': None,
        'episode_number': None,
        'episode_title': None,
    }

    # Standard patterns: S01E01, S1E1, 1x01
    patterns = [
        r'[Ss](\d{1,2})[Ee](\d{1,3})',  # S01E01
        r'(\d{1,2})x(\d{1,3})',          # 1x01
        r'[Ss]eason\s*(\d{1,2}).*[Ee]pisode\s*(\d{1,3})',  # Season 1 Episode 1
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            result['season_number'] = int(match.group(1))
            result['episode_number'] = int(match.group(2))
            break

    # Anime-style: [Group] Title - 01 [Quality].mkv
    if result['episode_number'] is None:
        anime_pattern = r'[-_\s](\d{2,3})(?:v\d)?[\s\[\.]'
        match = re.search(anime_pattern, filename)
        if match:
            result['episode_number'] = int(match.group(1))
            result['season_number'] = 1  # Assume season 1 for anime

    return result


@celery_app.task(name="app.tasks.download_monitor.check_downloads")
def check_downloads():
    """
    Monitor download client for active downloads
    Updates progress and triggers post-processing when complete
    """
    return runAsync(async_check_downloads())


async def async_check_downloads():
    """
    Async implementation of download monitoring
    """
    taskName = "download_monitor"
    startTime = time.time()
    status = "success"

    try:
        # Get qBittorrent client instance
        client = await get_qbittorrent_client()
        if not client:
            return {"status": "skipped", "reason": "qBittorrent not configured"}

        # Get all active torrents from download client
        torrents = await client.get_torrents()

        if not torrents:
            return {"status": "success", "active_downloads": 0, "completed": 0}

        completed_count = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            for torrent in torrents:
                # Update progress in database
                await conn.execute(
                    """
                    UPDATE download_history
                    SET progress = $1, updated_at = NOW()
                    WHERE torrent_hash = $2 AND status IN ('downloading', 'pending')
                    """,
                    torrent.progress,
                    torrent.hash,
                )

                # Get download record
                download_record = await conn.fetchrow(
                    "SELECT * FROM download_history WHERE torrent_hash = $1",
                    torrent.hash
                )

                if not download_record:
                    continue

                # Send real-time progress update
                download_dict = dict(download_record)
                user_ids = webtransport_manager.get_active_users()
                for user_id in user_ids:
                    await webtransport_manager.send_download_update(
                        user_id,
                        torrent.hash,
                        torrent.progress,
                        torrent.download_speed
                    )

                # Handle completed downloads
                if torrent.state == TorrentState.SEEDING or torrent.progress >= 1.0:
                    if download_dict["status"] != "completed":
                        async with conn.transaction():
                            await handle_completed_download(conn, download_dict, torrent)
                        completed_count += 1

                # Handle failed downloads
                elif torrent.state == TorrentState.ERROR:
                    await conn.execute(
                        """
                        UPDATE download_history
                        SET status = 'failed', error_message = $1, updated_at = NOW()
                        WHERE torrent_hash = $2
                        """,
                        "Torrent error in download client",
                        torrent.hash
                    )

        return {
            "status": "success",
            "active_downloads": len(torrents),
            "completed": completed_count,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Download monitoring error: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(f"task:last_run:{taskName}", {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "durationMs": elapsedMs,
        }, expire=86400)


async def handle_completed_download(conn, download_record, torrent):
    """
    Handle post-processing for completed download.
    Organizes files using FileManager with hardlinks and updates database.
    Root folder comes from download_history.root_folder_id.
    """
    try:
        # Mark as completed
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'completed', completed_at = NOW(), progress = 1.0, updated_at = NOW()
            WHERE torrent_hash = $1
            """,
            torrent.hash
        )

        media_id = download_record["media_id"]
        media_type = download_record["media_type"]
        root_folder_id = download_record.get("root_folder_id")

        # Get the root folder from download history
        root_folder = None
        if root_folder_id:
            root_folder = await folderSelector.getFolder(conn, root_folder_id)

        if not root_folder:
            print(f"No root folder found for download {torrent.hash}")
            return

        root_path = root_folder["root_path"]

        # Initialize services
        file_manager = FileManager()
        metadata_extractor = MetadataExtractor()

        # Get profile settings for file organization
        profile = await get_profile_settings(conn, media_id, media_type)
        illegal_replacement = profile.get('illegal_char_replacement') or ''
        colon_replacement = profile.get('colon_replacement') or ' -'

        # Update media record based on type
        if media_type == "movie":
            # Get movie details
            movie = await conn.fetchrow(
                """
                SELECT title, release_date, tmdb_id
                FROM movies WHERE id = $1
                """,
                media_id
            )

            if not movie:
                print(f"Movie not found: {media_id}")
                return

            title = movie["title"]
            year = movie["release_date"][:4] if movie["release_date"] else None

            # Find the largest video file in torrent directory
            source_path = file_manager.extract_largest_video(torrent.save_path)

            if not source_path:
                print(f"No video file found in {torrent.save_path}")
                await conn.execute(
                    """
                    UPDATE movies
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, root_folder_id = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    torrent.save_path,
                    torrent.size,
                    root_folder_id,
                    media_id
                )
                return

            # Extract metadata from file
            file_metadata = metadata_extractor.extract_metadata(source_path)
            quality_detected = file_metadata.get('quality') if file_metadata else None

            # Get naming pattern from profile or use default
            naming_pattern = profile.get('movie_naming_format') or "{title} ({year})"
            folder_pattern = profile.get('movie_folder_format') or "{title} ({year})"

            # Build movie data for formatting
            source_ext = Path(source_path).suffix
            movie_data = {
                'title': title,
                'year': year,
                'quality': quality_detected,
                'tmdb_id': movie["tmdb_id"],
                'extension': source_ext,
            }

            # Format folder and filename
            folder_name = file_manager.format_movie_filename(
                pattern=folder_pattern,
                movie_data=movie_data,
                include_extension=False,
                illegal_replacement=illegal_replacement,
                colon_replacement=colon_replacement,
            )
            filename = file_manager.format_movie_filename(
                pattern=naming_pattern,
                movie_data=movie_data,
                include_extension=True,
                illegal_replacement=illegal_replacement,
                colon_replacement=colon_replacement,
            )

            # Construct full destination path using root folder's root_path
            destination_path = os.path.join(root_path, folder_name, filename)

            # Organize file using hardlink (no fallback - folders are on same filesystem)
            try:
                organize_file_hardlink(file_manager, source_path, destination_path)
                final_path = destination_path
                file_size = os.path.getsize(final_path) if os.path.exists(final_path) else torrent.size
            except Exception as e:
                print(f"Hardlink failed: {e}. This should not happen - check folder configuration.")
                raise

            # Update database with organized file info and root folder assignment
            await conn.execute(
                """
                UPDATE movies
                SET status = 'completed', has_file = TRUE,
                    file_path = $1, file_size = $2, quality_detected = $3,
                    root_folder_id = $4, updated_at = NOW()
                WHERE id = $5
                """,
                final_path,
                file_size,
                quality_detected,
                root_folder_id,
                media_id
            )

        elif media_type == "show":
            # Get show details
            show = await conn.fetchrow(
                """
                SELECT title
                FROM shows WHERE id = $1
                """,
                media_id
            )

            if not show:
                print(f"Show not found: {media_id}")
                return

            title = show["title"]

            # Get naming patterns from profile
            naming_pattern = profile.get('show_naming_format') or "{series} - S{season:00}E{episode:00}"
            folder_pattern = profile.get('show_folder_format') or "{series}/Season {season:00}"

            # Get all video files from torrent
            video_files = file_manager.extract_all_videos(torrent.save_path)

            if not video_files:
                print(f"No video files found in {torrent.save_path}")
                await conn.execute(
                    """
                    UPDATE shows
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, root_folder_id = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    torrent.save_path,
                    torrent.size,
                    root_folder_id,
                    media_id
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None

                for source_path in video_files:
                    # Parse episode info from filename
                    episode_info = parse_episode_info(Path(source_path).name)

                    if episode_info['episode_number'] is None:
                        # Skip files we can't parse episode info from
                        continue

                    # Extract metadata from first file for quality detection
                    if quality_detected is None:
                        file_metadata = metadata_extractor.extract_metadata(source_path)
                        quality_detected = file_metadata.get('quality') if file_metadata else None

                    # Build show data for formatting
                    source_ext = Path(source_path).suffix
                    show_data = {
                        'series_title': title,
                        'season_number': episode_info['season_number'] or 1,
                        'episode_number': episode_info['episode_number'],
                        'episode_title': episode_info.get('episode_title') or '',
                        'quality': quality_detected,
                        'extension': source_ext,
                    }

                    # Format folder and filename
                    folder_name = file_manager.format_show_filename(
                        pattern=folder_pattern,
                        show_data=show_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = file_manager.format_show_filename(
                        pattern=naming_pattern,
                        show_data=show_data,
                        include_extension=True,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )

                    destination_path = os.path.join(root_path, folder_name, filename)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for episode: {e}. Check folder configuration.")
                        raise

                # Update database with first organized path (or folder)
                final_path = organized_paths[0] if organized_paths else torrent.save_path
                await conn.execute(
                    """
                    UPDATE shows
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, quality_detected = $3,
                        root_folder_id = $4, updated_at = NOW()
                    WHERE id = $5
                    """,
                    final_path,
                    total_size or torrent.size,
                    quality_detected,
                    root_folder_id,
                    media_id
                )

        elif media_type == "anime":
            # Get anime details
            anime = await conn.fetchrow(
                """
                SELECT title, season_year, anilist_id, mal_id
                FROM anime WHERE id = $1
                """,
                media_id
            )

            if not anime:
                print(f"Anime not found: {media_id}")
                return

            title = anime["title"]
            year = anime["season_year"]

            # Get naming patterns from profile
            naming_pattern = profile.get('anime_naming_format') or "{title} - {episode:00}"
            folder_pattern = profile.get('anime_folder_format') or "{title}"

            # Get all video files from torrent
            video_files = file_manager.extract_all_videos(torrent.save_path)

            if not video_files:
                print(f"No video files found in {torrent.save_path}")
                await conn.execute(
                    """
                    UPDATE anime
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, root_folder_id = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    torrent.save_path,
                    torrent.size,
                    root_folder_id,
                    media_id
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None

                for source_path in video_files:
                    # Parse episode info from filename
                    episode_info = parse_episode_info(Path(source_path).name)

                    if episode_info['episode_number'] is None:
                        # Skip files we can't parse episode info from
                        continue

                    # Extract metadata from first file for quality detection
                    if quality_detected is None:
                        file_metadata = metadata_extractor.extract_metadata(source_path)
                        quality_detected = file_metadata.get('quality') if file_metadata else None

                    # Build anime data for formatting
                    source_ext = Path(source_path).suffix
                    anime_data = {
                        'title': title,
                        'episode_number': episode_info['episode_number'],
                        'episode_title': episode_info.get('episode_title') or '',
                        'quality': quality_detected,
                        'anilist_id': anime["anilist_id"],
                        'mal_id': anime.get("mal_id"),
                        'year': year,
                        'extension': source_ext,
                    }

                    # Format folder and filename
                    folder_name = file_manager.format_anime_filename(
                        pattern=folder_pattern,
                        anime_data=anime_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = file_manager.format_anime_filename(
                        pattern=naming_pattern,
                        anime_data=anime_data,
                        include_extension=True,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )

                    destination_path = os.path.join(root_path, folder_name, filename)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for anime episode: {e}. Check folder configuration.")
                        raise

                # Update database with first organized path
                final_path = organized_paths[0] if organized_paths else torrent.save_path
                await conn.execute(
                    """
                    UPDATE anime
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, quality_detected = $3,
                        root_folder_id = $4, updated_at = NOW()
                    WHERE id = $5
                    """,
                    final_path,
                    total_size or torrent.size,
                    quality_detected,
                    root_folder_id,
                    media_id
                )

        elif media_type == "album":
            # Get album and artist details
            album = await conn.fetchrow(
                """
                SELECT a.*, ar.name as artist_name
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                WHERE a.id = $1
                """,
                media_id
            )

            if not album:
                print(f"Album not found: {media_id}")
                return

            title = album["title"]
            artist_name = album["artist_name"] or "Unknown Artist"
            year = album["release_date"].year if album["release_date"] else None

            # Get naming patterns from profile
            artist_folder_pattern = profile.get('music_artist_folder_format') or "{artist}"
            album_folder_pattern = profile.get('music_album_folder_format') or "{album} ({year})"
            track_naming_pattern = profile.get('music_track_naming_format') or "{track:00} - {title}"

            # Get all audio files from torrent
            audio_files = file_manager.extract_all_audio(torrent.save_path)

            if not audio_files:
                print(f"No audio files found in {torrent.save_path}")
                await conn.execute(
                    """
                    UPDATE albums
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, root_folder_id = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    torrent.save_path,
                    root_folder_id,
                    media_id
                )
            else:
                organized_paths = []
                total_size = 0

                for idx, source_path in enumerate(audio_files, start=1):
                    source_ext = Path(source_path).suffix
                    track_filename = Path(source_path).stem

                    # Build track data for formatting
                    track_data = {
                        'artist': artist_name,
                        'album': title,
                        'year': year,
                        'track_number': idx,
                        'disc_number': 1,
                        'title': track_filename,
                        'extension': source_ext,
                    }

                    # Format artist folder
                    artist_folder = file_manager.format_music_filename(
                        pattern=artist_folder_pattern,
                        track_data=track_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )

                    # Format album folder
                    album_folder = file_manager.format_music_filename(
                        pattern=album_folder_pattern,
                        track_data=track_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )

                    # Format track filename
                    track_name = file_manager.format_music_filename(
                        pattern=track_naming_pattern,
                        track_data=track_data,
                        include_extension=True,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )

                    destination_path = os.path.join(root_path, artist_folder, album_folder, track_name)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for audio file: {e}. Check folder configuration.")
                        raise

                # Update database with album folder path
                album_folder_path = os.path.dirname(organized_paths[0]) if organized_paths else torrent.save_path
                await conn.execute(
                    """
                    UPDATE albums
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, root_folder_id = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    album_folder_path,
                    root_folder_id,
                    media_id
                )

        else:
            title = "Media"

        # Notify user of completion
        user_ids = webtransport_manager.get_active_users()
        for user_id in user_ids:
            await webtransport_manager.send_download_complete(
                user_id, media_id, media_type, title
            )

        print(f"Download completed and organized: {title}")

    except Exception as e:
        print(f"Error handling completed download: {e}")
        import traceback
        traceback.print_exc()
