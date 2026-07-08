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
from app.services import naming_tokens
from app.services import artwork
from app.services import nfo
from app.services import music_tagging
from app.core.cache import cacheSet


async def get_file_operation(conn, media_id: int, media_type: str) -> str:
    """
    Get file operation (hardlink/copy) from media's profile.
    Returns 'hardlink' if use_hardlinks is True, 'copy' otherwise.
    Defaults to 'hardlink' if no profile is set.
    """
    table_map = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }

    table = table_map.get(media_type)
    if not table:
        return "hardlink"

    result = await conn.fetchrow(
        f"""
        SELECT mp.use_hardlinks
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
    )

    if result and result["use_hardlinks"] is not None:
        return "hardlink" if result["use_hardlinks"] else "copy"

    return "hardlink"


async def get_profile_settings(conn, media_id: int, media_type: str) -> dict:
    """
    Get profile settings for file organization.
    Returns dict with naming formats and character replacement settings.
    """
    table_map = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }

    table = table_map.get(media_type)
    if not table:
        return {}

    result = await conn.fetchrow(
        f"""
        SELECT
            mp.use_hardlinks,
            mp.media_server,
            mp.upgrade_replace_policy,
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
            mp.music_track_naming_format,
            mp.music_multi_disc_format,
            mp.music_embed_lyrics,
            mp.music_embed_artwork
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
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
    return file_manager.organize_file(source, dest, "hardlink")


def parse_episode_info(filename: str) -> dict:
    """
    Parse season and episode numbers from filename.
    Returns dict with season_number, episode_number, and episode_title (if found).
    """
    result = {
        "season_number": None,
        "episode_number": None,
        "episode_title": None,
    }

    # Standard patterns: S01E01, S1E1, 1x01
    patterns = [
        r"[Ss](\d{1,2})[Ee](\d{1,3})",  # S01E01
        r"(\d{1,2})x(\d{1,3})",  # 1x01
        r"[Ss]eason\s*(\d{1,2}).*[Ee]pisode\s*(\d{1,3})",  # Season 1 Episode 1
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            result["season_number"] = int(match.group(1))
            result["episode_number"] = int(match.group(2))
            break

    # Anime-style: [Group] Title - 01 [Quality].mkv
    if result["episode_number"] is None:
        anime_pattern = r"[-_\s](\d{2,3})(?:v\d)?[\s\[\.]"
        match = re.search(anime_pattern, filename)
        if match:
            result["episode_number"] = int(match.group(1))
            result["season_number"] = 1  # Assume season 1 for anime

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

        # Sample global transfer stats for the bandwidth/ratio history charts.
        from app.services.transfer_stats import record_transfer_sample

        await record_transfer_sample(client, torrents)

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
                    "SELECT * FROM download_history WHERE torrent_hash = $1", torrent.hash
                )

                if not download_record:
                    continue

                # Send real-time progress update
                download_dict = dict(download_record)
                user_ids = webtransport_manager.get_active_users()
                for user_id in user_ids:
                    await webtransport_manager.send_download_update(
                        user_id, torrent.hash, torrent.progress, torrent.download_speed
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
                        torrent.hash,
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
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )


def apply_replace_policy(grab_mode, policy, old_file_path, new_file_path):
    """
    Handle the previous file when an upgrade is imported. delete_old removes it (the only
    path that deletes a file, and only because the profile opts in); keep_old and
    keep_versions leave it in place (upgrades are named with quality, so versions coexist).
    """
    if grab_mode != "upgrade" or not old_file_path:
        return
    if os.path.normpath(old_file_path) == os.path.normpath(new_file_path):
        return  # overwritten in place, nothing to clean up
    if policy == "delete_old":
        try:
            if os.path.isfile(old_file_path):
                os.remove(old_file_path)
                print(f"Upgrade: removed replaced file {old_file_path}")
        except OSError as e:
            print(f"Could not remove replaced file {old_file_path}: {e}")
    else:
        print(f"Upgrade: kept previous file (policy={policy}): {old_file_path}")


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
            torrent.hash,
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
        illegal_replacement = profile.get("illegal_char_replacement") or ""
        colon_replacement = profile.get("colon_replacement") or " -"

        # Upgrade replace policy: capture the current file before it is replaced.
        grab_mode = download_record.get("grab_mode") or "auto"
        replace_policy = profile.get("upgrade_replace_policy") or "keep_old"
        old_file_path = None
        if grab_mode == "upgrade" and media_type in ("movie", "show", "anime", "album"):
            _table = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums"}[media_type]
            old_file_path = await conn.fetchval(f"SELECT file_path FROM {_table} WHERE id = $1", media_id)

        # Update media record based on type
        if media_type == "movie":
            # Get movie details
            movie = await conn.fetchrow(
                """
                SELECT title, release_date, tmdb_id, imdb_id, poster_path, backdrop_path,
                       overview, genres
                FROM movies WHERE id = $1
                """,
                media_id,
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
                    media_id,
                )
                return

            # Extract metadata from file
            file_metadata = metadata_extractor.extract_metadata(source_path)
            quality_detected = file_metadata.get("quality") if file_metadata else None

            # Get naming pattern from profile or use default
            naming_pattern = profile.get("movie_naming_format") or "{Movie CleanTitle} ({Release Year})"
            folder_pattern = profile.get("movie_folder_format") or "{Movie CleanTitle} ({Release Year})"

            # Resolve naming tokens from the movie row + file media info + release name.
            source_ext = Path(source_path).suffix
            nameContext = naming_tokens.build_movie_context(dict(movie), source_path, torrent.name)
            folder_name = naming_tokens.render(
                folder_pattern,
                nameContext,
                illegal_replacement=illegal_replacement,
                colon_replacement=colon_replacement,
            )
            filename = naming_tokens.render(
                naming_pattern,
                nameContext,
                illegal_replacement=illegal_replacement,
                colon_replacement=colon_replacement,
                extension=source_ext,
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
                media_id,
            )

            # Write poster/backdrop (both modes) and movie.nfo (Jellyfin mode) into the folder.
            movieFolder = os.path.dirname(final_path)
            try:
                await artwork.write_video_artwork(movieFolder, movie["poster_path"], movie["backdrop_path"])
                if profile.get("media_server") == "jellyfin":
                    nfo.write_movie_nfo(movieFolder, dict(movie))
            except Exception as e:
                print(f"Could not write movie artwork/nfo: {e}")

            # Apply the upgrade replace policy for the old file.
            apply_replace_policy(grab_mode, replace_policy, old_file_path, final_path)

            # Queue subtitle search for the organized movie file.
            try:
                from app.tasks.subtitle_search import search_subtitles

                search_subtitles.delay(media_id, "movie", final_path)
            except Exception as e:
                print(f"Could not queue subtitle search: {e}")

        elif media_type == "show":
            # Get show details
            show = await conn.fetchrow(
                """
                SELECT title, tmdb_id, tvdb_id, first_air_date, poster_path, backdrop_path,
                       overview, genres
                FROM shows WHERE id = $1
                """,
                media_id,
            )

            if not show:
                print(f"Show not found: {media_id}")
                return

            title = show["title"]
            showRow = dict(show)

            # Get naming patterns from profile
            naming_pattern = profile.get("show_naming_format") or "{Show Title} - S{Season:00}E{Episode:00}"
            folder_pattern = profile.get("show_folder_format") or "{Show Title}/Season {Season:00}"

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
                    media_id,
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None

                for source_path in video_files:
                    # Parse episode info from filename
                    episode_info = parse_episode_info(Path(source_path).name)

                    if episode_info["episode_number"] is None:
                        # Could not parse episode - queue for manual import mapping
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn,
                            torrent.hash,
                            torrent.name,
                            source_path,
                            media_type,
                            media_id,
                            root_folder_id,
                        )
                        continue

                    # Extract metadata from first file for quality detection
                    if quality_detected is None:
                        file_metadata = metadata_extractor.extract_metadata(source_path)
                        quality_detected = file_metadata.get("quality") if file_metadata else None

                    # Resolve naming tokens from the show row + episode info + file media info.
                    source_ext = Path(source_path).suffix
                    episodeInfo = {
                        "season_number": episode_info["season_number"] or 1,
                        "episode_number": episode_info["episode_number"],
                        "episode_title": episode_info.get("episode_title") or "",
                    }
                    nameContext = naming_tokens.build_show_context(
                        showRow, episodeInfo, source_path, Path(source_path).name
                    )
                    folder_name = naming_tokens.render(
                        folder_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = naming_tokens.render(
                        naming_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                        extension=source_ext,
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
                    media_id,
                )

                # Write series poster/backdrop + tvshow.nfo into the show's top folder.
                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    showFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    try:
                        await artwork.write_video_artwork(showFolder, show["poster_path"], show["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(showFolder, dict(show))
                    except Exception as e:
                        print(f"Could not write show artwork/nfo: {e}")

                # Queue subtitle search for each organized episode file.
                try:
                    from app.tasks.subtitle_search import search_subtitles

                    for episodePath in organized_paths:
                        search_subtitles.delay(media_id, "show", episodePath)
                except Exception as e:
                    print(f"Could not queue subtitle search: {e}")

        elif media_type == "anime":
            # Get anime details
            anime = await conn.fetchrow(
                """
                SELECT title, season_year, tmdb_id, anilist_id, mal_id, poster_path,
                       backdrop_path, overview
                FROM anime WHERE id = $1
                """,
                media_id,
            )

            if not anime:
                print(f"Anime not found: {media_id}")
                return

            title = anime["title"]
            year = anime["season_year"]
            animeRow = dict(anime)

            # Get naming patterns from profile
            naming_pattern = profile.get("anime_naming_format") or "{Anime Title} - {Episode:00}"
            folder_pattern = profile.get("anime_folder_format") or "{Anime Title}"

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
                    media_id,
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None

                for source_path in video_files:
                    # Parse episode info from filename
                    episode_info = parse_episode_info(Path(source_path).name)

                    if episode_info["episode_number"] is None:
                        # Could not parse episode - queue for manual import mapping
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn,
                            torrent.hash,
                            torrent.name,
                            source_path,
                            media_type,
                            media_id,
                            root_folder_id,
                        )
                        continue

                    # Extract metadata from first file for quality detection
                    if quality_detected is None:
                        file_metadata = metadata_extractor.extract_metadata(source_path)
                        quality_detected = file_metadata.get("quality") if file_metadata else None

                    # Resolve naming tokens from the anime row + episode info + file media info.
                    source_ext = Path(source_path).suffix
                    episodeInfo = {
                        "season_number": episode_info.get("season_number") or 1,
                        "episode_number": episode_info["episode_number"],
                        "episode_title": episode_info.get("episode_title") or "",
                        "absolute_episode": episode_info.get("absolute_episode"),
                    }
                    nameContext = naming_tokens.build_anime_context(
                        animeRow, episodeInfo, source_path, Path(source_path).name
                    )
                    folder_name = naming_tokens.render(
                        folder_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = naming_tokens.render(
                        naming_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                        extension=source_ext,
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
                    media_id,
                )

                # Write series poster/backdrop + tvshow.nfo into the anime's top folder.
                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    animeFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    try:
                        await artwork.write_video_artwork(animeFolder, anime["poster_path"], anime["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(animeFolder, dict(anime))
                    except Exception as e:
                        print(f"Could not write anime artwork/nfo: {e}")

        elif media_type == "album":
            # Get album and artist details
            album = await conn.fetchrow(
                """
                SELECT a.*, ar.name as artist_name, ar.picture_xl as artist_picture_xl
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                WHERE a.id = $1
                """,
                media_id,
            )

            if not album:
                print(f"Album not found: {media_id}")
                return

            title = album["title"]
            artist_name = album["artist_name"] or "Unknown Artist"
            year = album["release_date"].year if album["release_date"] else None
            # First genre for the {genre} naming token (genres is a JSONB list).
            albumGenres = album.get("genres") or []
            album_genre = None
            if albumGenres:
                first = albumGenres[0]
                album_genre = first.get("name") if isinstance(first, dict) else first

            # Get naming patterns from profile
            artist_folder_pattern = profile.get("music_artist_folder_format") or "{artist}"
            album_folder_pattern = profile.get("music_album_folder_format") or "{album} ({year})"
            track_naming_pattern = profile.get("music_track_naming_format") or "{track:00} - {title}"
            multi_disc_pattern = profile.get("music_multi_disc_format") or "{disc:00}-{track:00} - {title}"

            # Load known track metadata (disc/track numbers and titles) so multi-disc
            # albums are named correctly instead of by file position.
            track_rows = await conn.fetch(
                """
                SELECT disk_number, track_position, title, duration
                FROM tracks
                WHERE album_id = $1
                ORDER BY disk_number, track_position
                """,
                media_id,
            )
            # An album spanning more than one disc uses the multi-disc naming pattern.
            is_multi_disc = any((t["disk_number"] or 1) > 1 for t in track_rows)

            # Metadata embedding settings + one-time cover download.
            embed_artwork = bool(profile.get("music_embed_artwork"))
            embed_lyrics = bool(profile.get("music_embed_lyrics"))
            cover_bytes = None
            if embed_artwork:
                cover_bytes = await artwork.download_image(album.get("cover_xl") or album.get("cover_big"))

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
                    media_id,
                )
            else:
                organized_paths = []
                total_size = 0

                # Use real track metadata when its count matches the audio files,
                # otherwise fall back to file position with a single disc.
                use_track_meta = len(track_rows) == len(audio_files)

                for idx, source_path in enumerate(audio_files, start=1):
                    source_ext = Path(source_path).suffix
                    track_filename = Path(source_path).stem

                    if use_track_meta:
                        meta = track_rows[idx - 1]
                        disc_number = meta["disk_number"] or 1
                        track_number = meta["track_position"] or idx
                        track_title = meta["title"] or track_filename
                        track_duration = meta["duration"]
                    else:
                        disc_number = 1
                        track_number = idx
                        track_title = track_filename
                        track_duration = None

                    # Build track data for formatting
                    track_data = {
                        "artist": artist_name,
                        "album": title,
                        "year": year,
                        "track_number": track_number,
                        "disc_number": disc_number,
                        "title": track_title,
                        "genre": album_genre,
                        "extension": source_ext,
                    }

                    # Multi-disc albums use the dedicated naming pattern.
                    active_track_pattern = multi_disc_pattern if is_multi_disc else track_naming_pattern

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
                        pattern=active_track_pattern,
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

                    # Write tags, and embed artwork/lyrics into the organized file.
                    try:
                        music_tagging.write_tags(
                            destination_path,
                            {
                                "title": track_title,
                                "artist": artist_name,
                                "album": title,
                                "albumartist": artist_name,
                                "date": year,
                                "track": track_number,
                                "disc": disc_number,
                                "genre": album_genre,
                            },
                        )
                        if embed_artwork and cover_bytes:
                            music_tagging.embed_artwork(destination_path, cover_bytes)
                        if embed_lyrics:
                            plain, _synced = await music_tagging.fetch_lyrics(
                                artist_name, track_title, title, track_duration
                            )
                            if plain:
                                music_tagging.embed_lyrics(destination_path, plain)
                    except Exception as e:
                        print(f"Could not tag audio file {destination_path}: {e}")

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
                    media_id,
                )

                # Write album cover.jpg and artist folder.jpg.
                if organized_paths:
                    try:
                        await artwork.write_album_cover(
                            album_folder_path, album.get("cover_xl") or album.get("cover_big")
                        )
                        artistFolder = os.path.dirname(album_folder_path)
                        if album.get("artist_picture_xl"):
                            await artwork.write_artist_image(artistFolder, album["artist_picture_xl"])
                    except Exception as e:
                        print(f"Could not write album/artist artwork: {e}")

        else:
            title = "Media"

        # Notify user of completion
        user_ids = webtransport_manager.get_active_users()
        for user_id in user_ids:
            await webtransport_manager.send_download_complete(user_id, media_id, media_type, title)

        print(f"Download completed and organized: {title}")

    except Exception as e:
        print(f"Error handling completed download: {e}")
        import traceback

        traceback.print_exc()
